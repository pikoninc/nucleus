import os
import tempfile
import time
import unittest
from pathlib import Path

from plugins.builtin_desktop.planner import BuiltinDesktopPlanner
from nucleus.core.errors import ValidationError


class TestBuiltinDesktopPlannerConfig(unittest.TestCase):
    def test_tidy_preview_uses_config_rules(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            staging = td_path / "Desktop_Aux"
            docs = td_path / "Documents"
            pics = td_path / "Pictures"
            downloads = td_path / "Downloads"
            root.mkdir(parents=True)
            docs.mkdir(parents=True)
            pics.mkdir(parents=True)
            downloads.mkdir(parents=True)

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
                        f'  images: "{pics}"',
                        f'  documents: "{docs}"',
                        f'  downloads: "{downloads}"',
                        "",
                        "rules:",
                        '  - id: "r_images"',
                        "    match:",
                        "      any:",
                        '        - ext_in: ["jpg"]',
                        "    action:",
                        '      move_to: "images"',
                        '  - id: "r_docs"',
                        "    match:",
                        "      any:",
                        '        - ext_in: ["pdf"]',
                        "    action:",
                        '      move_to: "documents"',
                        '  - id: "r_tmp_delete"',
                        "    match:",
                        "      any:",
                        '        - ext_in: ["tmp"]',
                        "    action:",
                        "      delete: true",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: "downloads"',
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
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
                        {"name": "misc.bin", "is_file": True, "is_dir": False, "mtime": now},
                    ],
                },
                "scope": {"fs_roots": [str(root), str(staging), str(docs), str(pics), str(downloads)], "allow_network": False},
                "context": {"source": "test"},
            }

            plan = planner.plan(intent)
            self.assertEqual(plan["plan_id"], "plan_desktop_tidy_preview_001")
            move_steps = [s for s in plan["steps"] if s.get("tool", {}).get("tool_id") == "fs.move"]
            self.assertEqual(len(move_steps), 4)
            tos = [s["tool"]["args"]["to"] for s in move_steps]
            self.assertIn(f"{pics}/pic.jpg", tos)
            self.assertIn(f"{docs}/doc.pdf", tos)
            self.assertIn(f"{downloads}/misc.bin", tos)
            self.assertIn(f"{staging}/ToDelete/a.tmp", tos)

    def test_tidy_preview_scope_check_expands_user_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = td
            try:
                root = Path(td) / "Desktop"
                staging = Path(td) / "Desktop_Aux"
                docs = Path(td) / "Documents"
                root.mkdir(parents=True)
                docs.mkdir(parents=True)

                cfg_path = Path(td) / "desktop_rules.yml"
                cfg_path.write_text(
                    "\n".join(
                        [
                            'version: "0.1"',
                            'plugin: "builtin.desktop"',
                            "",
                            "root:",
                            '  path: "~/Desktop"',
                            '  staging_dir: "~/Desktop_Aux"',
                            "",
                            "folders:",
                            '  documents: "~/Documents"',
                            "",
                            "rules:",
                            '  - id: "r_any"',
                            "    match:",
                            "      any:",
                            '        - ext_in: ["txt"]',
                            "    action:",
                            '      move_to: "documents"',
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
                    "params": {"config_path": str(cfg_path), "entries": [{"name": "a.txt", "is_file": True, "is_dir": False, "mtime": now}]},
                    # fs_roots uses expanded absolute paths; config uses "~".
                    "scope": {"fs_roots": [str(root), str(staging), str(docs)], "allow_network": False},
                    "context": {"source": "test"},
                }

                plan = planner.plan(intent)
                self.assertEqual(plan["plan_id"], "plan_desktop_tidy_preview_001")
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

    def test_tidy_preview_rejects_empty_match(self) -> None:
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
                        '  misc: "Misc"',
                        "",
                        "rules:",
                        '  - id: "r_bad"',
                        "    match: {}",
                        "    action:",
                        '      move_to: "misc"',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            planner = BuiltinDesktopPlanner()
            intent = {
                "intent_id": "desktop.tidy.preview",
                "params": {"config_path": str(cfg_path), "entries": [{"name": "a.txt", "is_file": True, "is_dir": False, "mtime": 0}]},
                "scope": {"fs_roots": [str(root), str(staging)], "allow_network": False},
                "context": {"source": "test"},
            }

            with self.assertRaises(ValidationError) as ctx:
                planner.plan(intent)
            self.assertIn(ctx.exception.code, ("config.schema_invalid", "config.invalid"))

    def test_tidy_preview_rejects_path_traversal_in_folder_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Desktop"
            staging = Path(td) / "Desktop_Aux"
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
                        '  bad: "../escape"',
                        "",
                        "rules:",
                        '  - id: "r_any"',
                        "    match:",
                        "      any:",
                        '        - ext_in: ["txt"]',
                        "    action:",
                        '      move_to: "bad"',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            planner = BuiltinDesktopPlanner()
            intent = {
                "intent_id": "desktop.tidy.preview",
                "params": {"config_path": str(cfg_path), "entries": [{"name": "a.txt", "is_file": True, "is_dir": False, "mtime": 0}]},
                "scope": {"fs_roots": [str(root), str(staging)], "allow_network": False},
                "context": {"source": "test"},
            }

            with self.assertRaises(ValidationError) as ctx:
                planner.plan(intent)
            self.assertIn(ctx.exception.code, ("config.schema_invalid", "config.invalid"))

