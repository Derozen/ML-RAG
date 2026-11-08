"""Import local seulement : aucun téléchargement de corpus implicite."""
from __future__ import annotations

import csv
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from .common import sha256, unique, write_json, write_jsonl
from .preprocessing import normalize_text

FIELDS = ["doc_id", "meeting_start", "meeting_end", "related_dates", "published_at",
          "html_url", "pdf_url", "local_path", "sha256", "status"]
STATUSES = {"obtained", "missing", "review", "duplicate"}


def load_manifest(root):
    root = Path(root).resolve()
    path = root / "data/manifest.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError(f"Colonnes attendues : {FIELDS}")
        rows = list(reader)
    if not rows:
        raise ValueError("Manifeste vide : ajouter les rapports reçus avant l'exécution")
    unique(rows, "doc_id")
    hashes, errors, counts = {}, [], Counter()
    for row in rows:
        doc_id = row["doc_id"]
        if row["status"] not in STATUSES:
            errors.append(f"{doc_id}: statut invalide")
        try:
            start, end = date.fromisoformat(row["meeting_start"]), date.fromisoformat(row["meeting_end"])
            if start > end or not 2020 <= end.year <= 2025:
                raise ValueError("date hors périmètre 2020–2025 ou début après fin")
            if doc_id != f"FOMC_{end.isoformat()}":
                raise ValueError("doc_id attendu : FOMC_YYYY-MM-DD")
            for value in filter(None, row["related_dates"].split(";")):
                date.fromisoformat(value)
            if row["published_at"]:
                date.fromisoformat(row["published_at"])
        except ValueError as exc:
            errors.append(f"{doc_id}: {exc}")
            continue
        if row["status"] != "obtained":
            continue
        counts[str(end.year)] += 1
        local = (root / row["local_path"]).resolve()
        if not local.is_relative_to(root / "data/raw") or not local.is_file():
            errors.append(f"{doc_id}: fichier absent ou extérieur à data/raw")
            continue
        if local.suffix.lower() not in {".html", ".htm", ".pdf", ".txt"}:
            errors.append(f"{doc_id}: format non pris en charge")
        actual = sha256(local)
        row["actual_sha256"] = actual
        if row["sha256"] and row["sha256"].lower() != actual:
            errors.append(f"{doc_id}: empreinte SHA256 différente")
        if actual in hashes:
            errors.append(f"{doc_id}: octets identiques à {hashes[actual]}, marquer le doublon")
        hashes[actual] = doc_id
        row["path"] = local
        url = row["pdf_url"] if local.suffix.lower() == ".pdf" else row["html_url"] or row["pdf_url"]
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"www.federalreserve.gov", "federalreserve.gov"}:
            errors.append(f"{doc_id}: URL officielle HTTPS nécessaire")
        row["source_url"] = url
    report = {"counts_by_year": {str(y): counts[str(y)] for y in range(2020, 2026)},
              "obtained": sum(counts.values()), "expected_to_reconcile": 56,
              "difference": sum(counts.values()) - 56,
              "status_counts": dict(Counter(r["status"] for r in rows)), "errors": errors,
              "note": "56 est une attente du guide, pas un nombre de documents vérifié."}
    write_json(root / "data/processed/inventory_report.json", report)
    if errors:
        raise ValueError("Manifeste invalide :\n" + "\n".join(errors))
    return rows


def extract_html(path, selector):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(Path(path).read_bytes(), "html.parser")
    body = soup.select_one(selector)
    if body is None:
        raise ValueError(f"{path}: sélecteur {selector!r} introuvable ; adapter html_selector")
    for node in body.select("script, style, nav, footer, header, .shareDL, .social-sharing"):
        node.decompose()
    section, section_number = "Introduction", 0
    for node in body.find_all(["h1", "h2", "h3", "h4", "p", "table"]):
        if node.find_parent(["table"]):
            continue
        text = normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name.startswith("h"):
            section, section_number = text, section_number + 1
        else:
            yield section_number, section, None, text, node.name == "table"


def extract_pdf(path, drop_lines):
    from .pdf_layout import extract_pdf_sections
    yield from extract_pdf_sections(path, drop_lines)


def extract(root, config):
    root = Path(root)
    rows = load_manifest(root)
    paragraphs, review = [], []
    for row in rows:
        if row["status"] != "obtained":
            continue
        path = row["path"]
        if path.suffix.lower() in {".html", ".htm"}:
            items = extract_html(path, config.html_selector)
        elif path.suffix.lower() == ".pdf":
            from .pdf_layout import inspect_pdf
            items = extract_pdf(path, config.pdf_drop_lines)
            review.append({"doc_id": row["doc_id"], "check": "Colonnes détectées ; titres et tableaux à relire",
                           "pages": inspect_pdf(path)})
        else:
            items = ((0, "Texte — section à vérifier", None, normalize_text(p), False)
                     for p in path.read_text(encoding="utf-8-sig").split("\n\n") if p.strip())
        before = len(paragraphs)
        for position, (section_id, section, page, text, table) in enumerate(items, 1):
            paragraphs.append({"paragraph_id": f"{row['doc_id']}_P{position:04d}",
                               "doc_id": row["doc_id"], "meeting_end": row["meeting_end"],
                               "section_id": section_id, "section": section, "position": position,
                               "page": page, "source_url": row["source_url"], "text": text,
                               "source_sha256": row["actual_sha256"], "needs_table_review": table})
        if len(paragraphs) == before:
            raise ValueError(f"{row['doc_id']}: aucun paragraphe extrait")
    if not paragraphs:
        raise ValueError("Aucun document au statut obtained")
    unique(paragraphs, "paragraph_id")
    write_jsonl(root / "data/processed/paragraphs.jsonl", paragraphs)
    write_json(root / "data/processed/extraction_report.json", {
        "paragraphs": len(paragraphs), "documents": len({p["doc_id"] for p in paragraphs}),
        "review": review, "manual_checks_required": ["Début, milieu, fin de chaque rapport pilote",
        "Une décision chiffrée et une négation", "Titres, dates, type Minutes et tableaux"]})
    return paragraphs
