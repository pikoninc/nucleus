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
    def test_denies_network_tool_when_allow_network_false(self) -> None:
        tools = build_tool_registry()

        # Register a dummy network tool (deterministic; no real network).
        def dummy_net_tool(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
            if dry_run:
                return {
                    "dry_run": True,
                    "expected_effects": [{"kind": "net_http", "summary": f"Would call: {args.get('url')}", "resources": []}],
                }
            return {"dry_run": False, "ok": True}

        tools.register(
            {
                "tool_id": "net.http",
                "version": "0.1.0",
                "title": "HTTP request (dummy)",
                "description": "",
                "side_effects": "network",
                "destructive": False,
                "requires_explicit_allow": False,
                "supports_dry_run": True,
                "args_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"url": {"type": "string", "minLength": 1}},
                    "required": ["url"],
                },
            },
            dummy_net_tool,
        )

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

