"""Extraire les PDF FOMC et construire des chunks E5 avec provenance par page.

Les frontières de chunks respectent les mots, y compris les sous-tokens WordPiece.
Le chevauchement cible 60 tokens et peut varier légèrement pour cette raison.
"""

from collections import Counter, defaultdict
from datetime import date
from itertools import groupby
from types import SimpleNamespace
import re
import statistics

from common import ROOT, CONFIG, digest, write_json, write_jsonl, log, E5Tokenizer
from pdf_layout import extract_pdf_sections, page_lines

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def unique(rows, key):
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"Identifiants dupliqués : {key}")


def character_inventory(text):
    """Inventaire alphanumérique (ne valide pas l'ordre des caractères)."""
    return Counter(char for char in text.casefold() if char.isalnum())


def meeting_label(value):
    d = date.fromisoformat(value)
    return f"Meeting ending {MONTHS[d.month - 1]} {d.day}, {d.year} ({value})"


def split_inside_word(full, position):
    """Vrai si la frontière sépare deux caractères alphanumériques."""
    return (
        0 < position < len(full)
        and full[position - 1].isalnum()
        and full[position].isalnum()
    )


def safe_end(full, offsets, start, end):
    """Recule la fin vers une frontière de mot (sans créer de chunk vide)."""
    total = len(offsets)
    while end < total and end > start + 1 and split_inside_word(full, offsets[end - 1][1]):
        end -= 1
    if end < total and split_inside_word(full, offsets[end - 1][1]):
        raise ValueError("Impossible de terminer le chunk sur une frontière de mot")
    return end


def safe_overlap_start(full, offsets, current_start, previous_end, overlap):
    """Recule vers une frontière de mot sans revenir au début du chunk précédent."""
    candidate = max(current_start + 1, previous_end - overlap)
    while candidate > current_start + 1 and split_inside_word(full, offsets[candidate][0]):
        candidate -= 1
    if split_inside_word(full, offsets[candidate][0]):
        # Rare : aucun début valide après current_start. Ne pas découper dans un mot.
        raise ValueError("Impossible de démarrer le chunk sur une frontière de mot")
    return candidate


def count_page_characters(spans, char_start, char_end):
    """Comptabilise les caractères non blancs provenant de chaque page et paragraphe."""
    page_counts = Counter()
    paragraph_counts = {}
    for left, right, paragraph in spans:
        lo, hi = max(left, char_start), min(right, char_end)
        if lo >= hi:
            continue
        fragment = paragraph["text"][lo - left:hi - left]
        count = sum(not char.isspace() for char in fragment)
        if count:
            page_counts[paragraph["page"]] += count
            paragraph_counts[paragraph["paragraph_id"]] = count
    return page_counts, paragraph_counts


def chunk_paragraphs(paragraphs, tokenizer, config):
    unique(paragraphs, "paragraph_id")
    ordered = sorted(paragraphs, key=lambda p: (p["doc_id"], p["position"]))
    counts, chunks = Counter(), []

    for _, grouped in groupby(ordered, key=lambda p: (p["doc_id"], p["section_id"])):
        group = list(grouped)
        first = group[0]
        prefix = meeting_label(first["meeting_end"]) + " | " + first["section"] + "\n"
        overhead = len(tokenizer.encode(config.passage_prefix + prefix, add_special_tokens=True))
        budget = min(config.chunk_tokens, config.max_model_tokens - overhead - 4)
        if budget <= config.overlap_tokens:
            raise ValueError(f"Budget insuffisant : {first['doc_id']} / {first['section']}")

        full = ""
        spans = []
        for paragraph in group:
            if full:
                full += "\n\n"
            left = len(full)
            full += paragraph["text"]
            spans.append((left, len(full), paragraph))

        offsets = tokenizer(
            full, add_special_tokens=False, return_offsets_mapping=True,
            truncation=False, verbose=False,
        )["offset_mapping"]
        if not offsets:
            raise ValueError(f"Section vide : {first['doc_id']}")

        sentence_ends = {
            match.end() for match in re.finditer(r'[.!?](?:["’”])?(?=\s|$)|\n\n', full)
        }
        start, total, previous_end = 0, len(offsets), None
        while start < total:
            end = min(start + budget, total)
            if end < total:
                minimum = start + max(config.overlap_tokens + 1, budget // 2)
                candidates = [
                    j for j in range(minimum, end + 1)
                    if offsets[j - 1][1] in sentence_ends
                ]
                if candidates:
                    end = candidates[-1]

            end = safe_end(full, offsets, start, end)
            while True:
                char_start, char_end = offsets[start][0], offsets[end - 1][1]
                text = full[char_start:char_end]
                search_text = prefix + text
                model_count = len(tokenizer.encode(
                    config.passage_prefix + search_text, add_special_tokens=True,
                ))
                token_count = len(tokenizer.encode(text, add_special_tokens=False))
                if model_count <= config.max_model_tokens and token_count <= config.chunk_tokens:
                    break
                if end <= start + 1:
                    raise ValueError("Aucun chunk admissible dans le budget")
                end = safe_end(full, offsets, start, end - 1)

            if split_inside_word(full, char_start) or split_inside_word(full, char_end):
                raise ValueError(f"Frontière dans un mot : {first['doc_id']}")
            page_counts, paragraph_counts = count_page_characters(spans, char_start, char_end)
            if not page_counts:
                raise ValueError(f"Chunk sans provenance : {first['doc_id']}")
            sources = [p for _, _, p in spans if p["paragraph_id"] in paragraph_counts]
            pages = sorted(page_counts)
            total_chars = sum(page_counts.values())
            counts[first["doc_id"]] += 1
            chunk_id = f"{first['doc_id']}_C{counts[first['doc_id']]:04d}"
            chunks.append({
                "chunk_id": chunk_id, "doc_id": first["doc_id"],
                "meeting_end": first["meeting_end"], "section": first["section"],
                "section_id": first["section_id"],
                "paragraph_ids": [p["paragraph_id"] for p in sources],
                "page_start": min(pages), "page_end": max(pages), "pages": pages,
                "page_contributions": [
                    {"page": page, "characters": page_counts[page],
                     "ratio": page_counts[page] / total_chars}
                    for page in pages
                ],
                "paragraph_characters": paragraph_counts,
                "multipage": len(pages) > 1,
                "source_url": first["source_url"], "text": text,
                "search_text": search_text,
                "token_count": token_count, "model_token_count": model_count,
                "section_char_start": char_start, "section_char_end": char_end,
                "section_token_start": start, "section_token_end": end,
                "overlap_with_previous_tokens": (
                    max(0, previous_end - start) if previous_end is not None else 0
                ),
            })
            previous_end = end
            if end == total:
                break
            start = safe_overlap_start(full, offsets, start, end, config.overlap_tokens)

    unique(chunks, "chunk_id")
    if {c["doc_id"] for c in chunks} != {p["doc_id"] for p in paragraphs}:
        raise ValueError("Un document n'a produit aucun chunk")
    return chunks


def main():
    import pymupdf

    files = sorted((ROOT / "data/raw").rglob("*.pdf"))
    if len(files) != 93:
        raise ValueError(f"93 PDF attendus, {len(files)} présents")
    tokenizer = E5Tokenizer()
    config = SimpleNamespace(**CONFIG, passage_prefix="passage: ")
    paragraphs, manifest, failures = [], [], []
    page_count = 0

    for file in files:
        match = re.search(r"(20\d{6})", file.stem)
        if not match:
            raise ValueError(f"Date introuvable : {file.name}")
        value = match.group()
        when = f"{value[:4]}-{value[4:6]}-{value[6:]}"
        kind = "minutes" if file.name.startswith("fomcminutes") else "statements"
        doc_id = ("MIN_" if kind == "minutes" else "STA_") + when
        file_hash = digest(file)
        rows = list(extract_pdf_sections(file))
        by_page = defaultdict(Counter)
        for position, (sid, section, page, content, _) in enumerate(rows, 1):
            paragraphs.append({
                "paragraph_id": f"{doc_id}_P{position:04d}",
                "doc_id": doc_id, "meeting_end": when,
                "document_type": kind, "filename": file.name,
                "section_id": sid, "section": section,
                "position": position, "page": page, "text": content,
                "source_sha256": file_hash,
                "source_url": f"https://www.federalreserve.gov/monetarypolicy/files/{file.name}",
            })
            by_page[page].update(character_inventory(content))

        with pymupdf.open(file) as pdf:
            pages = len(pdf)
            page_count += pages
            for i, page in enumerate(pdf, 1):
                raw_text = " ".join(r["text"] for r in page_lines(page))
                expected = character_inventory(raw_text)
                actual = by_page[i]
                if expected != actual:
                    failures.append({
                        "file": file.name, "page": i,
                        "missing_characters": dict(expected - actual),
                        "extra_characters": dict(actual - expected),
                    })
        manifest.append({
            "doc_id": doc_id, "filename": file.name, "type": kind,
            "meeting_end": when, "path": str(file.relative_to(ROOT)),
            "sha256": file_hash, "pages": pages,
        })
        log(f"Extraction {len(manifest)}/93 : {file.name}")

    if failures:
        raise ValueError(f"Conservation du contenu échouée sur {len(failures)} pages : {failures[:10]}")
    unique(manifest, "doc_id")
    chunks = chunk_paragraphs(paragraphs, tokenizer, config)
    by_id = {p["paragraph_id"]: p for p in paragraphs}

    # Positions globales dans le texte logique du document (paragraphes séparés par \n\n).
    doc_offsets = defaultdict(int)
    section_starts = {}
    for p in paragraphs:
        key = (p["doc_id"], p["section_id"])
        section_starts.setdefault(key, doc_offsets[p["doc_id"]])
        doc_offsets[p["doc_id"]] += len(p["text"]) + 2

    for chunk in chunks:
        p = by_id[chunk["paragraph_ids"][0]]
        chunk.update(
            filename=p["filename"], document_type=p["document_type"],
            source_sha256=p["source_sha256"],
        )
        offset = section_starts[(chunk["doc_id"], chunk["section_id"])]
        chunk.update(
            doc_char_start=offset + chunk["section_char_start"],
            doc_char_end=offset + chunk["section_char_end"],
        )

    sizes = [c["token_count"] for c in chunks]
    multipage = [c for c in chunks if c["multipage"]]
    short = [c for c in chunks if c["token_count"] < 100]
    low_contribution = [
        c for c in multipage
        if min(p["ratio"] for p in c["page_contributions"]) < .05
    ]
    write_jsonl(ROOT / "data/processed/paragraphs.jsonl", paragraphs)
    write_jsonl(ROOT / "data/processed/chunks.jsonl", chunks)
    write_json(ROOT / "data/processed/manifest.json", manifest)
    report = {
        "config": CONFIG, "documents": len(files),
        "document_types": dict(Counter(m["type"] for m in manifest)),
        "pages": page_count, "paragraphs": len(paragraphs), "chunks": len(chunks),
        "min_tokens": min(sizes), "median_tokens": statistics.median(sizes),
        "max_tokens": max(sizes),
        "max_input_tokens": max(c["model_token_count"] for c in chunks),
        "chunks_under_100_tokens": len(short),
        "multipage_chunks": len(multipage),
        "multipage_ratio": len(multipage) / len(chunks),
        "multipage_with_minor_page_under_5_percent": len(low_contribution),
        "content_conservation_failures": failures,
        "content_validation": "Alphanumeric character inventory per PDF page",
        "chunks_sha256": digest(ROOT / "data/processed/chunks.jsonl"),
    }
    write_json(ROOT / "data/processed/chunk_report.json", report)
    log(f"Découpage terminé : {len(chunks)} chunks, {page_count} pages")
    log(f"Chunks multipages : {len(multipage)} ({len(multipage)/len(chunks):.1%})")
    log(f"Chunks <100 tokens : {len(short)}")
    log(f"Chunks multipages avec page <5 % : {len(low_contribution)}")


if __name__ == "__main__":
    main()
