"""Check annotation readiness; never infer judgments or launch model scoring."""
import csv
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/holdout_candidate'


def assess(queries, gold, pages, decisions, expected_keys=None):
    issues = []
    ids = {q['question_id'] for q in queries}
    keys = [(r['question_id'], r['page_id']) for r in pages]
    if len(keys) != len(set(keys)):
        issues.append('Duplicate question/page rows')
    if expected_keys is not None and set(keys) != set(expected_keys):
        issues.append('Page review does not cover exactly all pages in the requested documents')
    if {r['question_id'] for r in pages} != ids:
        issues.append('Page review question IDs differ from candidate questions')
    for q in queries:
        docs = set(q['source_documents'])
        if any(r['page_id'].rsplit('#p', 1)[0] not in docs for r in pages if r['question_id'] == q['question_id']):
            issues.append(f"{q['question_id']}: page outside requested source scope")
    pending = [r for r in pages if r['human_grade'].strip() not in ('0', '1', '2') or not r['reviewer'].strip()]
    if pending:
        issues.append(f'{len(pending)} page judgments missing a valid human grade or reviewer')
    disagreements = [r for r in pages if r['human_grade'].strip() in ('0', '1', '2')
                     and r['proposed_grade'].strip() and r['human_grade'].strip() != r['proposed_grade'].strip()]
    if any(not r['notes'].strip() for r in disagreements):
        issues.append('Changed page grades require an adjudication note')
    dmap = {r['question_id']: r for r in decisions}
    if len(dmap) != len(decisions) or set(dmap) != ids:
        issues.append('Question adjudications missing or duplicated')
    incomplete = [qid for qid in ids if qid not in dmap or not all((
        dmap[qid]['semantic_verdict'].strip() == 'distinct',
        dmap[qid]['old_questions_reviewed'].strip() == '145',
        dmap[qid]['answer_verified'].strip().lower() == 'yes',
        dmap[qid]['facets_verified'].strip().lower() == 'yes',
        bool(dmap[qid]['reviewer'].strip()), bool(dmap[qid]['rationale'].strip())))]
    if incomplete:
        issues.append(f'{len(incomplete)} questions need semantic/gold adjudication; overlap or uncertainty prevents release')
    grades = {(r['question_id'], r['page_id']): r['human_grade'].strip() for r in pages}
    for g in gold:
        for facet, refs in g['facet_page_ids'].items():
            if not any(grades.get((g['question_id'], pid)) in ('1', '2') for pid in refs):
                issues.append(f"{g['question_id']}/{facet}: no human-confirmed positive reference")
    return dict(status='ready_for_release_review' if not issues else 'annotation_pending',
                ready_for_final_scoring=False,
                release_review_required=True,
                note='This check validates recorded declarations, not reviewer identity or semantic truth. '
                     'A versioned release and source/protocol verification remain required before scoring.',
                page_pairs=len(pages), pending_page_pairs=len(pending),
                completed_question_adjudications=len(ids) - len(incomplete),
                grade_changes=len(disagreements),
                human_grade_counts=dict(Counter(r['human_grade'].strip() or 'blank' for r in pages)),
                blocking_items=issues)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page-review', type=Path, default=BASE / 'human_review.csv',
                        help='CSV to check, including the consolidated proposed grid')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'src'))
    from protocol import verify
    verify()
    def jl(name):
        return [json.loads(s) for s in (BASE / name).read_text(encoding='utf-8').splitlines() if s.strip()]
    def rows(name):
        with (BASE / name).open(encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))
    with args.page_review.open(encoding='utf-8-sig', newline='') as f:
        page_reviews = list(csv.DictReader(f))
    queries = jl('queries_20.jsonl')
    source_pages = set()
    with (ROOT / 'data/processed/paragraphs.jsonl').open(encoding='utf-8') as f:
        for line in f:
            p = json.loads(line)
            source_pages.add((p['filename'], p['page']))
    expected = {(q['question_id'], f'{name}#p{page}') for q in queries
                for name, page in source_pages if name in q['source_documents']}
    result = assess(queries, jl('question_gold.jsonl'),
                    page_reviews, rows('question_adjudication.csv'), expected)
    result['review_grid_sha256'] = hashlib.sha256(args.page_review.read_bytes()).hexdigest()
    result['review_grid'] = str(args.page_review.resolve())
    # Existing pair-level judgments cannot be overruled by a question-level checkbox.
    unresolved = [r for r in rows('semantic_pairs_145.csv')
                  if r.get('human_semantic_verdict', '').strip().lower()
                  not in ('', 'distinct')]
    if unresolved:
        result['blocking_items'].append(f'{len(unresolved)} pair-level semantic verdicts require resolution')
        result['status'] = 'annotation_pending'
    # This supplemental status never changes the original validation report or qrels.
    target = args.page_review.parent / 'review_readiness.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'page_pairs', 'pending_page_pairs',
                                            'completed_question_adjudications', 'grade_changes')}, indent=2))
    raise SystemExit(0 if result['status'] == 'ready_for_release_review' else 2)


if __name__ == '__main__':
    main()
