"""Fenêtres de tokens avec frontières de phrases préférées et offsets sources."""
from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import date
from itertools import groupby
from pathlib import Path

from .common import read_jsonl, sha256, unique, write_json, write_jsonl
from .encoding import load_tokenizer, resolved_revision

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")


def meeting_label(value):
    d = date.fromisoformat(value)
    return f"Meeting ending {MONTHS[d.month - 1]} {d.day}, {d.year} ({value})"


def chunk_paragraphs(paragraphs, tokenizer, config):
    """Retourne le texte original, jamais une chaîne reconstruite par decode()."""
    unique(paragraphs, "paragraph_id")
    ordered = sorted(paragraphs, key=lambda p: (p["doc_id"], p["position"]))
    counts, chunks = Counter(), []
    for _, group in groupby(ordered, key=lambda p: (p["doc_id"], p["section_id"])):
        group = list(group)
        first = group[0]
        prefix = meeting_label(first["meeting_end"]) + " | " + first["section"] + "\n"
        overhead = len(tokenizer.encode(config.passage_prefix + prefix, add_special_tokens=True))
        budget = min(config.chunk_tokens, config.max_model_tokens - overhead - 4)
        if budget <= config.overlap_tokens:
            raise ValueError(f"Section trop longue pour les métadonnées : {first['section']}")
        full, spans = "", []
        for paragraph in group:
            if full:
                full += "\n\n"
            start = len(full)
            full += paragraph["text"]
            spans.append((start, len(full), paragraph))
        encoded = tokenizer(full, add_special_tokens=False, return_offsets_mapping=True, truncation=False, verbose=False)
        offsets = encoded["offset_mapping"]
        if not offsets:
            raise ValueError(f"Section vide : {first['doc_id']}")
        sentence_ends = {m.end() for m in re.finditer(r"[.!?](?:[\"’”])?(?=\s|$)|\n\n", full)}
        start, total = 0, len(offsets)
        while start < total:
            end = min(start + budget, total)
            if end < total:
                candidates = [j for j in range(start + max(config.overlap_tokens + 1, budget // 2), end + 1)
                              if offsets[j - 1][1] in sentence_ends]
                if candidates:
                    end = candidates[-1]
            while True:
                char_start, char_end = offsets[start][0], offsets[end - 1][1]
                text = full[char_start:char_end]
                search_text = prefix + text
                model_count = len(tokenizer.encode(config.passage_prefix + search_text, add_special_tokens=True))
                token_count = len(tokenizer.encode(text, add_special_tokens=False))
                if model_count <= config.max_model_tokens and token_count <= config.chunk_tokens:
                    break
                end -= 1
                if end <= start:
                    raise ValueError("Aucun token ne tient dans le budget du modèle")
            sources = [p for left, right, p in spans if left < char_end and right > char_start]
            pages = [p["page"] for p in sources]
            counts[first["doc_id"]] += 1
            chunks.append({"chunk_id": f"{first['doc_id']}_C{counts[first['doc_id']]:04d}",
                "doc_id": first["doc_id"], "meeting_end": first["meeting_end"],
                "section": first["section"], "section_id": first["section_id"],
                "paragraph_ids": [p["paragraph_id"] for p in sources],
                "page_start": min(pages) if all(p is not None for p in pages) else None,
                "page_end": max(pages) if all(p is not None for p in pages) else None,
                "source_url": first["source_url"], "text": text, "search_text": search_text,
                "token_count": token_count, "model_token_count": model_count,
                "section_char_start": char_start, "section_char_end": char_end,
                "section_token_start": start, "section_token_end": end})
            if end == total:
                break
            # Garantit une progression même pour une frontière exceptionnellement courte.
            start = max(start + 1, end - config.overlap_tokens)
    unique(chunks, "chunk_id")
    if {c["doc_id"] for c in chunks} != {p["doc_id"] for p in paragraphs}:
        raise ValueError("Un document n'a produit aucun passage")
    return chunks


def chunk(root, config):
    root = Path(root)
    path = root / "data/processed/paragraphs.jsonl"
    paragraphs = read_jsonl(path)
    if not paragraphs:
        raise ValueError("Aucun paragraphe : exécuter extract")
    revision = resolved_revision(config)
    tokenizer = load_tokenizer(config, revision)
    effective_limit = min(config.max_model_tokens, tokenizer.model_max_length)
    if config.max_model_tokens > effective_limit:
        raise ValueError("max_model_tokens dépasse la capacité du tokenizer")
    chunks = chunk_paragraphs(paragraphs, tokenizer, config)
    out = root / "data/processed/chunks.jsonl"
    write_jsonl(out, chunks)
    sizes = [c["token_count"] for c in chunks]
    write_json(root / "data/processed/chunking.json", {
        "schema_version": 1, "algorithm": "section-offset-windows-sentence-preferred-v1",
        "config": config.to_dict(), "resolved_model_revision": revision,
        "paragraphs_sha256": sha256(path), "chunks_sha256": sha256(out),
        "count": len(chunks), "per_document": dict(Counter(c["doc_id"] for c in chunks)),
        "tokens_min": min(sizes), "tokens_median": statistics.median(sizes), "tokens_max": max(sizes)})
    return chunks
