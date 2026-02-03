import tempfile
import unittest
from pathlib import Path

from tools.fs.move import run as fs_move


class TestFsMoveConflict(unittest.TestCase):
    def test_on_conflict_skip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "a.txt"
            dst = Path(td) / "b.txt"
            src.write_text("A", encoding="utf-8")
            dst.write_text("B", encoding="utf-8")

            out = fs_move({"from": str(src), "to": str(dst), "on_conflict": "skip"}, dry_run=False)
            self.assertTrue(out.get("skipped"))
            self.assertTrue(src.exists())
            self.assertTrue(dst.exists())

    def test_on_conflict_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "a.txt"
            dst = Path(td) / "b.txt"
            src.write_text("A", encoding="utf-8")
            dst.write_text("B", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                fs_move({"from": str(src), "to": str(dst), "on_conflict": "error"}, dry_run=False)

    def test_on_conflict_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "a.txt"
            dst = Path(td) / "b.txt"
            src.write_text("A", encoding="utf-8")
            dst.write_text("B", encoding="utf-8")

            out = fs_move({"from": str(src), "to": str(dst), "on_conflict": "overwrite"}, dry_run=False)
            self.assertFalse(out.get("skipped"))
            self.assertFalse(src.exists())
            self.assertTrue(dst.exists())
            self.assertEqual(dst.read_text(encoding="utf-8"), "A")

    def test_dry_run_does_not_error_when_source_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "missing.txt"
            dst = Path(td) / "b.txt"
            out = fs_move({"from": str(src), "to": str(dst)}, dry_run=True)
            self.assertTrue(out.get("dry_run"))

