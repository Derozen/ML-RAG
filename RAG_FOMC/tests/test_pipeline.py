"""Tests synthétiques : aucune annotation ni performance officielle FOMC."""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag_fomc.chunking import chunk_paragraphs
from rag_fomc.common import Config, read_jsonl, sha256, write_json, write_jsonl
from rag_fomc.evaluation import compare, retrieval_metrics, validate_questions
from rag_fomc.indexing import ARTIFACTS, load_index
from rag_fomc.preprocessing import lexical_tokens, normalize_text
from rag_fomc.retrieval import METHODS, Retriever, reciprocal_rank_fusion, stable_top


class OffsetTokenizer:
    """Tokenizer de test seulement, jamais utilisé en production."""
    def encode(self, text, add_special_tokens=True, **kwargs):
        return list(range(len(re.findall(r"\S+", text)) + (2 if add_special_tokens else 0)))

    def __call__(self, text, **kwargs):
        matches = list(re.finditer(r"\S+", text))
        return {"input_ids": list(range(len(matches))), "offset_mapping": [(m.start(), m.end()) for m in matches]}


def paragraph(doc="FOMC_2024-09-18", text="alpha beta gamma.", position=1, section_id=0):
    return {"doc_id": doc, "meeting_end": doc[5:], "paragraph_id": f"{doc}_P{position:04d}",
            "section_id": section_id, "section": "Synthetic section", "position": position,
            "page": None, "source_url": "https://www.federalreserve.gov/synthetic-test-only", "text": text}


class CoreTests(unittest.TestCase):
    def test_financial_tokens_and_negation(self):
        tokens = lexical_tokens("4.75% 25 basis points did not change 1/2 ½")
        self.assertEqual(tokens, ["4.75%", "25", "basis", "points", "did", "not", "change", "1/2", "½"])

    def test_normalization_preserves_meaning(self):
        self.assertEqual(normalize_text("did\nnot\u00a0 change  4¾%"), "did not change 4¾%")

    def test_invalid_config(self):
        for kw in ({"overlap_tokens": 400}, {"top_k": 0}, {"chunk_tokens": 512}, {"repetitions": 0}):
            with self.assertRaises(ValueError):
                Config(**kw)

    def test_chunk_coverage_overlap_and_tail(self):
        text = " ".join(f"word{i}" for i in range(103))
        config = Config(chunk_tokens=20, overlap_tokens=4, max_model_tokens=64)
        chunks = chunk_paragraphs([paragraph(text=text)], OffsetTokenizer(), config)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[-1]["section_token_end"], 103)
        self.assertLess(chunks[-1]["token_count"], 20)
        covered = set()
        for c in chunks:
            self.assertEqual(c["text"], text[c["section_char_start"]:c["section_char_end"]])
            self.assertLessEqual(c["model_token_count"], 64)
            covered.update(range(c["section_token_start"], c["section_token_end"]))
        self.assertEqual(covered, set(range(103)))
        for a, b in zip(chunks, chunks[1:]):
            self.assertEqual(a["section_token_end"] - b["section_token_start"], 4)

    def test_chunks_never_cross_documents_or_sections(self):
        paragraphs = [paragraph(), paragraph(position=2, section_id=1), paragraph(doc="FOMC_2024-11-07")]
        chunks = chunk_paragraphs(paragraphs, OffsetTokenizer(), Config())
        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(len(c["paragraph_ids"]) == 1 for c in chunks))
        self.assertTrue(all(c["page_start"] is None for c in chunks))
        self.assertEqual(chunks, chunk_paragraphs(paragraphs, OffsetTokenizer(), Config()))

    def test_adjacent_paragraph_provenance(self):
        chunks = chunk_paragraphs([paragraph(), paragraph(position=2)], OffsetTokenizer(), Config())
        self.assertEqual(len(chunks[0]["paragraph_ids"]), 2)

    def test_stable_ties(self):
        self.assertEqual([i for i, _ in stable_top([0.2, 0.4, 0.4], 20)], [1, 2, 0])

    def test_invalid_scores(self):
        with self.assertRaises(ValueError):
            stable_top([float("nan")], 20)

    def test_rrf_formula_and_deduplication(self):
        a = [(0, 9), (1, 8)]
        b = [(2, 5), (1, 4), (0, 3)]
        scores = dict(reciprocal_rank_fusion([a, b], 60, 20))
        self.assertAlmostEqual(scores[0], 1 / 61 + 1 / 63)
        self.assertAlmostEqual(scores[1], 2 / 62)
        self.assertEqual(len(scores), 3)
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([[(0, 1), (0, 1)]], 60, 20)

    def test_metrics_partial_comparison(self):
        e = [{"chunk_ids": ["sep"]}, {"chunk_ids": ["nov"]}]
        m = retrieval_metrics(["x", "y", "sep"], e, 20)
        self.assertEqual(m["recall"], 0.5)
        self.assertAlmostEqual(m["mrr"], 1 / 3)
        self.assertEqual(m["all_evidence"], 0)

    def test_alternative_evidence_not_double_counted(self):
        e = [{"chunk_ids": ["sep1", "sep2"]}, {"chunk_ids": ["nov"]}]
        m = retrieval_metrics(["sep1", "sep2"], e, 20)
        self.assertEqual(m["evidence_coverage"], 0.5)
        self.assertEqual(m["recall"], 2 / 3)
        self.assertEqual(m["all_evidence"], 0)

    def test_no_hit_and_cutoff(self):
        m = retrieval_metrics(["x", "hit"], [{"chunk_ids": ["hit"]}], 1)
        self.assertEqual(m["mrr"], 0)
        self.assertEqual(m["recall"], 0)

    def test_unanswerable_has_no_recall(self):
        with self.assertRaises(ValueError):
            retrieval_metrics(["x"], [], 20)

    @unittest.skipUnless(importlib.util.find_spec("bs4"), "beautifulsoup4 absent")
    def test_html_excludes_navigation_and_keeps_table(self):
        from rag_fomc.ingestion import extract_html
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.html"
            path.write_text('<nav>outside</nav><div id="article"><nav>menu</nav><h2>Decision</h2>'
                '<p>did not change 4.75%</p><table><tr><td>25</td><td>basis points</td></tr></table></div>', encoding="utf-8")
            rows = list(extract_html(path, "#article"))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][3], "did not change 4.75%")
            self.assertTrue(rows[1][-1])
            self.assertNotIn("menu", str(rows))

    @unittest.skipUnless(importlib.util.find_spec("pymupdf"), "pymupdf absent")
    def test_pdf_page_provenance_and_empty_page(self):
        import pymupdf
        from rag_fomc.ingestion import extract_pdf
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "did not change 4.75%")
            document.save(path)
            document.close()
            rows = list(extract_pdf(path, []))
            self.assertEqual(rows[0][2], 1)
            self.assertIn("did not change 4.75%", rows[0][3])
            blank = Path(tmp) / "empty.pdf"
            document = pymupdf.open()
            document.new_page()
            document.save(blank)
            document.close()
            with self.assertRaisesRegex(ValueError, "vide"):
                list(extract_pdf(blank, []))


class IndexFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "indexes").mkdir()
        self.chunks = []
        for i, text in enumerate(("alpha not changed 4.75%", "beta 25 basis points", "gamma employment"), 1):
            p = paragraph(text=text)
            self.chunks.append({**p, "chunk_id": f"{p['doc_id']}_C{i:04d}", "search_text": text,
                "paragraph_ids": [p["paragraph_id"]], "token_count": len(text.split()),
                "page_start": None, "page_end": None})
        write_jsonl(self.root / "data/processed/chunks.jsonl", self.chunks)
        write_jsonl(self.root / "data/processed/paragraphs.jsonl", [paragraph()])
        write_json(self.root / "data/processed/chunking.json", {"synthetic": True})
        np.save(self.root / "indexes/vectors.npy", np.eye(3, dtype=np.float32), allow_pickle=False)
        write_json(self.root / "indexes/chunk_ids.json", [c["chunk_id"] for c in self.chunks])
        write_jsonl(self.root / "indexes/bm25_tokens.jsonl", [
            {"chunk_id": c["chunk_id"], "tokens": lexical_tokens(c["search_text"])} for c in self.chunks])
        self.metadata = {"schema_version": 1, "config": Config().to_dict(), "model_revision": "synthetic-only",
            "chunks_sha256": sha256(self.root / "data/processed/chunks.jsonl"),
            "paragraphs_sha256": sha256(self.root / "data/processed/paragraphs.jsonl"),
            "chunking_sha256": sha256(self.root / "data/processed/chunking.json"), "shape": [3, 3],
            "artifact_sha256": {f: sha256(self.root / "indexes" / f) for f in ARTIFACTS}}
        write_json(self.root / "indexes/metadata.json", self.metadata)

    def tearDown(self):
        self.tmp.cleanup()

    def question(self):
        return {"qid": "Q1", "family_id": "F1", "question": "alpha", "type": "factual", "split": "dev",
                "answerable": True, "validated": True, "reference_answer": "synthetic answer",
                "evidence": [{"evidence_id": "E1", "doc_id": self.chunks[0]["doc_id"],
                              "quote": "alpha not changed", "chunk_ids": [self.chunks[0]["chunk_id"]]}]}

    def test_reload_alignment(self):
        _, chunks, vectors, _ = load_index(self.root)
        self.assertEqual(len(chunks), vectors.shape[0])

    def test_stale_chunks_rejected(self):
        write_jsonl(self.root / "data/processed/chunks.jsonl", self.chunks[::-1])
        with self.assertRaisesRegex(ValueError, "périmé"):
            load_index(self.root)

    def test_corrupt_vectors_rejected(self):
        (self.root / "indexes/vectors.npy").write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "corrompu"):
            load_index(self.root)

    def test_reextracted_paragraphs_rejected(self):
        write_jsonl(self.root / "data/processed/paragraphs.jsonl", [paragraph(text="updated source")])
        with self.assertRaisesRegex(ValueError, "réextraits"):
            load_index(self.root)

    def test_unknown_evidence_rejected(self):
        q = self.question()
        q["evidence"][0]["chunk_ids"] = ["missing"]
        with self.assertRaises(ValueError):
            validate_questions([q], self.chunks, True)

    def test_unvalidated_question_rejected(self):
        q = self.question()
        q["validated"] = False
        with self.assertRaises(ValueError):
            validate_questions([q], self.chunks, True)

    def test_family_leakage_rejected(self):
        a, b = self.question(), self.question()
        b.update(qid="Q2", split="test")
        with self.assertRaisesRegex(ValueError, "Fuite"):
            validate_questions([a, b], self.chunks, True)

    def test_equivalent_quotes_by_chunk(self):
        q = self.question()
        e = q["evidence"][0]
        e["chunk_ids"].append(self.chunks[1]["chunk_id"])
        e["quotes_by_chunk"] = {self.chunks[1]["chunk_id"]: "25 basis points"}
        validate_questions([q], self.chunks, True)
        e["quotes_by_chunk"][self.chunks[1]["chunk_id"]] = "invented quote"
        with self.assertRaises(ValueError):
            validate_questions([q], self.chunks, True)

    def test_cluster_bootstrap_direction(self):
        from rag_fomc.comparison import paired_intervals
        questions = [self.question()]
        metrics = [{"qid": "Q1", "method": method,
                    **{name: (0 if method == "bm25" else 1) for name in
                       ("recall", "mrr", "evidence_coverage", "all_evidence")}} for method in METHODS]
        rows = paired_intervals(metrics, questions, seed=42, samples=100)
        row = next(r for r in rows if r["method_a"] == "bm25" and r["method_b"] == "dense" and r["metric"] == "recall")
        self.assertEqual(row["delta_b_minus_a"], 1)
        self.assertEqual(row["ci95_low"], 1)

    def test_benchmark_rejects_questions_changed_after_validation(self):
        from types import SimpleNamespace
        path = self.root / "evaluation/questions.jsonl"
        q = self.question()
        write_jsonl(path, [q])
        write_json(self.root / "evaluation/annotations.json", {
            "chunks_sha256": self.metadata["chunks_sha256"], "questions_sha256": sha256(path)})
        q["question"] = "a different but structurally valid question"
        write_jsonl(path, [q])
        retriever = SimpleNamespace(chunks=self.chunks, metadata=self.metadata)
        with self.assertRaisesRegex(ValueError, "Questions modifiées"):
            compare(self.root, retriever, path, "dev", self.root / "results/changed")

    def test_benchmark_requires_question_validation_fingerprint(self):
        from types import SimpleNamespace
        path = self.root / "evaluation/questions.jsonl"
        write_jsonl(path, [self.question()])
        write_json(self.root / "evaluation/annotations.json", {"chunks_sha256": self.metadata["chunks_sha256"]})
        retriever = SimpleNamespace(chunks=self.chunks, metadata=self.metadata)
        with self.assertRaisesRegex(ValueError, "empreinte absente"):
            compare(self.root, retriever, path, "dev", self.root / "results/missing")

    @unittest.skipUnless(importlib.util.find_spec("rank_bm25"), "rank-bm25 absent")
    def test_benchmark_end_to_end_with_synthetic_encoder(self):
        class SyntheticEncoder:
            def __init__(self, *args):
                pass

            def encode(self, texts, prefix):
                # Test de plomberie uniquement, pas un modèle sémantique.
                return np.asarray([[1, 0, 0] for _ in texts], dtype=np.float32)

        with patch("rag_fomc.retrieval.Encoder", SyntheticEncoder):
            retriever = Retriever(self.root)
            for method in METHODS:
                results, seconds, diagnostics = retriever.search("alpha", method)
                self.assertEqual(results[0]["chunk_id"], self.chunks[0]["chunk_id"])
                self.assertEqual(len(results), 3)
                self.assertGreaterEqual(seconds, 0)
            _, _, diag = retriever.search("zzzzzz", "bm25")
            self.assertTrue(diag["no_lexical_match"])
            q = self.question()
            unanswered = {"qid": "Q2", "family_id": "F2", "question": "zzzzzz", "type": "unanswerable",
                "split": "dev", "answerable": False, "validated": True,
                "evidence": [], "absence_reason": "Synthetic fixture has no answer"}
            write_jsonl(self.root / "evaluation/questions.jsonl", [q, unanswered])
            write_json(self.root / "evaluation/annotations.json", {"chunks_sha256": self.metadata["chunks_sha256"],
                       "questions_sha256": sha256(self.root / "evaluation/questions.jsonl")})
            output = self.root / "results/test"
            summary = compare(self.root, retriever, self.root / "evaluation/questions.jsonl", "dev", output, 2)
            self.assertEqual(len([s for s in summary if s["type"] == "ALL"]), 3)
            self.assertEqual(len(read_jsonl(output / "rankings.jsonl")), 18)
            self.assertEqual(len(read_jsonl(output / "unanswerable_review.jsonl")), 3)
            for s in summary:
                if s["type"] == "ALL":
                    self.assertEqual(s["recall"], 1)
                    self.assertEqual(s["answerable_questions"], 1)


if __name__ == "__main__":
    unittest.main()
