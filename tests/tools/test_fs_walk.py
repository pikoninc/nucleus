import tempfile
import unittest
from pathlib import Path

from tools.fs.walk import run as fs_walk


class TestFsWalk(unittest.TestCase):
    def test_walk_lists_files_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("A", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_text("B", encoding="utf-8")

            out = fs_walk({"path": str(root)}, dry_run=True)
            self.assertTrue(out.get("dry_run"))
            entries = out.get("entries", [])
            paths = [e.get("path") for e in entries if isinstance(e, dict)]
            self.assertIn("a.txt", paths)
            self.assertIn("sub/b.txt", paths)

    def test_walk_can_include_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "sub").mkdir()
            out = fs_walk({"path": str(root), "include_dirs": True}, dry_run=True)
            entries = out.get("entries", [])
            dirs = [e.get("path") for e in entries if isinstance(e, dict) and e.get("is_dir")]
            self.assertIn("sub", dirs)

