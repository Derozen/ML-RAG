"""Completion must cover the source scope exactly and preserve prior decisions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'annotation_tools'))
from complete_editorial_proposal import check_coverage


class CompletionCoverageTests(unittest.TestCase):
    def test_missing_or_out_of_scope_page_is_rejected(self):
        expected = {('Q', 'a#p1'), ('Q', 'a#p2')}
        with self.assertRaises(ValueError):
            check_coverage(expected, {('Q', 'a#p1'): 2}, {})
        with self.assertRaises(ValueError):
            check_coverage(expected, {('Q', 'a#p1'): 2}, {('Q', 'b#p2'): 0})

    def test_prior_grade_cannot_be_silently_overridden(self):
        with self.assertRaises(ValueError):
            check_coverage({('Q', 'a#p1')}, {('Q', 'a#p1'): 2}, {('Q', 'a#p1'): 0})

    def test_exact_disjoint_completion_passes(self):
        check_coverage({('Q', 'a#p1'), ('Q', 'a#p2')},
                       {('Q', 'a#p1'): 2}, {('Q', 'a#p2'): 0})
