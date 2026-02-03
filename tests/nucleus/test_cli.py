import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

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
        self.assertIn("desktop.tidy", intent_ids)
        self.assertIn("desktop.tidy.run", intent_ids)

    def test_cli_loads_env_file_from_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "env").write_text('OPENAI_API_KEY="test_key_from_env_file"\n', encoding="utf-8")

            old_cwd = os.getcwd()
            old_key = os.environ.get("OPENAI_API_KEY")
            try:
                if "OPENAI_API_KEY" in os.environ:
                    os.environ.pop("OPENAI_API_KEY", None)
                os.chdir(td)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = nuc_main(["list-tools", "--json"])
                self.assertEqual(rc, 0)
                self.assertEqual(os.environ.get("OPENAI_API_KEY"), "test_key_from_env_file")
            finally:
                os.chdir(old_cwd)
                if old_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = old_key

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

    def test_desktop_run_moves_files_into_staging(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            staging = td_path / "Desktop_Staging"
            root.mkdir(parents=True)
            (root / "pic.jpg").write_text("x", encoding="utf-8")
            (root / "doc.pdf").write_text("x", encoding="utf-8")
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
                        '  documents: "Documents"',
                        '  misc: "Misc"',
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
                rc = nuc_main(["desktop", "run", "--config-path", str(cfg_path), "--trace", str(trace_path), "--run-id", "run_test_run_1"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["plan_id"], "plan_desktop_tidy_run_001")
            self.assertTrue((staging / "Images" / "pic.jpg").exists())
            self.assertTrue((staging / "Documents" / "doc.pdf").exists())
            self.assertFalse((root / "pic.jpg").exists())
            self.assertFalse((root / "doc.pdf").exists())
            # ignored
            self.assertTrue((root / "a.tmp").exists())

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

    def test_desktop_ai_first_run_creates_config_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            root.mkdir(parents=True)
            (root / "pic.jpg").write_text("x", encoding="utf-8")

            xdg = td_path / "xdg"
            trace_path = td_path / "trace.jsonl"

            # First run: config doesn't exist -> wizard prompts and writes it, then runs tidy.run chosen by stub provider.
            inputs = iter(
                [
                    "y",  # create config
                    str(root),  # root path
                    "",  # staging dir default (<root>_Staging)
                ]
            )

            buf = io.StringIO()
            with (
                patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg)}, clear=False),
                patch("builtins.input", side_effect=lambda _prompt: next(inputs)),
                redirect_stdout(buf),
            ):
                rc = nuc_main(
                    [
                        "desktop",
                        "ai",
                        "--text",
                        "デスクトップを実行で整理して",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsIntentProvider",
                        "--model",
                        "desktop.tidy.run",
                        "--trace",
                        str(trace_path),
                        "--run-id",
                        "run_test_ai_1",
                    ]
                )
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["plan_id"], "plan_desktop_tidy_run_001")

            # Config created at XDG default path.
            cfg_path = xdg / "nucleus" / "desktop_rules.yml"
            self.assertTrue(cfg_path.exists())

            # File moved into staging.
            staging = td_path / "Desktop_Staging"
            self.assertTrue((staging / "Images" / "pic.jpg").exists())
            self.assertFalse((root / "pic.jpg").exists())

    def test_alfred_emits_intent_from_query(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            staging = td_path / "Desktop_Staging"
            root.mkdir(parents=True)

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
                        '  misc: "Misc"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: "misc"',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["alfred", "--query", f"tidy preview {cfg_path}"])
            self.assertEqual(rc, 0)
            obj = json.loads(buf.getvalue())
            self.assertEqual(obj["intent_id"], "desktop.tidy.preview")
            self.assertEqual(obj["params"]["config_path"], str(cfg_path))
            self.assertEqual(obj["context"]["source"], "alfred")
            self.assertEqual(set(obj["scope"]["fs_roots"]), {str(root), str(staging)})

    def test_alfred_emits_legacy_desktop_tidy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            root.mkdir(parents=True)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["alfred", "--query", f"tidy legacy {root}"])
            self.assertEqual(rc, 0)
            obj = json.loads(buf.getvalue())
            self.assertEqual(obj["intent_id"], "desktop.tidy")
            self.assertEqual(obj["params"]["target_dir"], str(root))
            self.assertEqual(obj["context"]["source"], "alfred")
            self.assertEqual(set(obj["scope"]["fs_roots"]), {str(root), f"{root}/_Sorted"})

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

    def test_intake_requires_allow_network_flag(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = nuc_main(["intake", "--text", "hello"])
        self.assertEqual(rc, 2)
        self.assertIn("intake.network_denied", buf.getvalue())

    def test_intake_missing_api_key_is_reported(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = nuc_main(["intake", "--text", "hello", "--allow-network-intake"])
        self.assertEqual(rc, 1)
        out = buf.getvalue()
        self.assertIn("intake.missing_api_key", out)

    def test_intake_can_use_non_openai_provider(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = nuc_main(
                [
                    "intake",
                    "--text",
                    "hello",
                    "--allow-network-intake",
                    "--provider",
                    "nucleus.intake.testing:FirstAllowedIntentProvider",
                    "--model",
                    "stub",
                ]
            )
        self.assertEqual(rc, 0)
        obj = json.loads(buf.getvalue())
        self.assertIn("intent_id", obj)


if __name__ == "__main__":
    unittest.main()

