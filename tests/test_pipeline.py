"""Tests des métriques et des invariants, indépendants des performances des modèles."""
from pathlib import Path
import math
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from common import normalize_text,lexical_tokens,questions,read_json,read_jsonl,digest,E5Tokenizer
from align_references import parse_page_qrels,make_chunk_pages,project_pages
from evaluate import metrics
from rerank import maxsim,validate_pool
from retrieve import rrf
from pdf_layout import reading_order

class MetricTests(unittest.TestCase):
    def test_known_graded_ndcg_and_mrr(self):
        result=metrics(['b','a','z'],{'a':2,'b':1,'c':2})
        ideal=3+3/math.log2(3)+1/math.log2(4)
        actual=1+3/math.log2(3)
        self.assertAlmostEqual(result['ndcg_at_10'],actual/ideal)
        self.assertEqual(result['mrr_at_10'],1)
        self.assertAlmostEqual(result['recall_at_20'],2/3)

    def test_reordering_twenty_evaluated_units_preserves_recall20(self):
        grades={'a':2,'b':1,'outside':2}
        ids=['a','b']+[f'x{i}' for i in range(18)]
        self.assertEqual(metrics(ids,grades)['recall_at_20'],metrics(ids[::-1],grades)['recall_at_20'])
        self.assertGreater(metrics(ids,grades)['ndcg_at_10'],metrics(ids[::-1],grades)['ndcg_at_10'])

    def test_unknown_and_duplicate_rankings(self):
        self.assertEqual(metrics(['x'],{'a':2})['mrr_at_10'],0)
        with self.assertRaises(ValueError): metrics(['a','a'],{'a':2})
        with self.assertRaises(ValueError): metrics(['a'],{})

    def test_pool_change_rejected(self):
        before=[{'chunk_id':str(i)} for i in range(20)]
        validate_pool(before,before[::-1])
        with self.assertRaises(ValueError): validate_pool(before,before[:-1]+[{'chunk_id':'other'}])

    def test_colbert_is_sum_of_token_maxima(self):
        q=np.eye(2,dtype=np.float32); d=np.eye(2,dtype=np.float32)
        self.assertEqual(maxsim(q,d),2)
        self.assertEqual(maxsim(q,d[:1]),1)
        with self.assertRaises(ValueError): maxsim(q,d[:0])

    def test_rrf_formula(self):
        order,scores=rrf([['a','b','c'],['b','d','a']],60)
        self.assertEqual(order,['b','a','d','c'])
        self.assertAlmostEqual(scores['b'],1/62+1/61)
        with self.assertRaises(ValueError): rrf([['a','a']])

class SourceTests(unittest.TestCase):
    def test_user_queries_and_all_sources(self):
        qs=questions(); self.assertEqual(len(qs),145)
        refs=parse_page_qrels((ROOT/'data/evaluation/silver_qrels_PAGES.trec').read_text(encoding='utf-8-sig'),
                              {q['id'] for q in qs},read_json(ROOT/'data/processed/manifest.json'))
        self.assertEqual(len(refs),279)
        self.assertEqual(len({pid.split('#p')[0] for qid,pid in refs}),93)
        self.assertTrue(all(set(q)=={'id','question'} for q in qs))

    def test_alignment_complete_and_current(self):
        report=read_json(ROOT/'data/evaluation/alignment_report.json')
        self.assertEqual(report['judgments'],279)
        self.assertEqual(report['questions'],145)
        self.assertEqual(report['chunks_sha256'],digest(ROOT/'data/processed/chunks.jsonl'))
        self.assertEqual(report['source_qrels_sha256'],digest(ROOT/'data/evaluation/silver_qrels_PAGES.trec'))
        self.assertEqual(report['mapping_sha256'],digest(ROOT/'data/evaluation/chunk_pages.jsonl'))

    def test_page_mapping_uses_actual_paragraphs(self):
        mapping=make_chunk_pages(read_jsonl(ROOT/'data/processed/chunks.jsonl'),
                                 read_jsonl(ROOT/'data/processed/paragraphs.jsonl'))
        exported={r['chunk_id']:r['page_ids'] for r in read_jsonl(ROOT/'data/evaluation/chunk_pages.jsonl')}
        self.assertEqual(mapping,exported)

    def test_mixed_font_baseline_order(self):
        rows=[dict(text='right part',bbox=(200,98,400,113),baseline=110),
              dict(text='left part',bbox=(40,100,199,114),baseline=110)]
        ordered,two=reading_order(rows,600)
        self.assertFalse(two); self.assertEqual([r['text'] for r in ordered],['left part','right part'])

    def test_fraction_matching_and_negation(self):
        self.assertEqual(normalize_text('  4¾  percent '),'4¾ percent')
        self.assertNotEqual(lexical_tokens('4¾ percent'),lexical_tokens('4½ percent'))
        self.assertNotEqual(lexical_tokens('did not rise'),lexical_tokens('did rise'))
        self.assertIn('not',lexical_tokens('did not change 4¾%'))

    def test_chunk_bounds_with_real_tokenizer(self):
        tok=E5Tokenizer()
        for c in read_jsonl(ROOT/'data/processed/chunks.jsonl'):
            self.assertLessEqual(len(tok.encode('passage: '+c['search_text'])),512)
            self.assertLessEqual(c['token_count'],400)

    def test_silver_grades_preserved_and_invalid_pages_rejected(self):
        manifest=[{'filename':'a.pdf','pages':3}]
        self.assertEqual(parse_page_qrels('q 0 a.pdf#p2 1\nq 0 a.pdf#p3 2',{'q'},manifest),
                         {('q','a.pdf#p2'):1,('q','a.pdf#p3'):2})
        for bad in ['q 0 a.pdf#p4 2','q 0 missing.pdf#p1 2','q 0 a.pdf#p1 2\nq 0 a.pdf#p1 2']:
            with self.assertRaises(ValueError): parse_page_qrels(bad,{'q'},manifest)

    def test_duplicate_pages_do_not_inflate_scores(self):
        mapping={'a':['d.pdf#p1','d.pdf#p2'],'b':['d.pdf#p2'],'c':['d.pdf#p3']}
        ids=project_pages(['a','b','c'],mapping)
        self.assertEqual(ids,['d.pdf#p1','d.pdf#p2','d.pdf#p3'])
        self.assertEqual(metrics(ids,{'d.pdf#p2':2})['mrr_at_10'],.5)

    def test_page_cutoff_can_change_while_chunk_pool_is_fixed(self):
        mapping={f'c{i}':[f'p{i+1}'] for i in range(20)}
        mapping['c0']=['p0','p1']
        ids=list(mapping)
        before=project_pages(ids,mapping); after=project_pages(ids[::-1],mapping)
        self.assertEqual(set(before),set(after))
        self.assertEqual(len(before),21)
        self.assertEqual(metrics(before,{'p20':2})['recall_at_20'],0)
        self.assertEqual(metrics(after,{'p20':2})['recall_at_20'],1)

if __name__=='__main__': unittest.main()
