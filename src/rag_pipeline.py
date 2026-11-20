
"""Récupération à la demande pour le MVP FOMC (sans lecture des qrels).

Réutilise les index et modèles existants.
Les scores de méthodes différentes ne sont pas comparables.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from functools import lru_cache
from time import perf_counter

import numpy as np

from common import CONFIG, CONTEXT_K, lexical_tokens, stable_order
from build_indexes import load_indexes, load_dense_encoder


@lru_cache(maxsize=1)
def assets():
    chunks, bm25, vectors = load_indexes()
    dense_model = load_dense_encoder()
    ids = [chunk["chunk_id"] for chunk in chunks]
    return chunks, bm25, vectors, dense_model, ids


def _rrf(ranks, constant):
    values = defaultdict(float)
    for ranking in ranks:
        for position, cid in enumerate(ranking, 1):
            values[cid] += 1.0 / (constant + position)
    return values


def retrieve(
    question: str,
    method: str = "hybrid_rrf",
    reranker: str = "colbert",
    top_k: int = CONFIG['top_k'],
    context_k: int = CONTEXT_K,
    timings: dict | None = None,
) -> list[dict]:

    if not isinstance(question, str) or not question.strip():
        raise ValueError("La question doit être non vide")

    if method not in ("bm25", "dense", "hybrid_rrf"):
        raise ValueError("Méthode de récupération inconnue")

    if reranker not in ("none", "bm25", "colbert", "cross_encoder"):
        raise ValueError("Reranker inconnu")

    if not 1 <= context_k <= CONTEXT_K or not context_k <= top_k <= 100:
        raise ValueError("Exiger 1 <= context_k <= 6 et context_k <= top_k <= 100")

    t_start = perf_counter()

    chunks, bm25, vectors, dense_model, ids = assets()

    t_assets = perf_counter()

    if top_k > len(chunks):
        raise ValueError("top_k supérieur à la taille du corpus")

    lexical = semantic = None
    lex_order = dense_order = None

    if method in ("bm25", "hybrid_rrf") or reranker == "bm25":
        lexical = np.asarray(
            bm25.get_scores(lexical_tokens(question)),
            dtype=np.float64,
        )
        lex_order = stable_order(lexical, ids)[:top_k]

    if method in ("dense", "hybrid_rrf"):
        query_text = "query: " + question

        if (
            len(
                dense_model.tokenizer.encode(
                    query_text,
                    truncation=False,
                )
            )
            > CONFIG["max_model_tokens"]
        ):
            raise ValueError("Question trop longue pour E5")

        query_vector = dense_model.encode(
            [query_text],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]

        semantic = vectors @ np.asarray(
            query_vector,
            dtype=np.float32,
        )

        dense_order = stable_order(semantic, ids)[:top_k]

    rrf_scores = {}

    if method == "bm25":
        candidate_idx = list(lex_order)

    elif method == "dense":
        candidate_idx = list(dense_order)

    else:
        rrf_scores = _rrf(
            (
                [ids[i] for i in lex_order],
                [ids[i] for i in dense_order],
            ),
            CONFIG["rrf_constant"],
        )

        idx = {cid: i for i, cid in enumerate(ids)}

        candidate_idx = [
            idx[cid]
            for cid in sorted(
                rrf_scores,
                key=lambda cid: (-rrf_scores[cid], cid),
            )[:top_k]
        ]

    candidate_ids = [ids[i] for i in candidate_idx]

    scores = np.array(
        [
            (
                float(lexical[i])
                if method == "bm25"
                else float(semantic[i])
                if method == "dense"
                else float(rrf_scores[ids[i]])
            )
            for i in candidate_idx
        ],
        dtype=float,
    )

    t_retrieval = perf_counter()

    # Reranking sur le même pool de candidats.

    if reranker == "bm25":
        rerank_scores = np.asarray(
            [lexical[i] for i in candidate_idx],
            dtype=float,
        )

    elif reranker == "cross_encoder":
        from rerank import CrossEncoder

        model = CrossEncoder()

        rerank_scores = np.asarray(
            model.score(
                question,
                [chunks[i]["search_text"] for i in candidate_idx],
            ),
            dtype=float,
        )

    elif reranker == "colbert":
        from rerank import ColBERT, maxsim

        model = ColBERT()

        qvec = model.encode([question], True)[0]

        dvecs = model.encode(
            [chunks[i]["search_text"] for i in candidate_idx],
            False,
        )

        rerank_scores = np.asarray(
            [maxsim(qvec, dv) for dv in dvecs],
            dtype=float,
        )

    else:
        rerank_scores = scores.copy()

    t_reranking = perf_counter()

    if (
        len(rerank_scores) != len(candidate_ids)
        or not np.isfinite(rerank_scores).all()
    ):
        raise ValueError("Scores de reranking invalides")

    order = (
        list(range(len(candidate_ids)))
        if reranker == "none"
        else stable_order(rerank_scores, candidate_ids)
    )

    results = []

    for rank, position in enumerate(order[:context_k], 1):
        c = chunks[candidate_idx[position]]

        url = c.get("source_url", "")
        page = c.get("page_start")

        if url and page:
            url = url.split("#")[0] + f"#page={page}"

        results.append(
            {
                "rank": rank,
                "chunk_id": c["chunk_id"],
                "text": c["text"],
                "document": c["filename"],
                "meeting_end": c["meeting_end"],
                "pages": c.get(
                    "pages",
                    list(
                        range(
                            c["page_start"],
                            c["page_end"] + 1,
                        )
                    ),
                ),
                "source_url": url,
                "retrieval_score": float(scores[position]),
                "rerank_score": float(rerank_scores[position]),
                "retriever": method,
                "reranker": reranker,
            }
        )

    # Nouveau : enregistrer les durées d'exécution.
    if timings is not None:
        timings.update(
            {
                "assets_s": round(t_assets - t_start, 3),
                "retrieval_s": round(
                    t_retrieval - t_assets, 3
                ),
                "reranking_s": round(
                    t_reranking - t_retrieval, 3
                ),
                "retrieval_total_s": round(
                    perf_counter() - t_start, 3
                ),
                "candidate_count": len(candidate_ids),
                "selected_count": len(results),
                "context_k": context_k,
            }
        )

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "question",
        help="Question libre entre guillemets",
    )

    parser.add_argument(
        "--method",
        choices=["bm25", "dense", "hybrid_rrf"],
        default="hybrid_rrf",
    )

    parser.add_argument(
        "--reranker",
        choices=[
            "none",
            "bm25",
            "colbert",
            "cross_encoder",
        ],
        default="colbert",
    )

    parser.add_argument(
        "--context-k",
        type=int,
        default=CONTEXT_K,
    )

    args = parser.parse_args()

    print(
        json.dumps(
            retrieve(
                args.question,
                args.method,
                args.reranker,
                context_k=args.context_k,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
