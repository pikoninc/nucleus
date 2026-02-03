import tempfile
import unittest
from pathlib import Path

from tools.fs.move import run as fs_move


class TestFsMoveSuffixIncrement(unittest.TestCase):
    def test_on_conflict_suffix_increment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "a.txt"
            dst = root / "b.txt"
            dst1 = root / "b(1).txt"
            src.write_text("A", encoding="utf-8")
            dst.write_text("B", encoding="utf-8")

            out = fs_move({"from": str(src), "to": str(dst), "on_conflict": "suffix_increment"}, dry_run=False)
            self.assertFalse(out.get("skipped"))
            self.assertFalse(src.exists())
            self.assertTrue(dst.exists())
            self.assertTrue(dst1.exists())
            self.assertEqual(dst1.read_text(encoding="utf-8"), "A")

