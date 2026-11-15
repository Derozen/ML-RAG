"""Extraire les 93 PDF et produire un d?coupage commun avec provenance."""
from collections import Counter, defaultdict
from datetime import date
from itertools import groupby
from types import SimpleNamespace
import re
import statistics
from common import ROOT, CONFIG, normalize_text, digest, write_json, write_jsonl, log, model_dir, E5Tokenizer
from pdf_layout import extract_pdf_sections, page_lines
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
def unique(rows,key):
    if len({r[key] for r in rows}) != len(rows): raise ValueError("Duplicate " + key)

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

def main():
    import pymupdf
    files=sorted((ROOT/'data/raw').rglob('*.pdf'))
    if len(files)!=93: raise ValueError(f'93 PDF attendus, {len(files)} présents')
    tokenizer=E5Tokenizer()
    config=SimpleNamespace(**CONFIG,passage_prefix='passage: ')
    paragraphs=[]; manifest=[]; page_count=0; failures=[]
    for file in files:
        match=re.search(r'(20\d{6})',file.stem)
        if not match: raise ValueError(file)
        value=match.group(); when=f'{value[:4]}-{value[4:6]}-{value[6:]}'
        kind='minutes' if file.name.startswith('fomcminutes') else 'statements'
        doc_id=('MIN_' if kind=='minutes' else 'STA_')+when
        file_hash=digest(file)
        rows=list(extract_pdf_sections(file))
        by_page=defaultdict(Counter)
        for position,(sid,section,page,text,_) in enumerate(rows,1):
            paragraphs.append(dict(paragraph_id=f'{doc_id}_P{position:04}',doc_id=doc_id,
                meeting_end=when,document_type=kind,filename=file.name,section_id=sid,
                section=section,position=position,page=page,text=text,source_sha256=file_hash,
                source_url=f'https://www.federalreserve.gov/monetarypolicy/files/{file.name}'))
            by_page[page]+=Counter(text.split())
        with pymupdf.open(file) as pdf:
            pages=len(pdf); page_count+=pages
            for i,page in enumerate(pdf,1):
                expected=Counter(' '.join(r['text'] for r in page_lines(page)).split())
                if expected!=by_page[i]: failures.append({'file':file.name,'page':i})
        manifest.append(dict(doc_id=doc_id,filename=file.name,type=kind,meeting_end=when,
                             path=str(file.relative_to(ROOT)),sha256=file_hash,pages=pages))
        log(f'Extraction {len(manifest)}/93 : {file.name}')
    if failures: raise ValueError(f'Pertes de contenu : {failures}')
    chunks=chunk_paragraphs(paragraphs,tokenizer,config)
    by_id={p['paragraph_id']:p for p in paragraphs}
    doc_offsets=defaultdict(int); section_starts={}
    for p in paragraphs:
        section_starts.setdefault((p['doc_id'],p['section_id']),doc_offsets[p['doc_id']])
        doc_offsets[p['doc_id']]+=len(p['text'])+2
    for c in chunks:
        p=by_id[c['paragraph_ids'][0]]
        c.update(filename=p['filename'],document_type=p['document_type'],source_sha256=p['source_sha256'])
        offset=section_starts[(c['doc_id'],c['section_id'])]
        c.update(doc_char_start=offset+c['section_char_start'],doc_char_end=offset+c['section_char_end'])
    write_jsonl(ROOT/'data/processed/paragraphs.jsonl',paragraphs)
    write_jsonl(ROOT/'data/processed/chunks.jsonl',chunks)
    write_json(ROOT/'data/processed/manifest.json',manifest)
    write_json(ROOT/'data/processed/chunk_report.json',dict(config=CONFIG,documents=len(files),
        document_types=dict(Counter(m['type'] for m in manifest)),pages=page_count,paragraphs=len(paragraphs),
        chunks=len(chunks),min_tokens=min(c['token_count'] for c in chunks),
        median_tokens=statistics.median(c['token_count'] for c in chunks),
        max_tokens=max(c['token_count'] for c in chunks),max_input_tokens=max(c['model_token_count'] for c in chunks),
        content_conservation_failures=failures,chunks_sha256=digest(ROOT/'data/processed/chunks.jsonl')))
    log(f'Découpage terminé : {len(chunks)} passages, {page_count} pages, aucune perte de tokens détectée')

if __name__=='__main__': main()

