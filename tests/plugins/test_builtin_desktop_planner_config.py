import tempfile
import time
import unittest
from pathlib import Path

from plugins.builtin_desktop.planner import BuiltinDesktopPlanner


class TestBuiltinDesktopPlannerConfig(unittest.TestCase):
    def test_tidy_preview_uses_config_rules(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Desktop"
            staging = Path(td) / "Desktop_Staging"
            root.mkdir(parents=True)

            cfg_path = Path(td) / "desktop_rules.yml"
            cfg_path.write_text(
                "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{root}"',
                        f'  staging_dir: "{staging}"',
                        "",
                        "folders:",
                        '  images: "Images"',
                        '  misc: "Misc"',
                        "",
                        "rules:",
                        '  - id: "r_images"',
                        "    match:",
                        "      any:",
                        '        - ext_in: ["jpg"]',
                        "    action:",
                        '      move_to: "images"',
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: "misc"',
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        '  ignore_patterns: ["*.tmp"]',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            planner = BuiltinDesktopPlanner()
            now = int(time.time())
            intent = {
                "intent_id": "desktop.tidy.preview",
                "params": {
                    "config_path": str(cfg_path),
                    "entries": [
                        {"name": "a.tmp", "is_file": True, "is_dir": False, "mtime": now},
                        {"name": "pic.jpg", "is_file": True, "is_dir": False, "mtime": now},
                        {"name": "doc.pdf", "is_file": True, "is_dir": False, "mtime": now},
                    ],
                },
                "scope": {"fs_roots": [str(root), str(staging)], "allow_network": False},
                "context": {"source": "test"},
            }

            plan = planner.plan(intent)
            self.assertEqual(plan["plan_id"], "plan_desktop_tidy_preview_001")
            move_steps = [s for s in plan["steps"] if s.get("tool", {}).get("tool_id") == "fs.move"]
            self.assertEqual(len(move_steps), 2)
            tos = [s["tool"]["args"]["to"] for s in move_steps]
            self.assertIn(f"{staging}/Images/pic.jpg", tos)
            self.assertIn(f"{staging}/Misc/doc.pdf", tos)

