"""Valider les qrels silver de pages sans inventer de jugements de chunks."""
from collections import Counter
import re
from common import ROOT, questions, read_json, read_jsonl, write_json, write_jsonl, write_csv, digest, log


def parse_page_qrels(text, question_ids, manifest):
    documents = {d['filename']: d for d in manifest}
    judgments = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f'Qrels ligne {line_number}: quatre champs TREC requis')
        qid, _, page_id, raw_grade = fields
        match = re.fullmatch(r'(.+\.pdf)#p([1-9][0-9]*)', page_id)
        if qid not in question_ids or not match:
            raise ValueError(f'Question/page inconnue ligne {line_number}')
        filename, page = match[1], int(match[2])
        grade = int(raw_grade)
        if grade < 0 or filename not in documents or page > documents[filename]['pages']:
            raise ValueError(f'Page/grade invalide ligne {line_number}')
        key = (qid, page_id)
        if key in judgments:
            raise ValueError(f'Jugement dupliqué: {key}')
        judgments[key] = grade
    covered = {qid for (qid, _), grade in judgments.items() if grade > 0}
    if covered != set(question_ids):
        raise ValueError('Une question ne possède aucune page pertinente annotée')
    return judgments


def make_chunk_pages(chunks, paragraphs):
    """Pages effectivement représentées par les paragraphes du chunk."""
    lookup = {p['paragraph_id']: p for p in paragraphs}
    result = {}
    for chunk in chunks:
        pages = set()
        for paragraph_id in chunk['paragraph_ids']:
            paragraph = lookup[paragraph_id]
            if paragraph['filename'] != chunk['filename']:
                raise ValueError('Provenance de paragraphe incohérente')
            pages.add(paragraph['page'])
        if not pages:
            raise ValueError('Chunk sans page')
        result[chunk['chunk_id']] = [f"{chunk['filename']}#p{p}" for p in sorted(pages)]
    return result


def project_pages(chunk_ids, mapping):
    """Rang de page = première apparition; pages d'un même chunk par ordre physique."""
    seen = set()
    pages = []
    for chunk_id in chunk_ids:
        for page_id in mapping[chunk_id]:
            if page_id not in seen:
                seen.add(page_id)
                pages.append(page_id)
    return pages


def main():
    base = ROOT / 'data/evaluation'
    queries = questions()
    manifest = read_json(ROOT / 'data/processed/manifest.json')
    for document in manifest:
        if digest(ROOT / document['path']) != document['sha256']:
            raise ValueError(f"PDF modifié depuis le découpage: {document['filename']}")
    judgments = parse_page_qrels((base / 'silver_qrels_PAGES.trec').read_text(encoding='utf-8-sig'),
                                {q['id'] for q in queries}, manifest)
    mapping = make_chunk_pages(read_jsonl(ROOT / 'data/processed/chunks.jsonl'),
                               read_jsonl(ROOT / 'data/processed/paragraphs.jsonl'))
    available = {page for pages in mapping.values() for page in pages}
    missing = sorted({page for (_, page), grade in judgments.items() if grade > 0} - available)
    if missing:
        raise ValueError(f'Pages annotées sans texte indexé: {missing}')
    write_csv(base / 'page_qrels.tsv', [dict(question_id=qid, page_id=page, relevance=grade)
              for (qid, page), grade in sorted(judgments.items())], delimiter='\t')
    write_jsonl(base / 'chunk_pages.jsonl', [dict(chunk_id=cid, page_ids=pages)
                                           for cid, pages in sorted(mapping.items())])
    report = dict(questions=len(queries), judgments=len(judgments),
                  judged_pages=len({page for _, page in judgments}),
                  judged_documents=len({page.split('#p')[0] for _, page in judgments}),
                  grade_counts=dict(Counter(judgments.values())),
                  corpus_documents=len(manifest), corpus_chunks=len(mapping),
                  source_pdfs_sha256_verified=True,
                  questions_sha256=digest(base / 'queries_145.jsonl'),
                  source_qrels_sha256=digest(base / 'silver_qrels_PAGES.trec'),
                  page_qrels_sha256=digest(base / 'page_qrels.tsv'),
                  mapping_sha256=digest(base / 'chunk_pages.jsonl'),
                  chunks_sha256=digest(ROOT / 'data/processed/chunks.jsonl'),
                  paragraphs_sha256=digest(ROOT / 'data/processed/paragraphs.jsonl'),
                  status='Silver page judgments supplied by user. Page existence and indexing verified; semantic relevance not manually re-annotated.',
                  evaluation_unit='unique PDF page', split_policy='all questions together; supplied split labels retained as metadata only')
    write_json(base / 'alignment_report.json', report)
    log(f"Qrels pages validés: {len(queries)} questions, {len(judgments)} jugements; aucun grade de chunk inventé")


if __name__ == '__main__':
    main()
