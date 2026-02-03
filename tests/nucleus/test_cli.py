import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from nucleus.cli.nuc import main as nuc_main


class TestNucCli(unittest.TestCase):
    def test_list_tools_outputs_json(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = nuc_main(["list-tools", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        tool_ids = [t["tool_id"] for t in data]
        self.assertIn("fs.list", tool_ids)
        self.assertIn("fs.move", tool_ids)

    def test_show_trace_outputs_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.jsonl"
            p.write_text(
                "\n".join(
                    [
                        json.dumps({"ts": "2026-02-03T00:00:00Z", "run_id": "r1", "event_type": "intent_received"}),
                        json.dumps({"ts": "2026-02-03T00:00:01Z", "run_id": "r1", "event_type": "run_finished"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["show-trace", "--trace", str(p), "--tail", "1"])
            self.assertEqual(rc, 0)
            lines = [l for l in buf.getvalue().splitlines() if l.strip()]
            self.assertEqual(len(lines), 1)
            obj = json.loads(lines[0])
            self.assertEqual(obj["event_type"], "run_finished")

    def test_list_intents_includes_desktop_tidy(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = nuc_main(["list-intents", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        intent_ids = [it["intent_id"] for it in data]
        self.assertIn("desktop.tidy.run", intent_ids)

    def test_desktop_preview_outputs_plan_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            staging = td_path / "Desktop_Staging"
            root.mkdir(parents=True)
            (root / "pic.jpg").write_text("x", encoding="utf-8")
            (root / "a.tmp").write_text("x", encoding="utf-8")

            cfg_path = td_path / "desktop_rules.yml"
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

            trace_path = td_path / "trace.jsonl"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["desktop", "preview", "--config-path", str(cfg_path), "--trace", str(trace_path), "--run-id", "run_test_preview_1"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["plan_id"], "plan_desktop_tidy_preview_001")
            self.assertTrue(trace_path.exists())

    def test_desktop_restore_moves_file_back(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            staging = td_path / "Desktop_Staging"
            root.mkdir(parents=True)
            (staging / "Images").mkdir(parents=True)
            (staging / "Images" / "pic.jpg").write_text("x", encoding="utf-8")

            cfg_path = td_path / "desktop_rules.yml"
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
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: "images"',
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            trace_path = td_path / "trace.jsonl"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["desktop", "restore", "--config-path", str(cfg_path), "--trace", str(trace_path), "--run-id", "run_test_restore_1"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["plan_id"], "plan_desktop_tidy_restore_001")
            self.assertTrue((root / "pic.jpg").exists())
            self.assertFalse((staging / "Images" / "pic.jpg").exists())

    def test_init_scaffolds_app_dir_non_interactive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "init",
                        "--app-id",
                        "my_app",
                        "--name",
                        "My App",
                        "--target-dir",
                        str(td_path),
                        "--no-input",
                    ]
                )
            self.assertEqual(rc, 0)
            app_dir = td_path / "my_app"
            self.assertTrue((app_dir / "pyproject.toml").exists())
            self.assertTrue((app_dir / "specs" / "INDEX.md").exists())
            self.assertTrue((app_dir / "ai" / "README.md").exists())
            self.assertTrue((app_dir / "ai" / "memory.md").exists())

    def test_memory_stub_prints_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tr = td_path / "t.txt"
            tr.write_text("see /workspaces/nucleus/README.md\n$ python -m unittest -q\n", encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["memory-stub", "--transcript", str(tr)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("Transcript", out)
            self.assertIn("README.md", out)


if __name__ == "__main__":
    unittest.main()

