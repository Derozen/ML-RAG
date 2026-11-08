"""Mesures appariées : passages pertinents, groupes de preuves et latence."""
from __future__ import annotations

import json
import importlib.metadata
import platform
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .common import read_jsonl, sha256, unique, write_csv, write_json, write_jsonl
from .preprocessing import normalize_text
from .retrieval import METHODS


def validate_questions(questions, chunks, annotated=False):
    if not questions:
        raise ValueError("Jeu de questions vide : fournir des questions vérifiées")
    unique(questions, "qid")
    by_id = {c["chunk_id"]: c for c in chunks}
    families = defaultdict(set)
    for q in questions:
        if not isinstance(q.get("question"), str) or not q["question"].strip():
            raise ValueError(f"{q['qid']}: question vide")
        if not annotated:
            continue
        if q.get("split") not in {"dev", "test"} or not q.get("type"):
            raise ValueError(f"{q['qid']}: type et split dev/test requis")
        if type(q.get("answerable")) is not bool or q.get("validated") is not True:
            raise ValueError(f"{q['qid']}: answerable booléen et validated=true requis après revue humaine")
        if not q.get("family_id"):
            raise ValueError(f"{q['qid']}: family_id requis pour grouper les reformulations")
        families[q["family_id"]].add(q["split"])
        evidence = q.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError(f"{q['qid']}: evidence doit être une liste")
        if q["answerable"] and (not evidence or not q.get("reference_answer")):
            raise ValueError(f"{q['qid']}: réponse de référence et preuves requises")
        if q["answerable"] and q["type"] == "comparative" and len(evidence) < 2:
            raise ValueError(f"{q['qid']}: au moins deux groupes de preuves pour une comparaison")
        if not q["answerable"]:
            if evidence or not q.get("absence_reason"):
                raise ValueError(f"{q['qid']}: absence_reason requis et evidence doit être vide")
        unique(evidence, "evidence_id")
        for e in evidence:
            accepted = e.get("chunk_ids", [])
            if not accepted or len(set(accepted)) != len(accepted):
                raise ValueError(f"{q['qid']}: IDs de preuves vides ou dupliqués")
            if not e.get("quote") or not e.get("doc_id"):
                raise ValueError(f"{q['qid']}: citation originale et document requis")
            variants = e.get("quotes_by_chunk", {})
            if not isinstance(variants, dict) or not set(variants).issubset(accepted):
                raise ValueError(f"{q['qid']}: quotes_by_chunk doit référencer des IDs acceptables")
            for chunk_id in accepted:
                if chunk_id not in by_id or by_id[chunk_id]["doc_id"] != e["doc_id"]:
                    raise ValueError(f"{q['qid']}: preuve inconnue ou document incohérent : {chunk_id}")
                quote = variants.get(chunk_id, e["quote"])
                if not isinstance(quote, str) or not quote.strip() or normalize_text(quote) not in normalize_text(by_id[chunk_id]["text"]):
                    raise ValueError(f"{q['qid']}: citation absente de {chunk_id} ; revoir le lien preuve/passage")
    if any(len(splits) > 1 for splits in families.values()):
        raise ValueError("Fuite dev/test : reformulations d'une famille dans plusieurs splits")


def retrieval_metrics(ranked_ids, evidence, k):
    if k <= 0:
        raise ValueError("k doit être positif")
    groups = [set(e["chunk_ids"]) for e in evidence]
    if not groups or any(not g for g in groups):
        raise ValueError("Preuves requises pour une question répondable")
    relevant = set.union(*groups)
    top = ranked_ids[:k]
    if len(top) != len(set(top)):
        raise ValueError("Classement contenant des doublons")
    found = set(top)
    first = next((rank for rank, cid in enumerate(top, 1) if cid in relevant), None)
    covered = sum(bool(g & found) for g in groups)
    return {"recall": len(found & relevant) / len(relevant), "mrr": 1 / first if first else 0.0,
            "evidence_coverage": covered / len(groups), "all_evidence": float(covered == len(groups))}


def compare(root, retriever, questions_path, split, output, repetitions=None):
    root, output = Path(root), Path(output)
    questions = read_jsonl(questions_path)
    validate_questions(questions, retriever.chunks, annotated=True)
    annotations_path = root / "evaluation/annotations.json"
    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
    if annotations.get("chunks_sha256") != retriever.metadata["chunks_sha256"]:
        raise ValueError("Annotations non liées au découpage courant : revoir les preuves puis actualiser annotations.json")
    if annotations.get("questions_sha256") != sha256(questions_path):
        raise ValueError("Questions modifiées ou empreinte absente : faire valider cette version puis actualiser questions_sha256 dans annotations.json")
    questions = [q for q in questions if q["split"] == split]
    if not questions:
        raise ValueError(f"Aucune question dans le split {split}")
    n = retriever.config.repetitions if repetitions is None else repetitions
    if n <= 0:
        raise ValueError("Nombre de répétitions invalide")
    k = retriever.config.top_k
    # Chargement du modèle et de l'index déjà terminé ; échauffement exclu.
    for method in METHODS:
        retriever.search(questions[0]["question"], method)
    rng = random.Random(retriever.config.seed)
    rankings, latency, metrics, unanswered, canonical = [], [], [], [], {}
    for repeat in range(n):
        schedule = [(q, method) for q in questions for method in METHODS]
        rng.shuffle(schedule)
        for q, method in schedule:
            results, seconds, diagnostics = retriever.search(q["question"], method)
            ids = [r["chunk_id"] for r in results]
            key = (q["qid"], method)
            latency.append({"qid": q["qid"], "method": method, "repeat": repeat + 1,
                            "seconds": seconds, **diagnostics})
            if repeat:
                if ids != canonical[key]:
                    raise ValueError("Classement instable entre répétitions ; inspecter le calcul")
                continue
            canonical[key] = ids
            rankings.extend({"qid": q["qid"], **r} for r in results)
            if q["answerable"]:
                metrics.append({"qid": q["qid"], "method": method, "type": q["type"],
                    "split": split, "k": k, **retrieval_metrics(ids, q["evidence"], k)})
            else:
                unanswered.append({"qid": q["qid"], "question": q["question"], "method": method,
                    "absence_reason": q["absence_reason"], "top_results": results[:3],
                    "note": "Candidats à examiner ; aucun seuil de rejet entraîné."})
    rankings.sort(key=lambda r: (r["qid"], r["method"], r["rank"]))
    metrics.sort(key=lambda r: (r["qid"], r["method"]))
    summary = []
    for method in METHODS:
        types = ["ALL"] + sorted({q["type"] for q in questions})
        for kind in types:
            selected = [m for m in metrics if m["method"] == method and (kind == "ALL" or m["type"] == kind)]
            qids = {q["qid"] for q in questions if kind == "ALL" or q["type"] == kind}
            times = [t["seconds"] for t in latency if t["method"] == method and t["qid"] in qids]
            summary.append({"method": method, "type": kind, "k": k, "answerable_questions": len(selected),
                **{name: float(np.mean([m[name] for m in selected])) if selected else None
                   for name in ("recall", "mrr", "evidence_coverage", "all_evidence")},
                "latency_samples": len(times), "latency_median_seconds": float(np.median(times)),
                "latency_p95_seconds": float(np.percentile(times, 95))})
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "rankings.csv", rankings,
        ["qid", "method", "rank", "chunk_id", "doc_id", "meeting_end", "section", "score", "source_url"])
    write_jsonl(output / "rankings.jsonl", rankings)
    write_csv(output / "metrics_per_question.csv", metrics,
        ["qid", "method", "type", "split", "k", "recall", "mrr", "evidence_coverage", "all_evidence"])
    write_csv(output / "latencies.csv", latency,
        ["qid", "method", "repeat", "seconds", "no_lexical_match", "lexical_scores_all_equal"])
    write_jsonl(output / "unanswerable_review.jsonl", unanswered)
    write_csv(output / "summary.csv", summary, list(summary[0]))
    from .comparison import paired_intervals, review_cases
    intervals = paired_intervals(metrics, questions, retriever.config.seed)
    write_csv(output / "paired_comparisons.csv", intervals, ["method_a", "method_b", "metric",
              "delta_b_minus_a", "ci95_low", "ci95_high", "families", "samples"])
    write_jsonl(output / "review_cases.jsonl", review_cases(questions, rankings, metrics))
    runtime_versions = {}
    for package in ("numpy", "rank-bm25", "sentence-transformers", "transformers", "torch"):
        try:
            runtime_versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            runtime_versions[package] = None
    write_json(output / "run.json", {"created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": split, "questions_sha256": sha256(questions_path), "annotations_sha256": sha256(annotations_path),
        "index_metadata_sha256": sha256(root / "indexes/metadata.json"),
        "chunks_sha256": retriever.metadata["chunks_sha256"], "config": retriever.config.to_dict(),
        "model_revision": retriever.metadata["model_revision"], "repetitions": n,
        "platform": platform.platform(), "processor": platform.processor(),
        "python": platform.python_version(), "runtime_versions": runtime_versions,
        "timing": "Chargement et échauffement exclus ; encodage de question inclus. RRF recalcule les deux branches.",
        "aggregation": "Macro-moyenne par question répondable. Latence sur toutes les questions du split.",
        "intervals": "Bootstrap exploratoire à 95%, 1000 tirages par famille, différences B-A ; pas de correction des comparaisons multiples.",
        "warning": "Ne pas régler les paramètres sur le test. Aucun résultat ne démontre la qualité sans annotations validées."})
    return summary
