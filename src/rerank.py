"""Reclasser les mêmes candidats BM25, ColBERT MaxSim et Cross-Encoder.

Ne consulte jamais les qrels. Préserve les pools et vérifie les empreintes
avant de réutiliser un calcul de reranking.
"""

import argparse
import gc
import time
from collections import defaultdict

import numpy as np

from common import (
    ROOT, CONFIG, METHODS, RERANKERS, questions, read_jsonl, read_json,
    write_jsonl, write_json, digest, log, model_dir, prepare_torch,
    stable_order, environment, lexical_tokens,
)
from build_indexes import load_indexes
from common import CONTEXT_K, select_context


def export_context(name):
    """Export actual final contexts; retain the full ranking for candidate audits."""
    source = ROOT / 'results/retrieval/rankings.jsonl'
    if not validate_cache(name, source):
        raise ValueError(f'Classement complet absent: {name}')
    path = ROOT / f'results/reranking/{name}.jsonl'
    groups = defaultdict(list)
    for row in read_jsonl(path):
        groups[row['question_id'], row['retrieval']].append(row)
    if len(groups) != len(questions()) * len(METHODS):
        raise ValueError('Groupes incomplets pour le contexte final')
    for limit in (5, CONTEXT_K):
        selected = []
        for group in groups.values():
            selected.extend(select_context(sorted(group, key=lambda r:r['rank']), limit))
        output = ROOT / f'results/reranking/{name}_top{limit}.jsonl'
        write_jsonl(output, selected)
        write_json(output.with_suffix('.meta.json'), dict(
            candidates_per_query=CONFIG['top_k'], final_context_k=limit,
            source_sha256=digest(path), output_sha256=digest(output), rows=len(selected)))


def maxsim(query, document):
    """Somme, pour chaque token de requête, de sa meilleure similarité document."""
    if len(query) == 0 or len(document) == 0:
        raise ValueError("Matrice de tokens vide")
    value = float(np.max(query @ document.T, axis=1).sum())
    if not np.isfinite(value):
        raise ValueError("Score MaxSim non fini")
    return value


class ColBERT:
    """Encodeur BERT, projection apprise, marqueurs de rôle et score MaxSim."""

    def __init__(self):
        self.torch = prepare_torch()
        from transformers import AutoConfig, AutoTokenizer, BertModel
        from safetensors.torch import load_file

        path = model_dir("colbert")
        config = AutoConfig.from_pretrained(str(path), local_files_only=True)
        state = load_file(str(path / "model.safetensors"), device="cpu")
        projection_keys = [k for k in state if k.endswith("linear.weight")]
        if len(projection_keys) != 1:
            raise ValueError(f"Projection ColBERT introuvable : {projection_keys}")
        self.projection = state[projection_keys[0]].float()
        backbone = {
            k.removeprefix("bert."): v for k, v in state.items()
            if k.startswith("bert.") and not k.removeprefix("bert.").startswith("pooler.")
        }
        if not backbone:
            raise ValueError("Poids de l'encodeur ColBERT introuvables")
        self.model = BertModel(config, add_pooling_layer=False)
        self.model.load_state_dict(backbone, strict=True)
        self.model.eval()
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(path), local_files_only=True, use_fast=True
        )
        self.options = read_json(path / "onnx_config.json")
        expected = (self.options["embedding_dim"], config.hidden_size)
        if tuple(self.projection.shape) != expected:
            raise ValueError(f"Projection ColBERT inattendue : {self.projection.shape}")
        self.skip = {
            self.tokenizer.convert_tokens_to_ids(word)
            for word in self.options["skiplist_words"]
        }
        self.truncations = {"query": 0, "document": 0}

    def encode(self, texts, is_query):
        torch = self.torch
        outputs = []
        kind = "query" if is_query else "document"
        limit = CONFIG["colbert_query_length" if is_query else "colbert_document_length"]
        marker = self.options["query_prefix_id" if is_query else "document_prefix_id"]
        for start in range(0, len(texts), CONFIG["batch_size"]):
            batch = texts[start:start + CONFIG["batch_size"]]
            lengths = [
                len(self.tokenizer.encode(t, add_special_tokens=True, truncation=False)) + 1
                for t in batch
            ]
            self.truncations[kind] += sum(length > limit for length in lengths)
            tokens = self.tokenizer(
                batch, padding=True, truncation=True, max_length=limit - 1,
                return_tensors="pt",
            )
            for name, value in list(tokens.items()):
                fill = marker if name == "input_ids" else 1 if name == "attention_mask" else 0
                column = torch.full((value.shape[0], 1), fill, dtype=value.dtype)
                tokens[name] = torch.cat([value[:, :1], column, value[:, 1:]], dim=1)
            with torch.inference_mode():
                hidden = self.model(**tokens).last_hidden_state
                projected = torch.nn.functional.normalize(
                    hidden @ self.projection.T, p=2, dim=-1
                )
            for i in range(len(batch)):
                keep = tokens["attention_mask"][i].bool()
                if not is_query:
                    for token_id in self.skip:
                        keep &= tokens["input_ids"][i] != token_id
                arr = projected[i][keep].cpu().numpy().astype(np.float32)
                if len(arr) == 0 or not np.isfinite(arr).all():
                    raise ValueError("Embedding ColBERT vide ou non fini")
                outputs.append(arr)
            if not is_query and (start // CONFIG["batch_size"]) % 25 == 0:
                log(f"ColBERT encode {min(start + len(batch), len(texts))}/{len(texts)} passages")
        return outputs


class CrossEncoder:
    def __init__(self):
        self.torch = prepare_torch()
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        path = str(model_dir("cross_encoder"))
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            path, local_files_only=True
        )
        self.model.eval()
        self.truncations = 0

    def score(self, query, documents):
        result = []
        for start in range(0, len(documents), CONFIG["batch_size"]):
            batch = documents[start:start + CONFIG["batch_size"]]
            self.truncations += sum(
                len(self.tokenizer.encode(query, passage, truncation=False))
                > CONFIG["cross_encoder_max_length"] for passage in batch
            )
            tokens = self.tokenizer(
                [query] * len(batch), batch, padding=True,
                truncation="only_second", max_length=CONFIG["cross_encoder_max_length"],
                return_tensors="pt",
            )
            with self.torch.inference_mode():
                logits = self.model(**tokens).logits
            if logits.ndim != 2 or logits.shape[1] != 1:
                raise ValueError(f"Sortie Cross-Encoder inattendue : {tuple(logits.shape)}")
            result.extend(logits[:, 0].cpu().numpy().astype(float).tolist())
        return result


def validate_pool(before, after):
    k = CONFIG["top_k"]
    before_ids = [r["chunk_id"] for r in before]
    after_ids = [r["chunk_id"] for r in after]
    if (
        len(before_ids) != k or len(after_ids) != k
        or len(set(before_ids)) != k or len(set(after_ids)) != k
        or set(before_ids) != set(after_ids)
    ):
        raise ValueError("Le reranker a modifié le pool de candidats")


def validate_input_pools(initial, queries, chunks_by_id):
    """Valide l'intégralité des listes de récupération avant tout calcul."""
    pools = defaultdict(list)
    for row in initial:
        pools[(row["question_id"], row["method"])].append(row)
    expected = {(q["id"], method) for q in queries for method in METHODS}
    if set(pools) != expected:
        raise ValueError("Questions ou méthodes de récupération manquantes/inattendues")
    k = CONFIG["top_k"]
    for key, rows in pools.items():
        ordered = sorted(rows, key=lambda r: r["rank"])
        ids = [r["chunk_id"] for r in ordered]
        if [r["rank"] for r in ordered] != list(range(1, k + 1)):
            raise ValueError(f"Rangs invalides pour {key}")
        if len(ids) != k or len(set(ids)) != k:
            raise ValueError(f"Candidats insuffisants ou dupliqués pour {key}")
        if any(cid not in chunks_by_id for cid in ids):
            raise ValueError(f"Identifiant de chunk inconnu pour {key}")
        pools[key] = ordered
    return pools


def validate_cache(name, source):
    """Retourne True uniquement si tous les fichiers de cache sont cohérents."""
    base = ROOT / "results/reranking"
    output = base / f"{name}.jsonl"
    metadata_path = base / f"{name}_run.json"
    timings_path = base / f"{name}_timings.jsonl"
    existing = [path.exists() for path in (output, metadata_path, timings_path)]
    if not any(existing):
        return False
    if not all(existing):
        raise ValueError(f"Cache de reranking incomplet : {name}")
    metadata = read_json(metadata_path)
    if (
        metadata.get("input_rankings_sha256") != digest(source)
        or metadata.get("output_sha256") != digest(output)
        or metadata.get("config") != CONFIG
        or metadata.get("rankings") != len(questions()) * len(METHODS) * CONFIG["top_k"]
    ):
        raise ValueError(
            f"Cache reranking périmé ou altéré : {name}. "
            "Sauvegarder puis déplacer les anciens fichiers avant de relancer."
        )
    return True


def main(only=None):
    queries = questions()
    chunks, bm25, _ = load_indexes()
    by_id = {c["chunk_id"]: c for c in chunks}
    index = {c["chunk_id"]: i for i, c in enumerate(chunks)}

    source = ROOT / "results/retrieval/rankings.jsonl"
    initial = read_jsonl(source)
    run = read_json(ROOT / "results/retrieval/run.json")
    if (
        run.get("rankings_sha256") != digest(source)
        or run.get("questions_sha256") != digest(ROOT / "data/evaluation/queries_145.jsonl")
        or run.get("chunks_sha256") != digest(ROOT / "data/processed/chunks.jsonl")
    ):
        raise ValueError("Classements de récupération périmés ou modifiés")
    pools = validate_input_pools(initial, queries, by_id)
    selected = [only] if only else list(RERANKERS)

    for name in selected:
        if validate_cache(name, source):
            export_context(name)
            log(f"Reranking déjà calculé et vérifié : {name}")
            continue
        log(f"Reranker : {name}")
        rows, timings, notes = [], [], {}
        if name == "colbert":
            model = ColBERT()
            candidate_ids = sorted({r["chunk_id"] for r in initial})
            started = time.perf_counter()
            embeddings = model.encode(
                [by_id[cid]["search_text"] for cid in candidate_ids], False
            )
            document_embeddings = dict(zip(candidate_ids, embeddings))
            notes["document_preencoding_seconds"] = time.perf_counter() - started
            notes["document_preencoding_scope"] = (
                "Union of retrieved candidates; no qrels; excluded from online latency."
            )
            del embeddings
        elif name == "cross_encoder":
            model = CrossEncoder()

        first = queries[0]
        first_ids = [r["chunk_id"] for r in pools[(first["id"], "bm25")]]
        if name == "colbert":
            model.encode([first["question"]], True)
        elif name == "cross_encoder":
            model.score(first["question"], [by_id[first_ids[0]]["search_text"]])
        else:
            bm25.get_scores(lexical_tokens(first["question"]))

        for n, q in enumerate(queries, 1):
            # Reuse identical question representation for all three retrieval pools.
            cached_query = None
            cached_bm25 = None
            if name == "colbert":
                query_start = time.perf_counter()
                cached_query = model.encode([q["question"]], True)[0]
                query_seconds = time.perf_counter() - query_start
            elif name == "bm25":
                query_start = time.perf_counter()
                cached_bm25 = bm25.get_scores(lexical_tokens(q["question"]))
                query_seconds = time.perf_counter() - query_start
            else:
                query_seconds = 0.0
            for retrieval in METHODS:
                before = pools[(q["id"], retrieval)]
                ids = [r["chunk_id"] for r in before]
                started = time.perf_counter()
                if name == "bm25":
                    scores = [cached_bm25[index[cid]] for cid in ids]
                elif name == "colbert":
                    scores = [maxsim(cached_query, document_embeddings[cid]) for cid in ids]
                elif name == "cross_encoder":
                    scores = model.score(
                        q["question"], [by_id[cid]["search_text"] for cid in ids]
                    )
                else:
                    raise ValueError(f"Reranker non reconnu : {name}")
                if len(scores) != len(ids) or not np.isfinite(np.asarray(scores)).all():
                    raise ValueError(f"Scores invalides : {q['id']} / {retrieval} / {name}")
                order = stable_order(scores, ids)
                after = [
                    dict(question_id=q["id"], retrieval=retrieval, reranker=name,
                         rank=rank, chunk_id=ids[i], score=float(scores[i]))
                    for rank, i in enumerate(order, 1)
                ]
                seconds = time.perf_counter() - started
                validate_pool(before, after)
                if name == "bm25" and retrieval == "bm25" and ids != [r["chunk_id"] for r in after]:
                    raise ValueError("Contrôle BM25→BM25 incohérent")
                rows.extend(after)
                timings.append(dict(
                    question_id=q["id"], retrieval=retrieval, reranker=name,
                    seconds=seconds + query_seconds, shared_query_seconds=query_seconds,
                    timing_note="Per-pool modeled latency includes the shared query cost (not total wall time)",
                ))
            if n % 10 == 0 or n == len(queries):
                log(f"{name} : {n}/{len(queries)} questions")
        if name != "bm25":
            notes["truncation_counts"] = model.truncations
        output = ROOT / f"results/reranking/{name}.jsonl"
        write_jsonl(output, rows)
        write_jsonl(ROOT / f"results/reranking/{name}_timings.jsonl", timings)
        write_json(ROOT / f"results/reranking/{name}_run.json", dict(
            config=CONFIG, questions=len(queries), rankings=len(rows),
            input_rankings_sha256=digest(source), output_sha256=digest(output),
            candidate_set_checks=len(queries) * len(METHODS), model_notes=notes,
            environment=environment(),
            timing=(
                "One sequential pass after warm-up. ColBERT document preencoding excluded. "
                "BM25/ColBERT shared query costs logged in shared_query_seconds and "
                "included in seconds for each pool as an estimated standalone cost. "
                "Cross-encoder scores pairs within seconds. "
                "Do not compare timings directly without accounting for these differences."
            ),
        ))
        if name != "bm25":
            del model
            if name == "colbert":
                del document_embeddings
            gc.collect()
        log(f"Reranking {name} terminé : {len(rows)} rangs")
        export_context(name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=RERANKERS)
    main(parser.parse_args().only)
