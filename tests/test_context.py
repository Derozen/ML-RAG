"""Regression tests: rerank twenty candidates before selecting six outputs."""
import sys
from pathlib import Path
from unittest import TestCase, mock
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import select_context
from rag_pipeline import retrieve
from generate import make_context


class ContextTests(TestCase):
    def test_top5_and_top6_are_distinct_prefixes(self):
        rows=[dict(rank=i+1,chunk_id=str(i),score=20-i) for i in range(20)]
        self.assertEqual(len(select_context(rows)),6)
        self.assertEqual(select_context(rows,5),rows[:5])
        with self.assertRaises(ValueError):select_context(rows,20)
        with self.assertRaises(ValueError):select_context(rows[::-1],6)

    def test_online_reranker_scores_twenty_before_returning_six(self):
        chunks=[dict(chunk_id=str(i),text=str(i),search_text=str(i),filename='a.pdf',
                     meeting_end='2021-01-27',page_start=1,page_end=1) for i in range(30)]
        lexical=mock.Mock()
        lexical.get_scores.return_value=np.arange(30,dtype=float)
        model=mock.Mock()
        model.score.return_value=list(range(20))
        timings={}
        with mock.patch('rag_pipeline.assets',return_value=(chunks,lexical,np.zeros((30,2)),None,[str(i) for i in range(30)])), mock.patch('rerank.CrossEncoder',return_value=model):
            result=retrieve('a question',method='bm25',reranker='cross_encoder',timings=timings)
        self.assertEqual(len(model.score.call_args.args[1]),20)
        self.assertEqual([r['chunk_id'] for r in result],['10','11','12','13','14','15'])
        self.assertEqual(timings['candidate_count'],20)
        self.assertEqual(timings['selected_count'],6)

    def test_generation_rejects_oversized_direct_context(self):
        with self.assertRaises(ValueError):make_context([{}]*20)
