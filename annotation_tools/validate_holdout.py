"""Validate candidate annotation artifacts, without running any RAG evaluation."""
from collections import Counter
from pathlib import Path
import csv
import re
import sys
import pymupdf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from common import read_json,read_jsonl,write_json,digest
from protocol import verify
from rebuild_holdout import canonical


def main():
    verify()
    base=ROOT/'data/holdout_candidate'
    queries=read_jsonl(base/'queries_20.jsonl')
    by_id={q['question_id']:q for q in queries}
    gold={q['question_id']:q for q in read_jsonl(base/'question_gold.jsonl')}
    assert len(queries)==len(by_id)==20 and set(gold)==set(by_id)
    assert Counter(q['source_scope'] for q in queries)==dict(minutes=6,statements=6,mixed=8)
    assert Counter(q['question_type'] for q in queries)==dict(factual=4,explanatory=6,comparative=5,multi_evidence=5)
    assert all(not ({'expected_answer','derivation','facet_page_ids'}&q.keys()) for q in queries)
    old=read_jsonl(ROOT/'data/evaluation/queries_145.jsonl')
    assert not {canonical(q['question']) for q in queries}&{canonical(q['question']) for q in old}
    judged={}
    for line in (base/'qrels_PAGES_candidate.trec').read_text(encoding='utf-8').splitlines():
        qid,iteration,page,grade=line.split();key=qid,page
        assert qid in by_id and iteration=='0' and int(grade) in (0,1,2) and key not in judged
        assert page.split('#p')[0] in by_id[qid]['source_documents']
        judged[key]=int(grade)
    assert {qid for (qid,_),g in judged.items() if g>0}==set(by_id)
    for qid,g in gold.items():
        assert all(pages and all(judged[qid,pid]>0 for pid in pages) for pages in g['facet_page_ids'].values())
    paragraphs={p['paragraph_id']:p for p in read_jsonl(ROOT/'data/processed/paragraphs.jsonl')}
    documents={d['filename']:d for d in read_json(ROOT/'data/processed/manifest.json')}
    opened={};raw_checks=0;quote_checks=0
    evidence=read_jsonl(base/'evidence_20.jsonl')
    assert {(e['question_id'],e['page_id']) for e in evidence}==set(judged)
    for e in evidence:
        assert judged[e['question_id'],e['page_id']]==e['relevance']
        name,page=e['page_id'].rsplit('#p',1)
        if name not in opened:
            assert digest(ROOT/documents[name]['path'])==documents[name]['sha256']
            opened[name]=pymupdf.open(ROOT/documents[name]['path'])
        assert 1<=int(page)<=len(opened[name])
        raw=canonical(opened[name][int(page)-1].get_text())
        for facet in e['covered_facets']:
            for snippet in facet['snippets']:
                p=paragraphs[snippet['paragraph_id']]
                assert p['text']==snippet['quote'] and p['filename']==name and p['page']==int(page)
                assert p['source_sha256']==snippet['source_sha256']
                quote_checks+=1
                for fragment in snippet['matched_fragments']:
                    assert canonical(fragment) in raw,(e['question_id'],e['page_id'],fragment)
                    raw_checks+=1
    for doc in opened.values():doc.close()
    with (base/'human_review.csv').open(encoding='utf-8-sig') as stream:
        reviews=list(csv.DictReader(stream))
    assert len({(r['question_id'],r['page_id']) for r in reviews})==len(reviews)==294
    assert all((r['proposed_grade']==str(judged[r['question_id'],r['page_id']])) if (r['question_id'],r['page_id']) in judged else r['proposed_grade']=='' for r in reviews)
    with (base/'semantic_pairs_145.csv').open(encoding='utf-8-sig') as stream:
        pairs=list(csv.DictReader(stream))
    assert len(pairs)==len({(r['new_question_id'],r['old_question_id']) for r in pairs})==20*145
    for target in re.findall(r'\]\(([^)]+)\)',(base/'REVUE_HUMAINE.md').read_text(encoding='utf-8')):
        assert (base/target.split('#')[0]).resolve().exists(),target
    assert not list(base.glob('*metrics*'))
    report=read_json(base/'validation_report.json')
    assert report['evaluation_performed'] is False and report['human_second_review_completed'] is False
    report.update(artifact_validation_passed=True,source_quote_checks=quote_checks,
                  independent_raw_pdf_fragment_checks=raw_checks,ready_for_final_scoring=False,
                  blocking_items=['Independent second annotation review not completed',
                                  '230 in-scope question/page pairs remain unjudged',
                                  'Semantic overlap review requires human adjudication; topical independence not proved'])
    report['annotation_tool_files']={p.name:digest(p) for p in Path(__file__).parent.iterdir() if p.is_file()}
    report['files']={p.name:digest(p) for p in base.iterdir() if p.is_file() and p.name!='validation_report.json'}
    write_json(base/'validation_report.json',report)
    print(f'PASS: {len(queries)} questions, {len(judged)} proposed page judgments, {quote_checks} quote checks, {raw_checks} raw-PDF fragment checks, {len(pairs)} old/new screening pairs. Dataset remains unscored and pending independent review.')


if __name__=='__main__':main()
