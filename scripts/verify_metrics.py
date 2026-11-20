"""Independently recompute cached page metrics for all exploratory contexts."""
import csv
import json
import math
from pathlib import Path
from statistics import mean
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]


def jl(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    gold = defaultdict(dict)
    for line in (ROOT / 'data/evaluation/silver_qrels_PAGES.trec').read_text().splitlines():
        qid, _, pid, g = line.split()
        assert pid not in gold[qid]
        gold[qid][pid] = int(g)
    mapping = {r['chunk_id']: r['page_ids'] for r in jl(ROOT / 'data/evaluation/chunk_pages.jsonl')}
    initial = defaultdict(list)
    for r in jl(ROOT / 'results/retrieval/rankings.jsonl'):
        initial[r['question_id'], r['method']].append(r['chunk_id'])
    checked = 0
    def dcg(gs):
        return sum((2**g-1)/math.log2(i+2) for i, g in enumerate(gs))
    for budget in (5, 6):
        folder = ROOT / f'results/context_top{budget}'
        detail = {(r['question_id'], r['retrieval'], r['reranker']): r for r in rows(folder / 'metrics_per_question.csv')}
        contexts = jl(folder / 'contexts.jsonl')
        assert len(detail) == len(contexts) == 1740
        means = defaultdict(list)
        seen = set()
        for c in contexts:
            key = c['question_id'], c['retrieval'], c['reranker']
            assert key not in seen
            seen.add(key)
            ids = c['chunk_ids']
            assert len(ids) == len(set(ids)) == budget
            pool = initial[c['question_id'], c['retrieval']]
            assert len(pool) == len(set(pool)) == 20 and set(ids) <= set(pool)
            pages = list(dict.fromkeys(pid for cid in ids for pid in mapping[cid]))
            assert pages == c['page_ids']
            labels = gold[c['question_id']]
            relevant = {p for p, g in labels.items() if g > 0}
            recall = len(set(pages) & relevant)/len(relevant)
            first = next((i+1 for i, pid in enumerate(pages[:budget]) if pid in relevant), None)
            expected = dict(context_page_recall=recall,
                            all_reference_pages_found=float(relevant <= set(pages)),
                            mrr_pages_at_budget=1/first if first else 0)
            for k in (5, 6):
                ideal = dcg(sorted(labels.values(), reverse=True)[:k])
                expected[f'ndcg_pages_at_{k}'] = dcg([labels.get(pid, 0) for pid in pages[:k]])/ideal
            for field, value in expected.items():
                assert abs(float(detail[key][field])-value) < 1e-12, (budget, key, field)
            assert int(detail[key]['selected_pages']) == len(pages)
            means[c['retrieval'], c['reranker']].append(expected)
            checked += 1
        for summary in rows(folder / 'comparison.csv'):
            values = means[summary['retrieval'], summary['reranker']]
            assert len(values) == int(summary['questions']) == 145
            for field in values[0]:
                assert abs(mean(r[field] for r in values)-float(summary[field])) < 1e-12
    out = ROOT / 'results/delivery_verification'
    out.mkdir(exist_ok=True)
    (out / 'metrics_recomputed.json').write_text(json.dumps(dict(status='passed',
        contexts_checked=checked, budgets=[5, 6], configurations_per_budget=12, questions=145,
        checks=['same twenty-candidate pools', 'page projection and deduplication',
                'context recall', 'all-reference coverage', 'nDCG pages at 5 and 6',
                'MRR pages at context budget', 'all 24 summary rows'],
        tolerance=1e-12, source_results_modified=False, new_holdout_scored=False), indent=2)+'\n', encoding='utf-8')
    print(f'PASS: {checked} contexts, 24 summaries, independently recomputed metrics; cached source results unchanged.')


if __name__ == '__main__':
    main()
