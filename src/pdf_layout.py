"""Lecture des Minutes à une/deux colonnes, avec titres et pages physiques."""
from __future__ import annotations

import re
import statistics

from common import normalize_text

MONTHS = r"January|February|March|April|May|June|July|August|September|October|November|December"
HEADINGS = re.compile(r"^(?:Developments in Financial Markets|Staff Review of|Staff Economic Outlook|"
    r"Participants[’'] Views|Committee Policy Actions?|Notation Vote|Discussion of|Considerations for|"
    r"Review of Monetary Policy|Attendance|PRESENT:|AUTHORIZATION FOR|FOREIGN CURRENCY DIRECTIVE)", re.I)


def running_header(text, y_end):
    """Règles limitées à la marge supérieure, vérifiées sur les originaux fournis."""
    if re.fullmatch(r"[_\s]+", text):
        return True
    if y_end > 56:
        return False
    clean = text.strip("_ ")
    return bool(re.fullmatch(r"\d+|Page\s+\d+", clean) or
                re.match(r"(?:Minutes of the (?:Meeting|Federal Open Market Committee)|Page\s+\d+)", clean) or
                re.match(rf"(?:\d+\s+)?(?:{MONTHS})\s+\d", clean))


def page_lines(page, drop_lines=()):
    drops = {normalize_text(x) for x in drop_lines}
    rows = []
    for block_id, block in enumerate(page.get_text("dict", sort=False)["blocks"]):
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"])
            text = normalize_text(text)
            if not text or text in drops or running_header(text, line["bbox"][3]):
                continue
            if re.fullmatch(r"[_\s]+", text):
                continue
            rows.append({"text": text, "bbox": line["bbox"], "block": block_id,
                         "baseline": line["spans"][0]["origin"][1],
                         "size": max(span["size"] for span in line["spans"]),
                         "bold": sum(len(s["text"]) for s in line["spans"] if s["flags"] & 16) /
                                 max(1, sum(len(s["text"]) for s in line["spans"]))})
    return rows


def reading_order(lines, width):
    """Les pages à deux colonnes se lisent colonne gauche puis droite, pas ligne par ligne."""
    middle = width / 2
    left = [r for r in lines if r["bbox"][0] < middle - 80 and r["bbox"][2] <= middle + 8]
    right = [r for r in lines if r["bbox"][0] >= middle + 8 and r["bbox"][2] - r["bbox"][0] > 80]
    two_columns = len(left) >= 6 and len(right) >= 6
    if not two_columns:
        return sorted(lines, key=lambda r: (round(r.get("baseline",r["bbox"][1]), 1), r["bbox"][0])), False
    # Les titres traversant la gouttière séparent des bandes, sans mélanger les colonnes.
    spanning = sorted([r for r in lines if r["bbox"][0] < middle and r["bbox"][2] > middle + 8],
                      key=lambda r: r["bbox"][1])
    ordinary = [r for r in lines if r not in spanning]
    ordered = []
    previous = -float("inf")
    for heading in spanning + [None]:
        limit = heading["bbox"][1] if heading else float("inf")
        band = [r for r in ordinary if previous <= r["bbox"][1] < limit]
        for side in (0, 1):
            ordered.extend(sorted([r for r in band if int(r["bbox"][0] >= middle) == side],
                                  key=lambda r: (round(r.get("baseline",r["bbox"][1]),1), r["bbox"][0])))
        if heading:
            ordered.append(heading)
            previous = limit
    return ordered, True


def paragraph_groups(lines, width, two_columns):
    """Reconstitue les paragraphes même quand le PDF encode un bloc par ligne."""
    if not lines:
        return
    side = lambda row: int(two_columns and row["bbox"][0] >= width / 2)
    gaps = [b["bbox"][1] - a["bbox"][1] for a, b in zip(lines, lines[1:])
            if side(a) == side(b) and 5 < b["bbox"][1] - a["bbox"][1] < 30]
    baseline = statistics.median_low(gaps) if gaps else 14.0
    current, current_heading = [], False
    for row in lines:
        text = row["text"]
        prominent = row.get("bold", 0) > 0.65 or row["size"] >= 12 or (text.isupper() and len(text) < 120)
        heading = len(text) < 180 and bool(HEADINGS.match(text))
        heading = heading and (prominent or text.rstrip(":") in {"PRESENT", "Attendance", "Notation Vote"})
        if current and current_heading and prominent and not text.endswith("."):
            previous = current[-1]
            if side(previous) == side(row) and 0 <= row["bbox"][1] - previous["bbox"][1] < baseline * 1.8:
                heading = True
        boundary = False
        if current:
            previous = current[-1]
            vertical = row["bbox"][1] - previous["bbox"][1]
            boundary = (heading != current_heading or side(previous) != side(row) or vertical < -2 or
                        vertical > baseline * 1.25 or abs(row["size"] - previous["size"]) > 1.2 or
                        abs(row["bbox"][0] - previous["bbox"][0]) > 40)
        if boundary:
            yield current_heading, normalize_text(" ".join(r["text"] for r in current))
            current = []
        current_heading = heading
        current.append(row)
    if current:
        yield current_heading, normalize_text(" ".join(r["text"] for r in current))


def extract_pdf_sections(path, drop_lines=()):
    import pymupdf
    section_id, section = 0, "Document information and opening"
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, 1):
            raw_lines = page_lines(page, drop_lines)
            if not raw_lines:
                raise ValueError(f"{path}: page {page_number} vide ; HTML ou OCR vérifié requis")
            ordered, two_columns = reading_order(raw_lines, page.rect.width)
            for heading, text in paragraph_groups(ordered, page.rect.width, two_columns):
                if heading:
                    section_id += 1
                    section = text
                # Les titres restent dans le texte : aucune ligne de contenu n'est perdue.
                yield section_id, section, page_number, text, False


def inspect_pdf(path):
    """Contrôles observables ; ne constitue pas une validation humaine des tableaux."""
    import pymupdf
    pages = []
    with pymupdf.open(path) as document:
        for number, page in enumerate(document, 1):
            lines = page_lines(page)
            _, columns = reading_order(lines, page.rect.width)
            text = " ".join(r["text"] for r in lines)
            pages.append({"page": number, "two_columns": columns, "characters": len(text),
                "replacement_characters": text.count("\ufffd"),
                "line_end_hyphens": sum(bool(re.search(r"[A-Za-z]-$", r["text"])) for r in lines)})
    return pages
