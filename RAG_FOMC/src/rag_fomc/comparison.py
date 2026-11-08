"""Comparaisons appariées et sélection transparente de cas à relire."""
from collections import defaultdict

import numpy as np

from .retrieval import METHODS


def paired_intervals(metrics, questions, seed, samples=1000):
    """Bootstrap par famille de reformulations, différence B moins A."""
    lookup = {(m["qid"], m["method"]): m for m in metrics}
    families = defaultdict(list)
    for q in questions:
        if q["answerable"]:
            families[q["family_id"]].append(q["qid"])
    groups = [families[f] for f in sorted(families)]
    if not groups:
        return []
    rng = np.random.default_rng(seed)
    selections = rng.integers(0, len(groups), size=(samples, len(groups)))
    rows = []
    for i, a in enumerate(METHODS):
        for b in METHODS[i + 1:]:
            for metric in ("recall", "mrr", "evidence_coverage", "all_evidence"):
                grouped = [[lookup[(qid, b)][metric] - lookup[(qid, a)][metric] for qid in g] for g in groups]
                observed = float(np.mean([d for group in grouped for d in group]))
                draws = [float(np.mean([d for j in selection for d in grouped[j]])) for selection in selections]
                rows.append({"method_a": a, "method_b": b, "metric": metric,
                    "delta_b_minus_a": observed, "ci95_low": float(np.percentile(draws, 2.5)),
                    "ci95_high": float(np.percentile(draws, 97.5)), "families": len(groups), "samples": samples})
    return rows


def review_cases(questions, rankings, metrics):
    """Un exemple par catégorie, sans inventer de cause aux erreurs."""
    by_question = defaultdict(lambda: defaultdict(list))
    for r in rankings:
        by_question[r["qid"]][r["method"]].append(r)
    lookup = {(m["qid"], m["method"]): m for m in metrics}
    selected, used = [], set()
    for q in sorted(questions, key=lambda q: q["qid"]):
        if not q["answerable"]:
            continue
        lists = by_question[q["qid"]]
        scores = [lookup[(q["qid"], m)]["all_evidence"] for m in METHODS]
        categories = []
        if all(s == 1 for s in scores):
            categories.append("success_all_evidence")
        if all(s == 0 for s in scores):
            categories.append("incomplete_all_methods")
        if len({tuple(r["chunk_id"] for r in lists[m]) for m in METHODS}) > 1:
            categories.append("different_rankings")
        for category in categories:
            if category in used:
                continue
            used.add(category)
            selected.append({"category": category, "qid": q["qid"], "question": q["question"],
                "reference_answer": q["reference_answer"], "evidence": q["evidence"],
                "methods": {m: {"metrics": lookup[(q["qid"], m)], "top5": lists[m][:5],
                    "evidence_ranks": [{"evidence_id": e["evidence_id"], "ranks": [r["rank"] for r in lists[m]
                                        if r["chunk_id"] in e["chunk_ids"]]} for e in q["evidence"]]}
                    for m in METHODS}, "human_analysis": "À compléter après consultation des originaux."})
    return selected
