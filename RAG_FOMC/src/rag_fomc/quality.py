"""Audit des extractions sur les PDF originaux, sans prétendre valider la pertinence."""
from collections import Counter, defaultdict
from pathlib import Path

from .common import atomic_text, read_jsonl, sha256, write_json
from .ingestion import load_manifest
from .pdf_layout import page_lines


def audit_extraction(root, config):
    import pymupdf
    root = Path(root)
    paragraphs = read_jsonl(root / "data/processed/paragraphs.jsonl")
    by_doc = defaultdict(list)
    for p in paragraphs:
        by_doc[p["doc_id"]].append(p)
    records, failures = [], []
    samples = ["# Extraits pour revue humaine\n", "Échantillons automatiques ; ils ne remplacent pas la lecture des originaux.\n"]
    for row in load_manifest(root):
        if row["status"] != "obtained":
            continue
        doc = by_doc[row["doc_id"]]
        if not doc:
            failures.append({"doc_id": row["doc_id"], "reason": "no_paragraphs"})
            continue
        page_text = defaultdict(list)
        for p in doc:
            page_text[p["page"]].extend(p["text"].split())
        page_count = None
        if row["path"].suffix.lower() == ".pdf":
            with pymupdf.open(row["path"]) as pdf:
                page_count = len(pdf)
                for number, page in enumerate(pdf, 1):
                    source = Counter(" ".join(r["text"] for r in page_lines(page, config.pdf_drop_lines)).split())
                    if source != Counter(page_text[number]):
                        failures.append({"doc_id": row["doc_id"], "page": number, "reason": "content_mismatch"})
        combined = " ".join(p["text"] for p in doc)
        records.append({"doc_id": row["doc_id"], "pages": page_count, "paragraphs": len(doc),
            "sections": list(dict.fromkeys(p["section"] for p in doc)),
            "replacement_characters": combined.count("\ufffd"),
            "has_negation": " not " in combined.lower(),
            "has_fraction": any(c in combined for c in "¼½¾⅛⅜⅝⅞"),
            "source_sha256": row["actual_sha256"]})
        samples.append(f"\n## {row['doc_id']}\n\nSource : {row['source_url']}\n")
        for label, position in (("Début", 0), ("Milieu", len(doc) // 2), ("Fin", len(doc) - 1)):
            p = doc[position]
            samples.append(f"\n### {label} — page physique {p['page']} — {p['paragraph_id']}\n\n{p['text']}\n")
    report = {"documents": len(records), "pages": sum(r["pages"] or 0 for r in records),
        "paragraphs": len(paragraphs), "content_conservation_failures": failures,
        "replacement_characters": sum(r["replacement_characters"] for r in records),
        "paragraphs_sha256": sha256(root / "data/processed/paragraphs.jsonl"), "per_document": records,
        "interpretation": "Comparaison multiensembles de tokens par page, après retrait explicite des en-têtes. Ne prouve pas l'ordre sémantique ni l'exactitude des tableaux."}
    write_json(root / "data/processed/quality_report.json", report)
    atomic_text(root / "data/processed/review_samples.md", "\n".join(samples))
    if failures:
        raise ValueError("Audit : perte ou duplication de contenu détectée ; consulter quality_report.json")
    return report
