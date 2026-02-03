import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

from nucleus.bootstrap_tools import build_tool_registry
from nucleus.core.errors import PolicyDenied
from nucleus.core.kernel import Kernel
from nucleus.core.runtime_context import RuntimeContext


class TestNetworkPolicy(unittest.TestCase):
    def test_denies_network_tool_when_allowlist_missing(self) -> None:
        tools = build_tool_registry()

        kernel = Kernel(tools)

        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_net_0", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            plan = {
                "plan_id": "p_net_0",
                "intent": {"intent_id": "test.net", "params": {}, "scope": {"fs_roots": ["."], "allow_network": True}},
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "Call network tool (missing allowlist)",
                        "phase": "commit",
                        "tool": {"tool_id": "net.http", "args": {"url": "https://api.example.com/ping"}, "dry_run_ok": True},
                    }
                ],
            }

            with self.assertRaises(PolicyDenied):
                kernel.run_plan(ctx, plan)

    def test_allows_network_tool_when_host_in_allowlist(self) -> None:
        tools = build_tool_registry()

        kernel = Kernel(tools)

        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_net_4", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            plan = {
                "plan_id": "p_net_4",
                "intent": {
                    "intent_id": "test.net",
                    "params": {},
                    "scope": {"fs_roots": ["."], "allow_network": True, "network_hosts_allowlist": ["api.allowed.com"]},
                },
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "Call network tool (host allowed)",
                        "phase": "commit",
                        "tool": {"tool_id": "net.http", "args": {"url": "https://api.allowed.com/ping"}, "dry_run_ok": True},
                    }
                ],
            }

            out = kernel.run_plan(ctx, plan)
            self.assertEqual(out["plan_id"], "p_net_4")

    def test_denies_network_tool_when_host_not_in_allowlist(self) -> None:
        tools = build_tool_registry()

        kernel = Kernel(tools)

        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_net_3", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            plan = {
                "plan_id": "p_net_3",
                "intent": {
                    "intent_id": "test.net",
                    "params": {},
                    "scope": {"fs_roots": ["."], "allow_network": True, "network_hosts_allowlist": ["api.allowed.com"]},
                },
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "Call network tool (host denied)",
                        "phase": "commit",
                        "tool": {"tool_id": "net.http", "args": {"url": "https://api.denied.com/ping"}, "dry_run_ok": True},
                    }
                ],
            }

            with self.assertRaises(PolicyDenied):
                kernel.run_plan(ctx, plan)

    def test_allows_network_tool_when_allow_network_true(self) -> None:
        tools = build_tool_registry()

        kernel = Kernel(tools)

        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_net_2", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            plan = {
                "plan_id": "p_net_2",
                "intent": {
                    "intent_id": "test.net",
                    "params": {},
                    "scope": {"fs_roots": ["."], "allow_network": True, "network_hosts_allowlist": ["*"]},
                },
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "Call network tool (allowed)",
                        "phase": "commit",
                        "tool": {"tool_id": "net.http", "args": {"url": "https://api.example.com/ping"}, "dry_run_ok": True},
                    }
                ],
            }

            out = kernel.run_plan(ctx, plan)
            self.assertEqual(out["plan_id"], "p_net_2")

    def test_denies_network_tool_when_allow_network_false(self) -> None:
        tools = build_tool_registry()

        kernel = Kernel(tools)

        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "trace.jsonl"
            ctx = RuntimeContext(run_id="run_test_net_1", dry_run=True, strict_dry_run=True, trace_path=trace_path)

            plan = {
                "plan_id": "p_net_1",
                "intent": {"intent_id": "test.net", "params": {}, "scope": {"fs_roots": ["."], "allow_network": False}},
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "Call network tool (should be denied)",
                        "phase": "commit",
                        "tool": {"tool_id": "net.http", "args": {"url": "https://api.example.com/ping"}, "dry_run_ok": True},
                    }
                ],
            }

            with self.assertRaises(PolicyDenied):
                kernel.run_plan(ctx, plan)

            # Ensure a policy decision was recorded in trace.
            events = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            event_types = [e["event_type"] for e in events]
            self.assertIn("policy_decision", event_types)
            self.assertIn("step_denied", event_types)


if __name__ == "__main__":
    unittest.main()

