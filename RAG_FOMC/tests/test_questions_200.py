"""Regression checks for the proposed benchmark and its split isolation."""
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_questions_200',ROOT/'scripts/prepare_questions_200.py')
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class QuestionDraftTests(unittest.TestCase):
    def test_sources_and_split_isolation(self):
        report=builder.audit(builder.read(ROOT/'evaluation/questions_200_draft.jsonl'),
                             builder.read(ROOT/'data/processed/paragraphs.jsonl'),
                             builder.read(ROOT/'data/processed/chunks.jsonl'))
        self.assertEqual(report['proof_groups_checked'],220)
        self.assertEqual(report['pdf_quote_failures'],0)

    def test_paraphrases_retain_their_ground_truth(self):
        rows=builder.read(ROOT/'evaluation/questions_200_draft.jsonl')
        by_id={q['qid']:q for q in rows}
        for q in rows:
            if q['type']=='paraphrase':
                parent=by_id[q['paraphrase_of']]
                for field in ('split','family_id','reference_answer','evidence'):
                    self.assertEqual(q[field],parent[field])

    def test_drafts_do_not_promote_the_validated_set(self):
        rows=builder.read(ROOT/'evaluation/questions_200_draft.jsonl')
        self.assertTrue(all(q['validated'] is False for q in rows))
        self.assertEqual(len(builder.read(ROOT/'evaluation/dev_50_draft.jsonl')),50)
        self.assertEqual(len(builder.read(ROOT/'evaluation/test_150_draft.jsonl')),150)
