import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict

from nucleus.core.planner import StaticPlanner
from nucleus.http_api import HttpApiConfig, serve_http_api


def _post_json(host: str, port: int, path: str, payload: Dict[str, Any], headers: Dict[str, str] | None = None) -> tuple[int, Dict[str, Any]]:
    conn = HTTPConnection(host, port, timeout=5)
    body = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    if headers:
        h.update(headers)
    conn.request("POST", path, body=body, headers=h)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8", errors="replace")
    obj = json.loads(raw) if raw else {}
    conn.close()
    return resp.status, obj


class TestHttpApi(unittest.TestCase):
    def setUp(self) -> None:
        plan_template = {
            "plan_id": "plan_http_static_001",
            "risk": {"level": "low", "reasons": ["test"]},
            "steps": [
                {
                    "step_id": "list",
                    "title": "List",
                    "phase": "staging",
                    "tool": {"tool_id": "fs.list", "args": {"path": "."}, "dry_run_ok": True},
                }
            ],
        }
        planner = StaticPlanner(plan_template)

        self.server = serve_http_api(
            HttpApiConfig(
                host="127.0.0.1",
                port=0,
                provider="nucleus.intake.testing:FirstAllowedIntentProvider",
                model="stub",
                planner_resolver=lambda _intent_id: planner,
            )
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_intake_returns_intent(self) -> None:
        status, obj = _post_json(
            self.host,
            self.port,
            "/intake",
            {"input_text": "hello", "scope": {"fs_roots": ["."], "allow_network": False}, "context": {"source": "web"}},
        )
        self.assertEqual(status, 200)
        self.assertIn("intent", obj)
        intent = obj["intent"]
        self.assertIsInstance(intent, dict)
        self.assertIn("intent_id", intent)
        self.assertEqual(intent["scope"]["fs_roots"], ["."])

    def test_run_executes_intent(self) -> None:
        with TemporaryDirectory() as td:
            trace_path = str(Path(td) / "trace.jsonl")
            intent = {"intent_id": "desktop.tidy.configure", "params": {}, "scope": {"fs_roots": ["."], "allow_network": False}, "context": {}}
            status, obj = _post_json(
                self.host,
                self.port,
                "/run",
                {"intent": intent, "run_id": "run_http_test", "trace_path": trace_path, "dry_run": True},
            )
            self.assertEqual(status, 200)
            self.assertEqual(obj["plan_id"], "plan_http_static_001")
            self.assertTrue(Path(trace_path).exists())

    def test_run_text_triangulates_and_executes(self) -> None:
        with TemporaryDirectory() as td:
            trace_path = str(Path(td) / "trace.jsonl")
            status, obj = _post_json(
                self.host,
                self.port,
                "/run_text",
                {
                    "input_text": "tidy my desktop",
                    "scope": {"fs_roots": ["."], "allow_network": False},
                    "context": {"source": "discord"},
                    "run_id": "run_http_test2",
                    "trace_path": trace_path,
                    "dry_run": True,
                },
            )
            self.assertEqual(status, 200)
            self.assertIn("intent", obj)
            self.assertEqual(obj["plan_id"], "plan_http_static_001")
            self.assertTrue(Path(trace_path).exists())


if __name__ == "__main__":
    unittest.main()

