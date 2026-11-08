"""Checks for source-preserving annotation expansion and unchanged rankings."""
from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('consolidate',ROOT/'scripts/consolidate_evidence.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
from rag_fomc.common import read_jsonl, sha256

class EvidenceRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original={q['qid']:q for q in read_jsonl(ROOT/'evaluation/questions.jsonl')}
        cls.revised={q['qid']:q for q in read_jsonl(ROOT/'evaluation/revision_v2/questions_consolidated.jsonl')}
        cls.chunks={c['chunk_id']:c for c in read_jsonl(ROOT/'data/processed/chunks.jsonl')}
        cls.paragraphs={p['paragraph_id']:p for p in read_jsonl(ROOT/'data/processed/paragraphs.jsonl')}

    def test_original_validation_and_outputs_preserved(self):
        metadata=json.loads((ROOT/'evaluation/revision_v2/annotations.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['original_questions_sha256'],sha256(ROOT/'evaluation/questions.jsonl'))
        self.assertEqual(metadata['original_annotations_sha256'],sha256(ROOT/'evaluation/annotations.json'))
        for split in ('dev','test'):
            self.assertEqual(sha256(ROOT/f'results/comparison_200_v1/{split}/rankings.jsonl'),
                             sha256(ROOT/f'results/comparison_200_v2_rescored/{split}/rankings.jsonl'))

    def test_questions_and_evidence_groups_are_not_redefined(self):
        self.assertEqual(set(self.original),set(self.revised))
        for qid,q in self.revised.items():
            old=self.original[qid]
            for field in ('question','reference_answer','split','family_id','answerable','type'):
                self.assertEqual(q[field],old[field])
            self.assertFalse(q['validated'])
            self.assertEqual(len(q['evidence']),len(old['evidence']))
            for e,prior in zip(q['evidence'],old['evidence']):
                self.assertEqual(e['evidence_id'],prior['evidence_id'])
                self.assertEqual(e['doc_id'],prior['doc_id'])
                self.assertTrue(set(prior['chunk_ids']).issubset(e['chunk_ids']))

    def test_every_variant_has_literal_source_and_correct_page(self):
        docs=defaultdict(set)
        for q in self.revised.values():
            for e in q['evidence']:
                for cid in e['chunk_ids']:
                    c=self.chunks[cid]; s=e['sources_by_chunk'][cid]
                    p=self.paragraphs[s['paragraph_id']]
                    self.assertIn(e['quotes_by_chunk'][cid],c['text'])
                    self.assertIsNotNone(module.literal_match(p['text'],e['quotes_by_chunk'][cid]))
                    self.assertEqual(p['page'],s['page'])
                    self.assertEqual(p['doc_id'],e['doc_id'])
                    self.assertIn(s['paragraph_id'],c['paragraph_ids'])
                    docs[q['split']].add(e['doc_id'])
        self.assertFalse(docs['dev'] & docs['test'])

    def test_paraphrases_and_comparisons_reuse_the_same_proof_groups(self):
        registry={}
        for q in self.revised.values():
            if q['type']=='paraphrase':
                self.assertEqual(q['evidence'],self.revised[q['paraphrase_of']]['evidence'])
            for e in q['evidence']:
                key=(e['doc_id'],e['quote'])
                ids=tuple(e['chunk_ids'])
                if key in registry: self.assertEqual(registry[key],ids)
                registry[key]=ids

    def test_confirmed_q021_alternative_is_accepted(self):
        ids=self.revised['Q021']['evidence'][0]['chunk_ids']
        self.assertIn('FOMC_2021-09-22_C0038',ids)
        self.assertIn('FOMC_2021-09-22_C0034',ids)

    def test_normalized_matching_preserves_numbers_negation_and_literal_spelling(self):
        text='The unem- ployment rate did not rise to 4¼ percent.'
        self.assertEqual(module.literal_match(text,'unemployment rate did not rise to 4¼ percent'),
                         'unem- ployment rate did not rise to 4¼ percent')
        self.assertIsNone(module.literal_match(text,'unemployment rate did rise to 4¼ percent'))
        self.assertIsNone(module.literal_match(text,'unemployment rate did not rise to 4½ percent'))
