"""Comparer BM25, E5 et RRF sans consulter les jugements de pertinence.

Les scores BM25 et E5 sont calculés une fois par question puis réutilisés
pour construire les classements BM25, Dense et hybride RRF.
Les latences sont des estimations séquentielles après échauffement :
- BM25 : tokenisation + scoring + top-k ;
- Dense : encodage de la question + produit matriciel + top-k ;
- Hybride : somme des coûts BM25 + Dense + fusion RRF.
Elles ne représentent pas trois exécutions indépendantes et simultanées.
"""

from __future__ import annotations

import time
from collections import defaultdict

import numpy as np

from common import (
    ROOT, CONFIG, METHODS, questions, lexical_tokens, stable_order,
    write_jsonl, write_json, digest, log, environment,
)
from build_indexes import load_indexes, load_dense_encoder


def rrf(rankings, constant=60):
    """Fusion par rang réciproque ; l'absence d'un document ne contribue pas."""
    if constant <= 0:
        raise ValueError("La constante RRF doit être strictement positive")
    scores = defaultdict(float)
    for ranking in rankings:
        if len(ranking) != len(set(ranking)):
            raise ValueError("Doublon de candidat dans un classement RRF")
        for rank, cid in enumerate(ranking, 1):
            scores[cid] += 1.0 / (constant + rank)
    return sorted(scores, key=lambda cid: (-scores[cid], cid)), scores


def main():
    queries = questions()
    if not queries:
        raise ValueError("Aucune question disponible")

    chunks, bm25, vectors = load_indexes()
    ids = [chunk["chunk_id"] for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("Identifiants de chunks dupliqués")

    k = int(CONFIG["top_k"])
    if not 1 <= k <= len(ids):
        raise ValueError(f"top_k invalide : {k} pour {len(ids)} chunks")

    expected_methods = {"bm25", "dense", "hybrid_rrf"}
    if set(METHODS) != expected_methods or len(METHODS) != 3:
        raise ValueError(f"Méthodes inattendues : {METHODS}")

    log("Chargement du modèle E5 pour les requêtes")
    model = load_dense_encoder()
    id_to_index = {cid: i for i, cid in enumerate(ids)}

    # Échauffement hors chronométrage (modèle et BM25 chargés).
    first_query = queries[0]["question"]
    model.encode(["query: " + first_query], normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False)
    bm25.get_scores(lexical_tokens(first_query))

    records, timings = [], []
    timings_policy = (
        "CPU, une exécution séquentielle par question après échauffement. "
        "Les temps excluent les chargements du modèle et des index. "
        "BM25: tokenisation, scores et tri top-k. "
        "Dense: encodage de question, similarité et tri top-k. "
        "Hybride: somme BM25 + Dense + coût additionnel de fusion RRF; "
        "ce total est reconstruit à partir des composants réutilisés. "
        "Mesures exploratoires, sans répétitions ni percentiles de confiance."
    )

    for number, query in enumerate(queries, 1):
        qid, query_text = query["id"], query["question"]

        # 1. Recherche lexicale : une seule fois pour cette question.
        bm25_start = time.perf_counter()
        lexical = np.asarray(bm25.get_scores(lexical_tokens(query_text)), dtype=np.float64)
        if lexical.shape != (len(ids),):
            raise ValueError(f"Taille des scores BM25 invalide pour {qid}")
        lex_order = stable_order(lexical, ids)[:k]
        bm25_seconds = time.perf_counter() - bm25_start

        # 2. Recherche sémantique : une seule fois pour cette question.
        dense_start = time.perf_counter()
        prefixed_query = "query: " + query_text
        if len(model.tokenizer.encode(prefixed_query, truncation=False)) > CONFIG["max_model_tokens"]:
            raise ValueError(f"Question trop longue : {qid}")
        qvec = np.asarray(
            model.encode([prefixed_query], normalize_embeddings=True,
                         convert_to_numpy=True, show_progress_bar=False)[0],
            dtype=np.float32,
        )
        semantic = vectors @ qvec
        if semantic.shape != (len(ids),):
            raise ValueError(f"Taille des scores E5 invalide pour {qid}")
        dense_order = stable_order(semantic, ids)[:k]
        dense_seconds = time.perf_counter() - dense_start

        # 3. Fusion RRF ; profondeur de fusion = top-k, comme la baseline.
        fusion_start = time.perf_counter()
        fused_order_ids, fused_scores = rrf(
            [[ids[i] for i in lex_order], [ids[i] for i in dense_order]],
            CONFIG["rrf_constant"],
        )
        hybrid_order = [id_to_index[cid] for cid in fused_order_ids[:k]]
        fusion_seconds = time.perf_counter() - fusion_start

        orders = {
            "bm25": lex_order,
            "dense": dense_order,
            "hybrid_rrf": hybrid_order,
        }
        scores = {"bm25": lexical, "dense": semantic}
        seconds = {
            "bm25": bm25_seconds,
            "dense": dense_seconds,
            "hybrid_rrf": bm25_seconds + dense_seconds + fusion_seconds,
        }

        for method in METHODS:
            order = orders[method]
            if len(order) != k or len(set(order)) != k:
                raise ValueError(f"Classement {method} invalide pour {qid}")
            timings.append({"question_id": qid, "method": method,
                            "seconds": seconds[method]})
            for rank, i in enumerate(order, 1):
                chunk = chunks[i]
                cid = ids[i]
                score = (fused_scores[cid] if method == "hybrid_rrf"
                         else float(scores[method][i]))
                records.append({
                    "question_id": qid,
                    "method": method,
                    "rank": rank,
                    "chunk_id": cid,
                    "score": float(score),
                    "filename": chunk["filename"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                })

        if number % 10 == 0 or number == len(queries):
            log(f"Récupération {number}/{len(queries)}")

    records.sort(key=lambda r: (r["question_id"], r["method"], r["rank"]))
    if len(records) != len(queries) * len(METHODS) * k:
        raise ValueError("Nombre de classements exportés inattendu")
    if len(timings) != len(queries) * len(METHODS):
        raise ValueError("Nombre de mesures de temps inattendu")

    rankings_path = ROOT / "results/retrieval/rankings.jsonl"
    write_jsonl(rankings_path, records)
    write_jsonl(ROOT / "results/retrieval/timings.jsonl", timings)
    write_json(ROOT / "results/retrieval/run.json", {
        "config": CONFIG,
        "questions_sha256": digest(ROOT / "data/evaluation/queries_145.jsonl"),
        "chunks_sha256": digest(ROOT / "data/processed/chunks.jsonl"),
        "rankings_sha256": digest(rankings_path),
        "questions": len(queries),
        "rankings": len(records),
        "split": "all",
        "environment": environment(),
        "timing": timings_policy,
    })
    log(f"Trois classements exportés : {len(records)} lignes")


if __name__ == "__main__":
    main()
