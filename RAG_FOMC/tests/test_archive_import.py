"""Régressions de l'import et des mises en page observées dans les PDF fournis."""
from collections import Counter
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag_fomc.archive_import import import_archive, meeting_dates
from rag_fomc.pdf_layout import paragraph_groups, reading_order, running_header

ROOT = Path(__file__).resolve().parents[1]


def line(text, x, y, x_end, block=0, size=11, bold=0):
    return {"text": text, "bbox": (x, y, x_end, y + 12), "block": block, "size": size, "bold": bold}


class LayoutTests(unittest.TestCase):
    def test_two_columns_not_interleaved(self):
        rows = []
        for i in range(8):
            rows += [line(f"left{i}", 50, 80 + i * 14, 280), line(f"right{i}", 330, 80 + i * 14, 560)]
        ordered, two_columns = reading_order(rows, 612)
        self.assertTrue(two_columns)
        self.assertEqual([r["text"] for r in ordered], [f"left{i}" for i in range(8)] + [f"right{i}" for i in range(8)])

    def test_full_width_heading_before_both_columns(self):
        rows = [line("Document title", 150, 60, 460)]
        for i in range(8):
            rows += [line(f"L{i}", 50, 100 + i * 14, 280), line(f"R{i}", 330, 100 + i * 14, 560)]
        ordered, _ = reading_order(rows, 612)
        self.assertEqual(ordered[0]["text"], "Document title")
        self.assertEqual(len(ordered), len(rows))

    def test_line_per_block_reassembled_into_paragraphs(self):
        rows = [line("first line", 90, 100, 520, block=1, size=10),
                line("continues here.", 90, 117, 300, block=2, size=10),
                line("New paragraph.", 90, 141, 520, block=3, size=10)]
        groups = list(paragraph_groups(rows, 612, False))
        self.assertEqual([text for _, text in groups], ["first line continues here.", "New paragraph."])

    def test_heading_and_body_in_same_block_do_not_drop_body(self):
        rows = [line("Notation Vote", 50, 100, 150, bold=1),
                line("By notation vote the Committee approved", 50, 114, 280),
                line("the minutes of the previous meeting.", 50, 128, 280)]
        groups = list(paragraph_groups(rows, 612, False))
        self.assertEqual(groups[0], (True, "Notation Vote"))
        self.assertIn("the minutes of the previous meeting.", groups[1][1])

    def test_running_header_rule_respects_body_numbers(self):
        self.assertTrue(running_header("Minutes of the Federal Open Market Committee 3", 45))
        self.assertTrue(running_header("Page 3", 40))
        self.assertFalse(running_header("25", 200))
        self.assertFalse(running_header("Minutes of the Federal Open Market Committee", 100))


class ImportTests(unittest.TestCase):
    def test_cross_month_and_title_fallback(self):
        self.assertEqual(meeting_dates("FOMC Minutes January 31–February 1, 2023", "", date(2023, 2, 1)),
                         (date(2023, 1, 31), date(2023, 2, 1)))
        self.assertEqual(meeting_dates("", "Minutes April 27–28, 2021", date(2021, 4, 28)),
                         (date(2021, 4, 27), date(2021, 4, 28)))

    def test_date_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            meeting_dates("January 26–27, 2021", "", date(2021, 1, 28))

    def test_zip_traversal_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../outside.py", "raise Exception('not executed')")
            with self.assertRaisesRegex(ValueError, "Chemin dangereux"):
                import_archive(archive, Path(tmp) / "project")
            self.assertFalse((Path(tmp) / "outside.py").exists())

    @unittest.skipUnless((ROOT / "data/raw/minutes/fomcminutes20210127.pdf").is_file(), "PDF fourni non présent")
    def test_real_archive_subset_import_is_idempotent_and_excludes_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "subset.zip"
            names = ["minutes/fomcminutes20210127.pdf", "minutes/fomcminutes20210428.pdf",
                     "minutes/fomcminutes20260128.pdf", "statements/monetary20210127a1.pdf"]
            with zipfile.ZipFile(archive, "w") as z:
                for name in names:
                    z.write(ROOT / "data/raw" / name, f"ML-RAG-master/utils/TxtExtraction/TextsData/{name}")
                z.writestr("ML-RAG-master/.env", "TEST_SECRET=must_not_be_copied")
                z.writestr("ML-RAG-master/utils/example.py", "# reference source, never executed\n")
            destination = Path(tmp) / "project"
            first = import_archive(archive, destination)
            second = import_archive(archive, destination)
            self.assertEqual(first, second)
            self.assertEqual(first["included_minutes"], 2)
            self.assertEqual(first["pdf_count"], 4)
            self.assertEqual(first["excluded_by_reason"]["excluded_meeting_year"], 1)
            self.assertFalse(any(destination.rglob(".env")))
            self.assertEqual((destination / "data/raw/minutes/fomcminutes20210127.pdf").read_bytes(),
                             (ROOT / "data/raw/minutes/fomcminutes20210127.pdf").read_bytes())


if __name__ == "__main__":
    unittest.main()
