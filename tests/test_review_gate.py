"""Prevent accidental promotion of incomplete or conflicting annotations."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'annotation_tools'))
from check_review import assess


def example():
    queries = [dict(question_id='Q', source_documents=['a.pdf'])]
    gold = [dict(question_id='Q', facet_page_ids={'fact': ['a.pdf#p1']})]
    pages = [dict(question_id='Q', page_id='a.pdf#p1', proposed_grade='2',
                  human_grade='2', reviewer='Reader', notes='')]
    decisions = [dict(question_id='Q', semantic_verdict='distinct', old_questions_reviewed='145',
                      answer_verified='yes', facets_verified='yes', reviewer='Reader',
                      rationale='Reviewed the questions and checked the supporting page.')]
    return queries, gold, pages, decisions


def test_blank_annotations_never_ready():
    q, g, p, d = example()
    p[0]['human_grade'] = ''
    d[0]['semantic_verdict'] = ''
    r = assess(q, g, p, d)
    assert r['status'] == 'annotation_pending'
    assert r['pending_page_pairs'] == 1
    assert not r['ready_for_final_scoring']


def test_missing_pages_or_unexplained_disagreement_block_release():
    q, g, p, d = example()
    p[0]['human_grade'] = '0'
    r = assess(q, g, p, d, {('Q', 'a.pdf#p1'), ('Q', 'a.pdf#p2')})
    assert r['status'] == 'annotation_pending'
    assert any('exactly all pages' in s for s in r['blocking_items'])
    assert any('adjudication note' in s for s in r['blocking_items'])
    assert any('no human-confirmed' in s for s in r['blocking_items'])


def test_complete_declarations_still_require_versioned_release():
    r = assess(*example(), expected_keys={('Q', 'a.pdf#p1')})
    assert r['status'] == 'ready_for_release_review'
    assert not r['ready_for_final_scoring']
    assert r['release_review_required']


def test_uncertain_semantic_novelty_blocks_release():
    q, g, p, d = example()
    d[0]['semantic_verdict'] = 'uncertain'
    assert assess(q, g, p, d)['status'] == 'annotation_pending'


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(value)
                              for name, value in globals().items()
                              if name.startswith('test_') and callable(value))
