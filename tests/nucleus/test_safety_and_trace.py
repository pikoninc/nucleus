import json
import tempfile
import unittest
from pathlib import Path

from nucleus.bootstrap_tools import build_tool_registry
from nucleus.core.kernel import Kernel
from nucleus.core.runtime_context import RuntimeContext


class TestNucleusSafetyAndTrace(unittest.TestCase):
    def setUp(self) -> None:
        self.tools = build_tool_registry()
        self.kernel = Kernel(self.tools)

    def test_denies_missing_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_1", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            plan = {
                "plan_id": "p1",
                "intent": {"intent_id": "desktop.tidy", "params": {}, "scope": {"fs_roots": []}},
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "List",
                        "phase": "staging",
                        "tool": {"tool_id": "fs.list", "args": {"path": "."}, "dry_run_ok": True},
                    }
                ],
            }

            with self.assertRaises(Exception):
                self.kernel.run_plan(ctx, plan)

            self.assertTrue(trace_path.exists())
            lines = [l for l in trace_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertGreaterEqual(len(lines), 1)
            events = [json.loads(l) for l in lines]
            event_types = [e["event_type"] for e in events]
            self.assertIn("intent_received", event_types)
            # Missing/invalid scope is rejected at schema validation (before policy evaluation).
            self.assertIn("error", event_types)

    def test_trace_emitted_on_successful_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_2", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            plan = {
                "plan_id": "p2",
                "intent": {"intent_id": "desktop.tidy", "params": {}, "scope": {"fs_roots": ["."], "allow_network": False}},
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "List",
                        "phase": "staging",
                        "tool": {"tool_id": "fs.list", "args": {"path": "."}, "dry_run_ok": True},
                    }
                ],
            }

            out = self.kernel.run_plan(ctx, plan)
            self.assertEqual(out["plan_id"], "p2")
            self.assertTrue(trace_path.exists())

            events = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            event_types = [e["event_type"] for e in events]
            self.assertIn("intent_received", event_types)
            self.assertIn("policy_decision", event_types)
            self.assertIn("step_started", event_types)
            self.assertIn("step_finished", event_types)
            self.assertIn("run_finished", event_types)

    def test_dry_run_allows_move_of_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_3", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            plan = {
                "plan_id": "p3",
                "intent": {"intent_id": "desktop.tidy", "params": {}, "scope": {"fs_roots": ["."], "allow_network": False}},
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "Move (dry-run, even if source missing)",
                        "phase": "commit",
                        "tool": {
                            "tool_id": "fs.move",
                            "args": {"from": "./does_not_exist.txt", "to": "./_Sorted/does_not_exist.txt"},
                            "dry_run_ok": True,
                        },
                    }
                ],
            }

            out = self.kernel.run_plan(ctx, plan)
            self.assertEqual(out["plan_id"], "p3")

    def test_denies_path_outside_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_4", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            # Declare scope rooted at temp dir, but attempt to stat a path outside it.
            plan = {
                "plan_id": "p4",
                "intent": {"intent_id": "desktop.tidy", "params": {}, "scope": {"fs_roots": [td], "allow_network": False}},
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "Stat outside scope",
                        "phase": "staging",
                        "tool": {"tool_id": "fs.stat", "args": {"path": "/"}, "dry_run_ok": True},
                    }
                ],
            }

            with self.assertRaises(Exception):
                self.kernel.run_plan(ctx, plan)

            lines = [l for l in trace_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            events = [json.loads(l) for l in lines]
            event_types = [e["event_type"] for e in events]
            self.assertIn("policy_decision", event_types)
            self.assertIn("step_denied", event_types)

    def test_invalid_plan_schema_emits_error_trace(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_5", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            # Missing required fields (no steps array).
            plan = {
                "plan_id": "p5",
                "intent": {"intent_id": "desktop.tidy", "params": {}, "scope": {"fs_roots": [td], "allow_network": False}},
            }

            with self.assertRaises(Exception):
                self.kernel.run_plan(ctx, plan)

            lines = [l for l in trace_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            events = [json.loads(l) for l in lines]
            event_types = [e["event_type"] for e in events]
            self.assertIn("intent_received", event_types)
            self.assertIn("error", event_types)


if __name__ == "__main__":
    unittest.main()

