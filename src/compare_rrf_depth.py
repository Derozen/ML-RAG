"""Comparer les profondeurs de fusion RRF 20, 50 et 100 sans modifier le pipeline.

Usage (depuis la racine RAG_FOMC): python src/compare_rrf_depth.py
Les qrels restent ceux des pages PDF et les mêmes 20 chunks finaux sont évalués.
"""
from __future__ import annotations

from collections import defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import mean
import time

import numpy as np

from common import (
    ROOT, CONFIG, questions, lexical_tokens, stable_order,
    digest, log,
)
from build_indexes import load_indexes, load_dense_encoder
from align_references import project_pages

DEPTHS = (20, 50, 100)
FINAL_TOP_K = 20


def read_jsonl(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def read_qrels(path):
    relevance = defaultdict(dict)
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            relevance[row["question_id"]][row["page_id"]] = int(row["relevance"])
    return relevance


def rrf_top_k(lexical_ids, dense_ids, final_k, constant):
    scores = defaultdict(float)
    for ranking in (lexical_ids, dense_ids):
        if len(ranking) != len(set(ranking)):
            raise ValueError("Doublons dans un classement de récupération")
        for rank, cid in enumerate(ranking, 1):
            scores[cid] += 1.0 / (constant + rank)
    return sorted(scores, key=lambda cid: (-scores[cid], cid))[:final_k]


def page_metrics(pages, relevance, pool_pages):
    relevant = {page for page, grade in relevance.items() if grade > 0}
    if not relevant:
        raise ValueError("Question sans qrel positif")
    out = {}
    for cutoff in (5, 10, 20):
        out[f"recall_at_{cutoff}"] = len(set(pages[:cutoff]) & relevant) / len(relevant)
    def dcg(grades):
        return sum((2 ** grade - 1) / math.log2(rank + 1)
                   for rank, grade in enumerate(grades, 1))
    ideal = dcg(sorted(relevance.values(), reverse=True)[:10])
    out["ndcg_at_10"] = dcg([relevance.get(p, 0) for p in pages[:10]]) / ideal
    first = next((rank for rank, p in enumerate(pages[:10], 1) if p in relevant), None)
    out["mrr_at_10"] = 1.0 / first if first else 0.0
    out["pool_page_recall"] = len(pool_pages & relevant) / len(relevant)
    out["candidate_pages"] = len(pages)
    return out


def write_csv(path, rows):
    if not rows:
        raise ValueError("Aucun résultat à exporter")
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    queries = questions()
    chunks, bm25, vectors = load_indexes()
    ids = [c["chunk_id"] for c in chunks]
    if len(ids) < max(DEPTHS):
        raise ValueError("Corpus trop petit pour la profondeur 100")
    mapping_file = ROOT / "data/evaluation/chunk_pages.jsonl"
    qrels_file = ROOT / "data/evaluation/page_qrels.tsv"
    audit_file = ROOT / "data/evaluation/alignment_report.json"
    audit = json.loads(audit_file.read_text(encoding="utf-8"))
    for path, key in ((mapping_file, "mapping_sha256"),
                      (qrels_file, "page_qrels_sha256"),
                      (ROOT / "data/processed/chunks.jsonl", "chunks_sha256"),
                      (ROOT / "data/evaluation/queries_145.jsonl", "questions_sha256")):
        if digest(path) != audit[key]:
            raise ValueError(f"Fichier modifié depuis l'alignement : {path}")
    mapping = {r["chunk_id"]: r["page_ids"] for r in read_jsonl(mapping_file)}
    if set(mapping) != set(ids):
        raise ValueError("Mapping et index ne contiennent pas les mêmes chunks")
    qrels = read_qrels(qrels_file)
    if set(qrels) != {q["id"] for q in queries}:
        raise ValueError("Questions et qrels incohérents")

    model = load_dense_encoder()
    output = ROOT / "results/rrf_depth"
    output.mkdir(parents=True, exist_ok=True)
    metric_rows, ranking_rows = [], []

    # Echauffement hors du chronométrage : les temps restent exploratoires.
    model.encode(["query: " + queries[0]["question"]],
                 normalize_embeddings=True, convert_to_numpy=True,
                 show_progress_bar=False)
    bm25.get_scores(lexical_tokens(queries[0]["question"]))

    for n, query in enumerate(queries, 1):
        qid = query["id"]
        question = query["question"]
        if len(model.tokenizer.encode("query: " + question, truncation=False)) > CONFIG["max_model_tokens"]:
            raise ValueError(f"Question trop longue : {qid}")

        started = time.perf_counter()
        lexical_scores = np.asarray(bm25.get_scores(lexical_tokens(question)))
        bm25_seconds = time.perf_counter() - started

        started = time.perf_counter()
        query_vector = model.encode(["query: " + question],
                                    normalize_embeddings=True,
                                    convert_to_numpy=True,
                                    show_progress_bar=False)[0]
        dense_scores = vectors @ query_vector
        dense_seconds = time.perf_counter() - started

        # Stable_order trie l'intégralité du corpus : chaque profondeur
        # utilise exactement le même classement BM25/E5 initial.
        lexical_order = stable_order(lexical_scores, ids)
        dense_order = stable_order(dense_scores, ids)

        for depth in DEPTHS:
            started = time.perf_counter()
            final_ids = rrf_top_k(
                [ids[i] for i in lexical_order[:depth]],
                [ids[i] for i in dense_order[:depth]],
                FINAL_TOP_K, CONFIG["rrf_constant"]
            )
            fusion_seconds = time.perf_counter() - started
            if len(final_ids) != FINAL_TOP_K or len(set(final_ids)) != FINAL_TOP_K:
                raise ValueError(f"Résultats RRF non conformes : {qid}, profondeur {depth}")
            page_ranking = project_pages(final_ids, mapping)
            pool_pages = set(page_ranking)
            scores = page_metrics(page_ranking, qrels[qid], pool_pages)
            metric_rows.append({
                "question_id": qid, "depth": depth,
                **scores, "zero_pool": int(scores["pool_page_recall"] == 0),
                "bm25_seconds": bm25_seconds,
                "dense_seconds": dense_seconds,
                "fusion_seconds": fusion_seconds,
                "estimated_total_seconds": bm25_seconds + dense_seconds + fusion_seconds,
            })
            ranking_rows.append({
                "question_id": qid, "depth": depth,
                "chunk_ids": final_ids, "page_ids": page_ranking,
            })
        if n % 10 == 0 or n == len(queries):
            log(f"Profondeurs RRF : {n}/{len(queries)}")

    summary = []
    metrics = ("recall_at_5", "recall_at_10", "recall_at_20", "ndcg_at_10",
               "mrr_at_10", "pool_page_recall", "candidate_pages")
    for depth in DEPTHS:
        group = [r for r in metric_rows if r["depth"] == depth]
        summary.append({
            "depth": depth, "final_top_k": FINAL_TOP_K,
            "questions": len(group),
            **{metric: mean(r[metric] for r in group) for metric in metrics},
            "zero_pool_questions": sum(r["zero_pool"] for r in group),
            "estimated_total_median_ms": float(np.median(
                [r["estimated_total_seconds"] for r in group]) * 1000),
        })

    write_csv(output / "comparison.csv", summary)
    write_csv(output / "metrics_per_question.csv", metric_rows)
    with (output / "page_rankings.jsonl").open("w", encoding="utf-8") as stream:
        for record in ranking_rows:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    (output / "run.json").write_text(json.dumps({
        "depths": DEPTHS, "final_top_k": FINAL_TOP_K,
        "evaluation_unit": "unique PDF page", "qrels_quality": "silver",
        "rrf_constant": CONFIG["rrf_constant"],
        "source_chunks_sha256": digest(ROOT / "data/processed/chunks.jsonl"),
        "source_qrels_sha256": digest(qrels_file),
        "note": "All depths use original qrels; no change to existing rankings or indexes."
    }, indent=2), encoding="utf-8")
    for row in summary:
        log(f"RRF depth={row['depth']:3} | recall@20={row['recall_at_20']:.3f} "
            f"| nDCG@10={row['ndcg_at_10']:.3f} "
            f"| pool={row['pool_page_recall']:.3f} "
            f"| zero-pool={row['zero_pool_questions']}")
    log(f"Résultats dans : {output}")


if __name__ == "__main__":
    main()
