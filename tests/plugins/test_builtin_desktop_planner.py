import unittest

from plugins.builtin_desktop.planner import BuiltinDesktopPlanner


class TestBuiltinDesktopPlannerRules(unittest.TestCase):
    def test_exclude_and_include_dirs_and_overwrite_strategy(self) -> None:
        planner = BuiltinDesktopPlanner()
        intent = {
            "intent_id": "desktop.tidy",
            "params": {
                "target_dir": "~/Desktop",
                "include_dirs": True,
                "exclude": ["*.tmp"],
                "overwrite_strategy": "skip",
                "entries": [
                    {"name": "a.tmp", "is_file": True, "is_dir": False},
                    {"name": "pic.jpg", "is_file": True, "is_dir": False},
                    {"name": "Folder1", "is_file": False, "is_dir": True},
                    {"name": "_Sorted", "is_file": False, "is_dir": True},
                ],
            },
            "scope": {"fs_roots": ["~/Desktop"], "allow_network": False},
            "context": {"source": "test"},
        }

        plan = planner.plan(intent)
        steps = plan["steps"]
        move_steps = [s for s in steps if s.get("tool", {}).get("tool_id") == "fs.move"]

        # a.tmp excluded
        self.assertFalse(any("a.tmp" in (s.get("title") or "") for s in move_steps))

        # pic.jpg should be categorized as Images
        jpg = next((s for s in move_steps if "pic.jpg" in (s.get("title") or "")), None)
        self.assertIsNotNone(jpg)
        self.assertEqual(jpg["tool"]["args"]["on_conflict"], "skip")
        self.assertTrue(str(jpg["tool"]["args"]["to"]).endswith("/_Sorted/Images/pic.jpg"))

        # Folder1 should be moved under Folders when include_dirs=True
        d = next((s for s in move_steps if "Folder1" in (s.get("title") or "")), None)
        self.assertIsNotNone(d)
        self.assertTrue(str(d["tool"]["args"]["to"]).endswith("/_Sorted/Folders/Folder1"))

