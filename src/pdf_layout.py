"""Extraction des PDF FOMC : ordre de lecture, paragraphes et césures auditées.

Nécessite : pip install wordfreq
Ne supprime jamais un trait d'union sans continuité géométrique et indice lexical.
"""
from __future__ import annotations

from functools import lru_cache
import re
import statistics
from common import normalize_text

MONTHS = r"January|February|March|April|May|June|July|August|September|October|November|December"
HEADINGS = re.compile(
    r"^(?:Developments in Financial Markets|Staff Review of|Staff Economic Outlook|"
    r"Participants[’'] Views|Committee Policy Actions?|Notation Vote|Discussion of|"
    r"Considerations for|Review of Monetary Policy|Attendance|PRESENT:|"
    r"AUTHORIZATION FOR|FOREIGN CURRENCY DIRECTIVE)", re.I,
)
END_FRAGMENT = re.compile(r"([A-Za-z]{1,})-$")
START_FRAGMENT = re.compile(r"^([A-Za-z]{1,})\b")

# Priorité aux exceptions explicites pour les termes économiques composés.
COMPOUNDS = {
    "short-term", "long-term", "near-term", "medium-term", "long-run",
    "short-run", "year-over-year", "month-over-month", "quarter-over-quarter",
    "well-anchored", "non-financial", "non-bank", "market-based",
    "data-dependent", "inter-meeting", "investment-grade", "supply-side",
    "demand-side", "policy-related", "risk-taking", "balance-sheet",
    "federal-funds", "post-pandemic", "pre-pandemic", "cost-push",
}

# Cas observés, dont la fusion ne dépend pas du score du dictionnaire.
CONFIRMED = {
    "inflation", "increased", "increase", "increases", "economic", "employment",
    "unemployment", "committee", "participants", "participant", "federal",
    "securities", "continued", "balance", "financial", "reserve", "remained",
    "expected", "expectations", "conditions", "development", "developments",
    "demand", "holdings", "necessary", "currency", "appropriate",
    "activity", "pandemic", "elevated", "settlement", "system",
    "monetary", "purchases", "uncertainty", "videoconference", "delivery",
    "section", "including", "market", "period", "percent", "policy",
    "members", "president", "selected", "indicated", "discretion",
    "paragraph", "instruction", "meeting", "arrangements", "forward",
    "mature", "alternate", "disregarding", "manager", "treasury", "although",
    "recent",
    "households",
    "accommodative",
    "intermeeting",
    "repurchase",
    "however",
    "accommodation",
    "below",
    "concurred",
    "counterparty",
    "reflecting",
    "remain",
    "tightening",
    "extent",
    "toward",
    "bottlenecks",
    "imports",
    "robust",
    "reserves",
    "delinquency",
    "banking",
    "framework",
    "borrowing",
    "improved",
}


# Fusions confirmées sur les pages du PDF FOMC du 27 janvier 2021.
# Conserver les fragments : la décision reste spécifique à la coupure observée.
CONFIRMED_SPLITS = {
    ("authoriza", "tions"): "authorizations",
    ("trans", "actions"): "transactions",
    ("para", "graphs"): "paragraphs",
}


@lru_cache(maxsize=20000)
def lexical_decision(left: str, right: str) -> str:
    """Retourne 'join', 'compound' ou 'uncertain'."""
    joined = (left + right).lower()
    compound = (left + "-" + right).lower()
    if compound in COMPOUNDS:
        return "compound"
    if (left.lower(), right.lower()) in CONFIRMED_SPLITS:
        return "join"
    if joined in CONFIRMED:
        return "join"
    try:
        from wordfreq import zipf_frequency
    except ImportError as exc:
        raise ImportError(
            "Installer la dépendance lexicale : python -m pip install wordfreq"
        ) from exc

    joined_score = zipf_frequency(joined, "en")
    compound_score = zipf_frequency(compound, "en")
    # Critères volontairement prudents : vocabulaire reconnu et préférence nette.
    if joined_score >= 3.0 and joined_score >= compound_score + 0.6:
        return "join"
    if compound_score >= 3.0 and compound_score >= joined_score + 0.6:
        return "compound"
    return "uncertain"


def continuation(a, b):
    """Continuité géométrique des lignes, sans traverser colonne ou bloc."""
    if not all(k in a and k in b for k in ("bbox", "block")):
        return True  # Pour les petits tests avec seulement un champ text.
    if a["block"] != b["block"]:
        return False
    ay = a["bbox"][1]
    by = b["bbox"][1]
    line_height = max(1.0, a["bbox"][3] - a["bbox"][1])
    if not (0 < by - ay <= max(30.0, 2.2 * line_height)):
        return False
    # Les débuts peuvent être indentés ; rejeter les sauts horizontaux majeurs.
    if abs(a["bbox"][0] - b["bbox"][0]) > 85:
        return False
    return True


def join_pdf_lines(lines, audit=None):
    """Reconstitue un paragraphe ; journalise les césures non résolues."""
    if not lines:
        return ""
    result = lines[0]["text"]
    for previous, row in zip(lines, lines[1:]):
        next_text = row["text"]
        end = END_FRAGMENT.search(result)
        begin = START_FRAGMENT.match(next_text)
        if end and begin and continuation(previous, row):
            left, right = end.group(1), begin.group(1)
            action = lexical_decision(left, right)
            if audit is not None:
                audit[action] = audit.get(action, 0) + 1
            if action == "join":
                # Conserver exactement la casse des fragments PDF.
                result = result[:end.start()] + left + right + next_text[begin.end():]
                continue
            if action == "compound":
                result += next_text
                continue
            # Incertain : trait d'union et séparation conservés.
        result += " " + next_text
    return normalize_text(result)


def running_header(text, y_end):
    if re.fullmatch(r"[_\s]+", text):
        return True
    if y_end > 56:
        return False
    clean = text.strip("_ ")
    return bool(
        re.fullmatch(r"\d+|Page\s+\d+", clean)
        or re.match(r"(?:Minutes of the (?:Meeting|Federal Open Market Committee)|Page\s+\d+)", clean)
        or re.match(rf"(?:\d+\s+)?(?:{MONTHS})\s+\d", clean)
    )


def page_lines(page, drop_lines=()):
    drops = {normalize_text(s) for s in drop_lines}
    rows = []
    for block_id, block in enumerate(page.get_text("dict", sort=False)["blocks"]):
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            if not line["spans"]:
                continue
            text = normalize_text("".join(s["text"] for s in line["spans"]))
            if not text or text in drops or running_header(text, line["bbox"][3]):
                continue
            total = sum(len(s["text"]) for s in line["spans"])
            bold = sum(len(s["text"]) for s in line["spans"] if s["flags"] & 16)
            rows.append({
                "text": text, "bbox": line["bbox"], "block": block_id,
                "baseline": line["spans"][0]["origin"][1],
                "size": max(s["size"] for s in line["spans"]),
                "bold": bold / max(1, total),
            })
    return rows


def reading_order(lines, width):
    middle = width / 2
    left = [r for r in lines if r["bbox"][0] < middle - 80 and r["bbox"][2] <= middle + 8]
    right = [r for r in lines if r["bbox"][0] >= middle + 8 and r["bbox"][2] - r["bbox"][0] > 80]
    two_columns = len(left) >= 6 and len(right) >= 6
    if not two_columns:
        return sorted(lines, key=lambda r: (round(r.get("baseline", r["bbox"][1]), 1), r["bbox"][0])), False
    spanning = sorted(
        [r for r in lines if r["bbox"][0] < middle and r["bbox"][2] > middle + 8],
        key=lambda r: r["bbox"][1],
    )
    ordinary = [r for r in lines if r not in spanning]
    ordered = []
    previous = -float("inf")
    for heading in spanning + [None]:
        limit = heading["bbox"][1] if heading else float("inf")
        band = [r for r in ordinary if previous <= r["bbox"][1] < limit]
        for side in (0, 1):
            ordered.extend(sorted(
                [r for r in band if int(r["bbox"][0] >= middle) == side],
                key=lambda r: (round(r.get("baseline", r["bbox"][1]), 1), r["bbox"][0]),
            ))
        if heading:
            ordered.append(heading)
            previous = limit
    return ordered, True


def paragraph_groups(lines, width, two_columns, audit=None):
    """Regroupe les lignes en conservant les frontières de colonnes et titres."""
    if not lines:
        return
    side = lambda r: int(two_columns and r["bbox"][0] >= width / 2)
    gaps = [b["bbox"][1] - a["bbox"][1] for a, b in zip(lines, lines[1:])
            if side(a) == side(b) and 5 < b["bbox"][1] - a["bbox"][1] < 30]
    baseline = statistics.median_low(gaps) if gaps else 14.0
    current, current_heading = [], False
    for row in lines:
        text = row["text"]
        prominent = row.get("bold", 0) > .65 or row["size"] >= 12 or (text.isupper() and len(text) < 120)
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
            boundary = (
                heading != current_heading or side(previous) != side(row)
                or vertical < -2 or vertical > baseline * 1.25
                or abs(row["size"] - previous["size"]) > 1.2
                or abs(row["bbox"][0] - previous["bbox"][0]) > 40
            )
            # Une coupure réelle confirmée ne doit pas former une frontière artificielle.
            left = END_FRAGMENT.search(previous["text"])
            right = START_FRAGMENT.match(text)
            if (boundary and not heading and not current_heading and left and right
                    and side(previous) == side(row) and continuation(previous, row)
                    and lexical_decision(left.group(1), right.group(1)) == "join"):
                boundary = False
        if boundary:
            yield current_heading, join_pdf_lines(current, audit)
            current = []
        current_heading = heading
        current.append(row)
    if current:
        yield current_heading, join_pdf_lines(current, audit)


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
                yield section_id, section, page_number, text, False


def inspect_pdf(path):
    """Diagnostique l'extraction ; ne prétend pas valider la pertinence du texte."""
    import pymupdf
    pages = []
    with pymupdf.open(path) as document:
        for number, page in enumerate(document, 1):
            lines = page_lines(page)
            ordered, two_columns = reading_order(lines, page.rect.width)
            audit = {}
            list(paragraph_groups(ordered, page.rect.width, two_columns, audit))
            text = " ".join(r["text"] for r in lines)
            pages.append({
                "page": number, "two_columns": two_columns,
                "characters": len(text), "replacement_characters": text.count("\ufffd"),
                "line_end_hyphens": sum(bool(END_FRAGMENT.search(r["text"])) for r in lines),
                "hyphenation_decisions": audit,
            })
    return pages
