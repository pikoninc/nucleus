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
        self.assertIn("desktop.tidy", intent_ids)

    def test_dry_run_intent_outputs_plan_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = nuc_main(
                    [
                        "dry-run-intent",
                        "--intent",
                        "desktop.tidy",
                        "--target-dir",
                        ".",
                        "--trace",
                        str(trace_path),
                        "--run-id",
                        "run_test_intent_1",
                    ]
                )
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["plan_id"], "plan_desktop_tidy_001")
            self.assertTrue(trace_path.exists())


if __name__ == "__main__":
    unittest.main()

