"""Read-only checks of the frozen study; writes a separate methodological audit."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rag_fomc.common import read_jsonl, sha256, write_json
from rag_fomc.evaluation import retrieval_metrics, validate_questions
from rag_fomc.indexing import load_index

def main():
    questions_path=ROOT/'evaluation/questions.jsonl'
    questions=read_jsonl(questions_path)
    meta,chunks,_,_=load_index(ROOT)
    validate_questions(questions,chunks,annotated=True)
    annotation=json.loads((ROOT/'evaluation/annotations.json').read_text(encoding='utf-8'))
    assert annotation['questions_sha256']==sha256(questions_path)
    assert annotation['chunks_sha256']==meta['chunks_sha256']
    split_docs=defaultdict(set)
    for q in questions:
        for e in q['evidence']: split_docs[q['split']].add(e['doc_id'])
    assert not split_docs['dev'] & split_docs['test']
    checked=0; runs={}
    for split in ('dev','test'):
        folder=ROOT/f'results/comparison_200_v1/{split}'
        run=json.loads((folder/'run.json').read_text(encoding='utf-8'))
        assert run['questions_sha256']==sha256(questions_path)
        assert run['annotations_sha256']==sha256(ROOT/'evaluation/annotations.json')
        assert run['chunks_sha256']==meta['chunks_sha256']
        assert run['config']==meta['config']
        ranks=defaultdict(list)
        for r in read_jsonl(folder/'rankings.jsonl'): ranks[(r['qid'],r['method'])].append(r)
        by_q={q['qid']:q for q in questions if q['split']==split}
        with (folder/'metrics_per_question.csv').open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                q=by_q[row['qid']]
                ids=[r['chunk_id'] for r in sorted(ranks[(q['qid'],row['method'])],key=lambda r:r['rank'])]
                recomputed=retrieval_metrics(ids,q['evidence'],int(row['k']))
                assert all(abs(float(row[key])-value)<1e-12 for key,value in recomputed.items())
                checked+=1
        runs[split]={'questions':len(by_q),'answerable':sum(q['answerable'] for q in by_q.values()),
                     'evidence_documents':len(split_docs[split]),'configuration_matches_index':True}
    # A concrete relevance gap in DEV, not an automatic annotation amendment.
    q=next(q for q in questions if q['qid']=='Q021')
    alternative=next(c for c in chunks if c['chunk_id']=='FOMC_2021-09-22_C0038')
    quote='The Committee decided to keep the target range for the federal funds rate at 0 to ¼ percent'
    assert quote in alternative['text']
    assert all(alternative['chunk_id'] not in e['chunk_ids'] for e in q['evidence'])
    rankings=read_jsonl(ROOT/'results/comparison_200_v1/dev/rankings.jsonl')
    hit=next(r for r in rankings if r['qid']=='Q021' and r['method']=='bm25' and r['chunk_id']==alternative['chunk_id'])
    gap={'qid':'Q021','split':'dev','question':q['question'],'existing_accepted_chunks':q['evidence'][0]['chunk_ids'],
         'additional_chunk':alternative['chunk_id'],'doc_id':alternative['doc_id'],
         'page':12,'quote':quote,'bm25_rank':hit['rank'],
         'status':'confirmed_semantic_alternative_not_added_to_frozen_annotations',
         'consequence':'A relevant passage is retrieved but the original annotation-based score marks this question as unsuccessful.'}
    courses=[]
    import pymupdf
    for n in (1,2):
        path=Path.home()/f'Downloads/Cours_ML_ECC_{n}.pdf'
        with pymupdf.open(path) as pdf: pages=len(pdf)
        courses.append({'file':str(path),'pages':pages,'sha256':sha256(path)})
    out=ROOT/'results/methodology_review_2026-11-08'
    write_json(out/'audit.json',{
        'created_at_utc':datetime.now(timezone.utc).isoformat(),'courses':courses,
        'scope':'Frozen retrieval baseline, not trained predictive modeling or complete RAG.',
        'runs':runs,'questions':len(questions),'types':dict(Counter(q['type'] for q in questions)),
        'metric_rows_recomputed_without_retrieval':checked,'metric_mismatches':0,
        'cross_split_evidence_documents':0,'index_integrity':'passed',
        'questions_sha256':sha256(questions_path),'chunks_sha256':meta['chunks_sha256'],
        'confirmed_annotation_gaps':[gap],
        'limitations':['No completed hyperparameter search; current study is a fixed-configuration baseline.',
                       'Previously observed test must not be reused as an untouched confirmation test for new tuning.',
                       'Family bootstrap omits shared-document dependence.',
                       'Concurrent initial runs do not establish a reliable latency comparison.',
                       'No abstention evaluation and limited topic/negative diversity.'],
        'preservation':'Original qrels, index, rankings, scores and PDF report have not been rewritten.'})
    write_json(out/'annotation_case_Q021.json',gap)
    print(f'Audit saved to {out}; {checked} metric rows checked; no metric mismatch.')

if __name__=='__main__': main()
