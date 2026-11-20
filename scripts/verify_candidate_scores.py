"""Recompute provisional candidate metrics from exported contexts, without models."""
import csv
import json
import math
from pathlib import Path
import sys
from collections import defaultdict
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from common import digest, read_jsonl, write_json
from align_references import project_pages


def main():
    out = Path(sys.argv[1]).resolve()
    run = json.loads((out/'run.json').read_text(encoding='utf-8'))
    assert run['status']=='completed_provisional' and run['final_independent_test'] is False
    for name,sha in run['input_sha256'].items(): assert digest(ROOT/name)==sha
    for name,sha in run['output_sha256'].items(): assert digest(out/name)==sha
    refs = defaultdict(dict)
    for line in (ROOT/'data/holdout_candidate/assistant_review/completed_proposal/qrels_PAGES_proposed.trec').read_text().splitlines():
        qid,_,pid,grade = line.split()
        refs[qid][pid]=int(grade)
    mapping={r['chunk_id']:r['page_ids'] for r in read_jsonl(ROOT/'data/evaluation/chunk_pages.jsonl')}
    rankings={(r['question_id'],r['retrieval'],r['reranker']):r['chunk_ids'] for r in read_jsonl(out/'rankings.jsonl')}
    with (out/'metrics_per_question.csv').open(encoding='utf-8-sig',newline='') as f:
        detailed={(r['question_id'],r['retrieval'],r['reranker'],int(r['budget'])):r for r in csv.DictReader(f)}
    assert len(rankings)==240 and len(detailed)==480
    checks=[]
    for ctx in read_jsonl(out/'contexts.jsonl'):
        qid,m,rr,k=ctx['question_id'],ctx['retrieval'],ctx['reranker'],ctx['budget']
        order=rankings[qid,m,rr]
        assert len(order)==len(set(order))==20 and set(order)==set(rankings[qid,m,'none'])
        assert ctx['chunk_ids']==order[:k] and ctx['page_ids']==project_pages(order[:k],mapping)
        pages=ctx['page_ids']; grades=refs[qid]; positives={p for p,g in grades.items() if g>0}
        hits=[i+1 for i,p in enumerate(pages[:k]) if grades.get(p,0)>0]
        numerator=sum((2**grades.get(p,0)-1)/math.log2(i+2) for i,p in enumerate(pages[:k]))
        denominator=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(sorted(grades.values(),reverse=True)[:k]))
        expected=dict(context_page_recall=len(positives.intersection(pages))/len(positives),
            all_reference_pages_found=float(positives.issubset(pages)),
            ndcg_pages_at_budget=numerator/denominator,mrr_pages_at_budget=1/min(hits) if hits else 0.)
        row=detailed[qid,m,rr,k]
        assert all(abs(float(row[key])-value)<1e-12 for key,value in expected.items())
        checks.append(dict(retrieval=m,reranker=rr,budget=k,**expected))
    with (out/'comparison.csv').open(encoding='utf-8-sig',newline='') as f:
        summary=list(csv.DictReader(f))
    assert len(checks)==480 and len(summary)==24
    for row in summary:
        group=[r for r in checks if (r['retrieval'],r['reranker'],r['budget'])==(row['retrieval'],row['reranker'],int(row['budget']))]
        assert len(group)==20
        assert all(abs(mean(r[key] for r in group)-float(row[key]))<1e-12 for key in expected)
    write_json(out/'independent_recalculation.json',dict(status='passed',contexts=480,summaries=24,tolerance=1e-12,
        annotation_quality_validated=False,final_independent_test=False))
    print('PASS: 480 contextes, 24 synthèses, pools et provenance contrôlés ; qualité des annotations non certifiée.')


if __name__=='__main__': main()
