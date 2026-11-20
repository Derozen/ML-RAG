
"""Préparer un audit humain des références silver FOMC.

Aucune modification des qrels originaux.
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent

TARGETS = ["FOMC_004", "FOMC_007", "FOMC_061"]
METHODS = ("bm25", "dense", "hybrid_rrf")
TOP_K = 20

def load_jsonl(path):
    with path.open(encoding="utf-8-sig") as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]

questions = {
    q["question_id"]: q
    for q in load_jsonl(
        ROOT / "data/evaluation/queries_145.jsonl"
    )
}

chunks = {
    c["chunk_id"]: c
    for c in load_jsonl(
        ROOT / "data/processed/chunks.jsonl"
    )
}

rankings = load_jsonl(
    ROOT / "results/retrieval/rankings.jsonl"
)

mapping = {
    r["chunk_id"]: r["page_ids"]
    for r in load_jsonl(
        ROOT / "data/evaluation/chunk_pages.jsonl"
    )
}

qrels = defaultdict(dict)

with (
    ROOT / "data/evaluation/silver_qrels_PAGES.trec"
).open(encoding="utf-8-sig") as f:
    for line in f:
        if not line.strip():
            continue
        qid, _, page, grade = line.split()
        qrels[qid][page] = int(grade)

# Un seul enregistrement par question et chunk,
# même si plusieurs méthodes retrouvent ce chunk.
candidates = {}

for result in rankings:
    qid = result["question_id"]
    method = result["method"]

    if qid not in TARGETS or method not in METHODS:
        continue

    if result["rank"] > TOP_K:
        continue

    cid = result["chunk_id"]
    key = (qid, cid)

    if key not in candidates:
        chunk = chunks[cid]
        pages = mapping[cid]

        candidates[key] = {
            "question_id": qid,
            "question": questions[qid]["question"],
            "chunk_id": cid,
            "filename": chunk["filename"],
            "page_ids": " | ".join(pages),
            "silver_grades": " | ".join(
                str(qrels[qid].get(p, "non_jugee"))
                for p in pages
            ),
            "bm25_rank": "",
            "dense_rank": "",
            "hybrid_rrf_rank": "",
            "text": chunk["text"],
            "human_status": "",
            "human_grade": "",
            "notes": "",
        }

    candidates[key][f"{method}_rank"] = result["rank"]

output = ROOT / "data/evaluation/audit/candidates_3_questions.csv"
output.parent.mkdir(parents=True, exist_ok=True)

rows = sorted(
    candidates.values(),
    key=lambda r: (
        r["question_id"],
        min(
            int(r[f"{m}_rank"])
            for m in METHODS
            if r[f"{m}_rank"] != ""
        ),
        r["chunk_id"],
    ),
)

with output.open(
    "w", encoding="utf-8-sig", newline=""
) as f:
    writer = csv.DictWriter(
        f, fieldnames=list(rows[0].keys())
    )
    writer.writeheader()
    writer.writerows(rows)

print("Questions auditées :", len(TARGETS))
print("Passages candidats uniques :", len(rows))
print("Fichier :", output)
