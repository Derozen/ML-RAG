"""Import reproductible des PDF et sources utiles du dépôt fourni par l'utilisateur."""
from __future__ import annotations

import hashlib
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath

from .common import atomic_text, sha256, write_csv, write_json
from .ingestion import FIELDS
from .preprocessing import normalize_text

MONTHS = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"), 1)}
MONTH_PATTERN = "|".join(MONTHS)
DATE_RANGE = re.compile(rf"(?P<month>{MONTH_PATTERN})\s+(?P<start>\d{{1,2}})"
    rf"(?:\s*[-–—]\s*(?:(?P<end_month>{MONTH_PATTERN})\s+)?(?P<end>\d{{1,2}}))?"
    r",\s*(?P<year>\d{4})")


def meeting_dates(title, first_page, expected_end):
    """Les dates viennent du document ; le nom du fichier sert au contrôle croisé."""
    for text in (title or "", normalize_text(first_page)):
        for match in DATE_RANGE.finditer(text):
            fields = match.groupdict()
            year = int(fields["year"])
            start_month = MONTHS[fields["month"]]
            end_month = MONTHS[fields["end_month"] or fields["month"]]
            end = date(year, end_month, int(fields["end"] or fields["start"]))
            start = date(year - int(start_month > end_month), start_month, int(fields["start"]))
            if end == expected_end and start <= end:
                return start, end
    raise ValueError(f"Dates non établies dans le titre/première page : {expected_end}")


def write_unchanged_or_new(path, content):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Fichier existant différent, conservé : {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def import_archive(archive, root):
    import pymupdf
    root, archive = Path(root).resolve(), Path(archive).resolve()
    if not zipfile.is_zipfile(archive):
        raise ValueError("Archive ZIP attendue")
    inventory, manifest, source_files = [], [], []
    with zipfile.ZipFile(archive) as bundle:
        if sum(i.file_size for i in bundle.infolist()) > 1024 * 1024 * 1024:
            raise ValueError("Archive décompressée supérieure à 1 Go")
        for info in bundle.infolist():
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or ".." in relative.parts or "\\" in info.filename or any(":" in p for p in relative.parts):
                raise ValueError(f"Chemin dangereux dans l'archive : {info.filename}")
        # Aucune extraction générale : .env, bytecode et réglages locaux ne sont pas importés.
        for info in sorted(bundle.infolist(), key=lambda i: i.filename):
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or ".." in relative.parts or "\\" in info.filename:
                raise ValueError(f"Chemin dangereux dans l'archive : {info.filename}")
            if info.is_dir():
                continue
            if info.file_size > 50 * 1024 * 1024:
                raise ValueError(f"Fichier individuel trop volumineux : {info.filename}")
            name = relative.name
            minutes_match = re.fullmatch(r"fomcminutes(\d{8})\.pdf", name)
            statement_match = re.fullmatch(r"monetary(\d{8})a1\.pdf", name)
            match = minutes_match or statement_match
            if match:
                content = bundle.read(info)
                if not content.startswith(b"%PDF-"):
                    raise ValueError(f"PDF invalide : {name}")
                kind = "minutes" if minutes_match else "statements"
                expected = date.fromisoformat(f"{match[1][:4]}-{match[1][4:6]}-{match[1][6:]}")
                local = Path("data/raw") / kind / name
                with pymupdf.open(stream=content, filetype="pdf") as document:
                    title = document.metadata.get("title", "")
                    first_page = document[0].get_text()
                    pages = len(document)
                    if kind == "minutes":
                        start, end = meeting_dates(title, first_page, expected)
                        if "Minutes" not in (title + first_page) or "Committee" not in (title + first_page):
                            raise ValueError(f"Type Minutes non confirmé dans {name}")
                    else:
                        start, end = None, expected
                selected = kind == "minutes" and 2020 <= end.year <= 2025
                reason = "included_minutes_2020_2025" if selected else (
                    "excluded_document_type_statement" if kind == "statements" else "excluded_meeting_year")
                write_unchanged_or_new(root / local, content)
                digest = hashlib.sha256(content).hexdigest()
                inventory.append({"archive_entry": info.filename, "local_path": local.as_posix(),
                    "document_type": kind, "meeting_end": end.isoformat(), "pages": pages,
                    "included": selected, "reason": reason, "sha256": digest, "pdf_title": title})
                if selected:
                    iso = end.isoformat()
                    manifest.append({"doc_id": f"FOMC_{iso}", "meeting_start": start.isoformat(),
                        "meeting_end": iso, "related_dates": "", "published_at": "",
                        "html_url": f"https://www.federalreserve.gov/monetarypolicy/fomcminutes{match[1]}.htm",
                        "pdf_url": f"https://www.federalreserve.gov/monetarypolicy/files/{name}",
                        "local_path": local.as_posix(), "sha256": digest, "status": "obtained"})
            elif name.endswith(".py") and "__pycache__" not in relative.parts:
                destination = root / "references" / Path(*relative.parts)
                if not destination.resolve().is_relative_to(root / "references"):
                    raise ValueError("Destination des sources hors du dossier references")
                write_unchanged_or_new(destination, bundle.read(info))
                source_files.append(str(destination.relative_to(root).as_posix()))
    if not manifest:
        raise ValueError("Aucune Minutes dans le périmètre 2020–2025")
    manifest.sort(key=lambda row: row["doc_id"])
    path = root / "data/manifest.csv"
    # Le manifeste courant est conservé dans une sauvegarde avant une première migration.
    if path.exists() and len(path.read_text(encoding="utf-8-sig").splitlines()) > 1:
        backup = root / "data/import_backups" / f"manifest-{sha256(path)[:12]}.csv"
        write_unchanged_or_new(backup, path.read_bytes())
    write_csv(path, manifest, FIELDS)
    write_csv(root / "data/archive_inventory.csv", inventory, ["archive_entry", "local_path", "document_type",
              "meeting_end", "pages", "included", "reason", "sha256", "pdf_title"])
    report = {"archive_name": archive.name, "archive_sha256": sha256(archive), "pdf_count": len(inventory),
        "document_types": dict(Counter(r["document_type"] for r in inventory)),
        "included_minutes": len(manifest), "included_by_year": dict(Counter(r["meeting_end"][:4] for r in manifest)),
        "excluded_by_reason": dict(Counter(r["reason"] for r in inventory if not r["included"])),
        "missing_years": [year for year in range(2020, 2026) if str(year) not in {r["meeting_end"][:4] for r in manifest}],
        "reference_sources": source_files, "excluded_local_configuration": [".env", "__pycache__", ".vscode"],
        "dates": "Dates de réunion confirmées par titre/première page ; publication non déduite des métadonnées PDF.",
        "urls": "URLs officielles construites depuis les noms de fichiers ; import sans téléchargement de rapports supplémentaires."}
    write_json(root / "data/import_report.json", report)
    return report
