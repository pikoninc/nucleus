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
    def setUp(self) -> None:
        self._old_disable_dotenv = os.environ.get("NUCLEUS_DISABLE_DOTENV")
        os.environ["NUCLEUS_DISABLE_DOTENV"] = "1"

    def tearDown(self) -> None:
        if self._old_disable_dotenv is None:
            os.environ.pop("NUCLEUS_DISABLE_DOTENV", None)
        else:
            os.environ["NUCLEUS_DISABLE_DOTENV"] = self._old_disable_dotenv

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
        self.assertIn("desktop.tidy.preview", intent_ids)

    def test_cli_loads_env_file_from_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "env").write_text('OPENAI_API_KEY="test_key_from_env_file"\n', encoding="utf-8")

            old_cwd = os.getcwd()
            old_key = os.environ.get("OPENAI_API_KEY")
            try:
                if "OPENAI_API_KEY" in os.environ:
                    os.environ.pop("OPENAI_API_KEY", None)
                # Enable dotenv loading for this test only.
                old_disable = os.environ.get("NUCLEUS_DISABLE_DOTENV")
                os.environ.pop("NUCLEUS_DISABLE_DOTENV", None)
                os.chdir(td)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = nuc_main(["list-tools", "--json"])
                self.assertEqual(rc, 0)
                self.assertEqual(os.environ.get("OPENAI_API_KEY"), "test_key_from_env_file")
            finally:
                os.chdir(old_cwd)
                if old_disable is None:
                    os.environ["NUCLEUS_DISABLE_DOTENV"] = "1"
                else:
                    os.environ["NUCLEUS_DISABLE_DOTENV"] = old_disable
                if old_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = old_key

    def test_desktop_preview_outputs_plan_id(self) -> None:
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
                        f'  images: "{pics}"',
                        f'  downloads: "{downloads}"',
                        "",
                        "rules:",
                        '  - id: "r_images"',
                        "    match:",
                        "      any:",
                        '        - ext_in: ["jpg"]',
                        "    action:",
                        '      move_to: "images"',
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

            trace_path = td_path / "trace.jsonl"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["desktop", "preview", "--config-path", str(cfg_path), "--trace", str(trace_path), "--run-id", "run_test_preview_1"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["plan_id"], "plan_desktop_tidy_preview_001")
            self.assertTrue(trace_path.exists())
            # dry-run: should not move files
            self.assertTrue((root / "pic.jpg").exists())
            self.assertTrue((root / "a.tmp").exists())

    def test_desktop_run_moves_files_to_dest_and_todelete(self) -> None:
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

            trace_path = td_path / "trace.jsonl"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["desktop", "run", "--config-path", str(cfg_path), "--trace", str(trace_path), "--run-id", "run_test_run_1"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["plan_id"], "plan_desktop_tidy_run_001")
            self.assertTrue((pics / "pic.jpg").exists())
            self.assertTrue((docs / "doc.pdf").exists())
            self.assertFalse((root / "pic.jpg").exists())
            self.assertFalse((root / "doc.pdf").exists())
            self.assertTrue((staging / "ToDelete" / "a.tmp").exists())
            self.assertFalse((root / "a.tmp").exists())

    def test_desktop_ai_first_run_creates_config_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            root.mkdir(parents=True)
            (root / "pic.jpg").write_text("x", encoding="utf-8")

            xdg = td_path / "xdg"
            trace_path = td_path / "trace.jsonl"

            docs = td_path / "Documents"
            pics = td_path / "Pictures"
            docs.mkdir(parents=True)
            pics.mkdir(parents=True)

            cfg_path = xdg / "nucleus" / "desktop_rules.yml"

            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{root}"',
                        f'  staging_dir: "{root}_Aux"',
                        "",
                        "folders:",
                        f'  images: "{pics}"',
                        f'  downloads: "{docs}"',
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
                        '    move_to: "downloads"',
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with (
                patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg)}, clear=False),
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
                        "--configure-provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--configure-model",
                        model_json,
                        "--source-root",
                        str(root),
                        "--dest-root",
                        str(docs),
                        "--dest-root",
                        str(pics),
                        "--config-path",
                        str(cfg_path),
                        "--trace",
                        str(trace_path),
                        "--run-id",
                        "run_test_ai_1",
                    ]
                )
            self.assertEqual(rc, 0)
            # desktop ai bootstrap prints YAML + status text before the final pretty-printed JSON.
            # Extract the JSON object containing "plan_id" from the full output.
            txt = buf.getvalue()
            dec = json.JSONDecoder()
            out_obj = None
            pid_idx = txt.rfind('"plan_id"')
            self.assertGreaterEqual(pid_idx, 0)
            start = txt.rfind("{", 0, pid_idx)
            self.assertGreaterEqual(start, 0)
            try:
                obj, _end = dec.raw_decode(txt[start:])
            except Exception as e:  # noqa: BLE001
                raise AssertionError(f"Failed to parse JSON output: {e!r}") from e
            if isinstance(obj, dict):
                out_obj = obj
            self.assertIsNotNone(out_obj)
            self.assertEqual(out_obj["plan_id"], "plan_desktop_tidy_run_001")
            self.assertTrue(cfg_path.exists())
            self.assertTrue((pics / "pic.jpg").exists())
            self.assertFalse((root / "pic.jpg").exists())

    def test_desktop_ai_migrates_incompatible_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            root.mkdir(parents=True)
            (root / "pic.jpg").write_text("x", encoding="utf-8")

            docs = td_path / "Documents"
            pics = td_path / "Pictures"
            docs.mkdir(parents=True)
            pics.mkdir(parents=True)

            xdg = td_path / "xdg"
            cfg_path = xdg / "nucleus" / "desktop_rules.yml"
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            # Old-style incompatible config (folders values are relative names)
            cfg_path.write_text(
                "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{root}"',
                        f'  staging_dir: "{root}_Aux"',
                        "",
                        "folders:",
                        '  screenshots: "Screenshots"',
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

            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: \"{root}\"',
                        f'  staging_dir: \"{root}_Aux\"',
                        "",
                        "folders:",
                        f'  images: \"{pics}\"',
                        f'  downloads: \"{docs}\"',
                        "",
                        "rules:",
                        '  - id: \"r_images\"',
                        "    match:",
                        "      any:",
                        '        - ext_in: [\"jpg\"]',
                        "    action:",
                        '      move_to: \"images\"',
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: \"downloads\"',
                        "",
                        "safety:",
                        '  collision_strategy: \"suffix_increment\"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            trace_path = td_path / "trace.jsonl"
            buf = io.StringIO()
            with (
                patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg)}, clear=False),
                redirect_stdout(buf),
            ):
                rc = nuc_main(
                    [
                        "desktop",
                        "ai",
                        "--text",
                        "整理して",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsIntentProvider",
                        "--model",
                        "desktop.tidy.run",
                        "--configure-provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--configure-model",
                        model_json,
                        "--source-root",
                        str(root),
                        "--dest-root",
                        str(docs),
                        "--dest-root",
                        str(pics),
                        "--trace",
                        str(trace_path),
                        "--run-id",
                        "run_test_ai_migrate_1",
                    ]
                )
            self.assertEqual(rc, 0)
            # Old config kept; new generated config written next to it.
            gen = xdg / "nucleus" / "desktop_rules.generated.yml"
            self.assertTrue(cfg_path.exists())
            self.assertTrue(gen.exists())
            self.assertTrue((pics / "pic.jpg").exists())
            self.assertFalse((root / "pic.jpg").exists())

    def test_desktop_ai_prefers_source_root_over_existing_valid_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            xdg = td_path / "xdg"
            cfg_path = xdg / "nucleus" / "desktop_rules.yml"
            cfg_path.parent.mkdir(parents=True, exist_ok=True)

            # Existing valid config points to Desktop_A.
            desktop_a = td_path / "Desktop_A"
            desktop_b = td_path / "Desktop_B"
            docs = td_path / "Documents"
            pics = td_path / "Pictures"
            for p in (desktop_a, desktop_b, docs, pics):
                p.mkdir(parents=True, exist_ok=True)
            (desktop_b / "pic.jpg").write_text("x", encoding="utf-8")

            cfg_path.write_text(
                "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{desktop_a}"',
                        f'  staging_dir: "{desktop_a}_Aux"',
                        "",
                        "folders:",
                        f'  images: "{pics}"',
                        f'  downloads: "{docs}"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: "downloads"',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            # Bootstrap config proposal for Desktop_B.
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{desktop_b}"',
                        f'  staging_dir: "{desktop_b}_Aux"',
                        "",
                        "folders:",
                        f'  images: "{pics}"',
                        f'  downloads: "{docs}"',
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
                        '    move_to: "downloads"',
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            trace_path = td_path / "trace.jsonl"
            buf = io.StringIO()
            with (
                patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg)}, clear=False),
                redirect_stdout(buf),
            ):
                rc = nuc_main(
                    [
                        "desktop",
                        "ai",
                        "--text",
                        "整理して",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsIntentProvider",
                        "--model",
                        "desktop.tidy.run",
                        "--configure-provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--configure-model",
                        model_json,
                        "--source-root",
                        str(desktop_b),
                        "--dest-root",
                        str(docs),
                        "--dest-root",
                        str(pics),
                        "--trace",
                        str(trace_path),
                        "--run-id",
                        "run_test_ai_prefer_1",
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(cfg_path.exists())
            gen = xdg / "nucleus" / "desktop_rules.generated.yml"
            self.assertTrue(gen.exists())
            self.assertTrue((pics / "pic.jpg").exists())
            self.assertFalse((desktop_b / "pic.jpg").exists())

    def test_desktop_ai_overwrites_existing_generated_config_when_source_root_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            xdg = td_path / "xdg"
            cfg_path = xdg / "nucleus" / "desktop_rules.yml"
            gen_path = xdg / "nucleus" / "desktop_rules.generated.yml"
            cfg_path.parent.mkdir(parents=True, exist_ok=True)

            desktop_old = td_path / "Desktop_Old"
            desktop_new = td_path / "Desktop_New"
            docs = td_path / "Documents"
            pics = td_path / "Pictures"
            for p in (desktop_old, desktop_new, docs, pics):
                p.mkdir(parents=True, exist_ok=True)
            (desktop_new / "pic.jpg").write_text("x", encoding="utf-8")

            # Old incompatible config (forces generated mode).
            cfg_path.write_text(
                "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{desktop_old}"',
                        f'  staging_dir: "{desktop_old}_Aux"',
                        "",
                        "folders:",
                        '  screenshots: "Screenshots"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: "screenshots"',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            # Pre-existing generated config pointing to desktop_old (this must be overwritten).
            gen_path.write_text(
                "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{desktop_old}"',
                        f'  staging_dir: "{desktop_old}_Aux"',
                        "",
                        "folders:",
                        f'  images: "{pics}"',
                        f'  downloads: "{docs}"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: "downloads"',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            # Bootstrap config proposal for desktop_new.
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{desktop_new}"',
                        f'  staging_dir: "{desktop_new}_Aux"',
                        "",
                        "folders:",
                        f'  images: "{pics}"',
                        f'  downloads: "{docs}"',
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
                        '    move_to: "downloads"',
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            trace_path = td_path / "trace.jsonl"
            buf = io.StringIO()
            with (
                patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg)}, clear=False),
                redirect_stdout(buf),
            ):
                rc = nuc_main(
                    [
                        "desktop",
                        "ai",
                        "--text",
                        "整理して",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsIntentProvider",
                        "--model",
                        "desktop.tidy.run",
                        "--configure-provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--configure-model",
                        model_json,
                        "--source-root",
                        str(desktop_new),
                        "--dest-root",
                        str(docs),
                        "--dest-root",
                        str(pics),
                        "--trace",
                        str(trace_path),
                        "--run-id",
                        "run_test_ai_overwrite_gen_1",
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(gen_path.exists())
            self.assertTrue((pics / "pic.jpg").exists())
            self.assertFalse((desktop_new / "pic.jpg").exists())

    def test_desktop_configure_ai_writes_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_docs = td_path / "Documents"
            dest_pics = td_path / "Pictures"
            source.mkdir(parents=True)
            dest_docs.mkdir(parents=True)
            dest_pics.mkdir(parents=True)
            (source / "pic.jpg").write_text("x", encoding="utf-8")
            (source / "a.tmp").write_text("x", encoding="utf-8")

            out_cfg = td_path / "desktop_rules.yml"
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        f'  documents: "{dest_docs}"',
                        f'  images: "{dest_pics}"',
                        f'  downloads: "{dest_docs}"',
                        "",
                        "rules:",
                        '  - id: "r_tmp"',
                        "    match:",
                        "      any:",
                        '        - ext_in: ["tmp"]',
                        "    action:",
                        "      delete: true",
                        '  - id: "r_images"',
                        "    match:",
                        "      any:",
                        '        - ext_in: ["jpg"]',
                        "    action:",
                        '      move_to: "images"',
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
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_docs),
                        "--dest-root",
                        str(dest_pics),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out_cfg.exists())

    def test_desktop_configure_ai_normalizes_folders_list_value(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_docs = td_path / "Documents"
            source.mkdir(parents=True)
            dest_docs.mkdir(parents=True)
            (source / "a.tmp").write_text("x", encoding="utf-8")

            out_cfg = td_path / "desktop_rules.yml"
            # Simulate an LLM mistake: folders value as YAML list
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        "  downloads:",
                        f"    - \"{dest_docs}\"",
                        "",
                        "rules:",
                        '  - id: "r_tmp"',
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
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_docs),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out_cfg.exists())

    def test_desktop_configure_ai_normalizes_rules_dict_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_docs = td_path / "Documents"
            source.mkdir(parents=True)
            dest_docs.mkdir(parents=True)

            out_cfg = td_path / "desktop_rules.yml"
            # Simulate an LLM mistake: rules is an object (should be array), containing unmatched_action.
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        f'  documents: "{dest_docs}"',
                        "",
                        "rules:",
                        "  unmatched_action:",
                        "    move_to: Documents",
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_docs),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out_cfg.exists())

    def test_desktop_configure_ai_fills_required_keys_and_normalizes_unmatched_subfolder(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_docs = td_path / "Documents"
            source.mkdir(parents=True)
            dest_docs.mkdir(parents=True)

            out_cfg = td_path / "desktop_rules.yml"
            # Simulate an LLM proposal missing version/plugin and using path-like move_to.
            draft = {
                "config_yaml": "\n".join(
                    [
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        f'  Documents: "{dest_docs}"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        "    move_to: Documents/Unmatched",
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_docs),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out_cfg.exists())
            # Ensure config validates basic shape after normalization.
            import yaml as _yaml

            obj = _yaml.safe_load(out_cfg.read_text(encoding="utf-8"))
            self.assertEqual(obj["version"], "0.1")
            self.assertEqual(obj["plugin"], "builtin.desktop")
            self.assertIsInstance(obj.get("rules"), list)
            mt = obj["defaults"]["unmatched_action"]["move_to"]
            self.assertIsInstance(mt, str)
            self.assertNotIn("/", mt)

    def test_desktop_configure_ai_normalizes_folders_object_value(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_dl = td_path / "Downloads"
            source.mkdir(parents=True)
            dest_dl.mkdir(parents=True)

            out_cfg = td_path / "desktop_rules.yml"
            # Simulate an LLM mistake: folders value is an object with a 'path' field.
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        "  Downloads:",
                        f'    path: "{dest_dl}"',
                        "    rules:",
                        "      action:",
                        "        - move_to: Downloads",
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        "    move_to: Downloads",
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_dl),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out_cfg.exists())

    def test_desktop_configure_ai_normalizes_tilde_without_slash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            source.mkdir(parents=True)
            # Use HOME patch so ~/Downloads resolves inside temp dir.
            downloads = td_path / "Downloads"
            downloads.mkdir(parents=True)

            out_cfg = td_path / "desktop_rules.yml"
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        "  Downloads: \"~Downloads\"",
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        "    move_to: Downloads",
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with (
                patch.dict("os.environ", {"HOME": str(td_path)}, clear=False),
                redirect_stdout(buf),
            ):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        "~/Downloads",
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out_cfg.exists())

    def test_desktop_configure_ai_drops_stray_delete_in_unmatched_action(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_docs = td_path / "Documents"
            source.mkdir(parents=True)
            dest_docs.mkdir(parents=True)

            out_cfg = td_path / "desktop_rules.yml"
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        f'  documents: "{dest_docs}"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        "    move_to: documents",
                        "    delete: false",
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_docs),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out_cfg.exists())

    def test_desktop_configure_ai_drops_malformed_rule_missing_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_dl = td_path / "Downloads"
            source.mkdir(parents=True)
            dest_dl.mkdir(parents=True)

            out_cfg = td_path / "desktop_rules.yml"
            # Simulate an LLM mistake: rule has only action (no id/match)
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        f'  downloads: "{dest_dl}"',
                        "",
                        "rules:",
                        "  - action:",
                        "      move_to: Downloads",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        "    move_to: downloads",
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_dl),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            import yaml as _yaml

            obj = _yaml.safe_load(out_cfg.read_text(encoding="utf-8"))
            self.assertIsInstance(obj.get("rules"), list)
            # malformed rule should be dropped
            self.assertEqual(obj["rules"], [])

    def test_desktop_configure_ai_relociates_folders_outside_dest_roots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_docs = td_path / "Dest" / "Documents"
            dest_pics = td_path / "Dest" / "Pictures"
            dest_dl = td_path / "Dest" / "Downloads"
            source.mkdir(parents=True)
            dest_docs.mkdir(parents=True)
            dest_pics.mkdir(parents=True)
            dest_dl.mkdir(parents=True)

            out_cfg = td_path / "desktop_rules.yml"
            # LLM mistake: folders destination incorrectly placed under source_root.
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        f'  Archives: "{source}/Archives"',
                        f'  Downloads: "{dest_dl}"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        "    move_to: Archives",
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_docs),
                        "--dest-root",
                        str(dest_pics),
                        "--dest-root",
                        str(dest_dl),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            import yaml as _yaml
            import os as _os

            obj = _yaml.safe_load(out_cfg.read_text(encoding="utf-8"))
            folders = obj.get("folders", {})
            self.assertIsInstance(folders, dict)
            self.assertIn("Archives", folders)
            arch = folders["Archives"]
            self.assertIsInstance(arch, str)
            # Must be relocated under one of dest roots (we choose primary dest root).
            self.assertEqual(_os.path.commonpath([str(dest_docs), _os.path.expanduser(arch)]), str(dest_docs))

    def test_desktop_configure_ai_normalizes_folders_list_multiple_files_to_common_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source = td_path / "Desktop"
            dest_dl = td_path / "Dest" / "Downloads"
            source.mkdir(parents=True)
            dest_dl.mkdir(parents=True)

            out_cfg = td_path / "desktop_rules.yml"
            draft = {
                "config_yaml": "\n".join(
                    [
                        'version: "0.1"',
                        'plugin: "builtin.desktop"',
                        "",
                        "root:",
                        f'  path: "{source}"',
                        f'  staging_dir: "{source}_Aux"',
                        "",
                        "folders:",
                        "  Downloads:",
                        f'    - "{dest_dl}/archive.zip"',
                        f'    - "{dest_dl}/doc.pdf"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        "    move_to: Downloads",
                        "",
                        "safety:",
                        '  collision_strategy: "suffix_increment"',
                        "  ignore_patterns: []",
                        "",
                    ]
                )
                + "\n",
                "rationale": "stub",
                "clarify": [],
            }
            model_json = json.dumps(draft, ensure_ascii=False)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "desktop",
                        "configure",
                        "--ai",
                        "--source-root",
                        str(source),
                        "--dest-root",
                        str(dest_dl),
                        "--config-path",
                        str(out_cfg),
                        "--accept",
                        "--allow-network-intake",
                        "--provider",
                        "nucleus.intake.testing:ModelAsJsonProvider",
                        "--model",
                        model_json,
                    ]
                )
            self.assertEqual(rc, 0)
            import yaml as _yaml
            import os as _os

            obj = _yaml.safe_load(out_cfg.read_text(encoding="utf-8"))
            folders = obj.get("folders", {})
            self.assertIsInstance(folders, dict)
            self.assertEqual(_os.path.expanduser(folders.get("Downloads")), str(dest_dl))

    def test_alfred_emits_intent_from_query(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "Desktop"
            staging = td_path / "Desktop_Aux"
            docs = td_path / "Documents"
            downloads = td_path / "Downloads"
            root.mkdir(parents=True)
            docs.mkdir(parents=True)
            downloads.mkdir(parents=True)

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
                        f'  documents: "{docs}"',
                        f'  downloads: "{downloads}"',
                        "",
                        "rules: []",
                        "",
                        "defaults:",
                        "  unmatched_action:",
                        '    move_to: "downloads"',
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
            self.assertEqual(set(obj["scope"]["fs_roots"]), {str(root), str(staging), f"{staging}/ToDelete", str(docs), str(downloads)})

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
        old_key = os.environ.get("OPENAI_API_KEY")
        os.environ.pop("OPENAI_API_KEY", None)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(["intake", "--text", "hello", "--allow-network-intake"])
            self.assertEqual(rc, 1)
            out = buf.getvalue()
            self.assertIn("intake.missing_api_key", out)
        finally:
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key

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

    def test_intake_prints_error_data_payload_when_present(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = nuc_main(
                [
                    "intake",
                    "--text",
                    "hello",
                    "--allow-network-intake",
                    "--provider",
                    "nucleus.intake.testing:RaiseValidationErrorProvider",
                    "--model",
                    "stub",
                ]
            )
        self.assertEqual(rc, 1)
        out = buf.getvalue()
        self.assertIn("intake.openai_http_error", out)
        self.assertIn('"status": 401', out)
        self.assertIn('"body": "invalid_api_key"', out)


if __name__ == "__main__":
    unittest.main()

