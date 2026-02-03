from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from nucleus.bootstrap_tools import build_tool_registry
from nucleus.core.errors import PolicyDenied, ValidationError
from nucleus.core.kernel import Kernel
from nucleus.core.runtime_context import RuntimeContext
from nucleus.intake.provider_loading import load_triage_provider
from nucleus.intake.triage import triage_text_to_intent
from nucleus.registry.plugin_registry import PluginRegistry
from nucleus.resources import plugins_dir


def _json_response(handler: BaseHTTPRequestHandler, status: int, obj: Dict[str, Any]) -> None:
    raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _read_json_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    n = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(n) if n > 0 else b""
    if not raw:
        return {}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise ValidationError(code="http.invalid_json", message="Request body must be valid JSON") from e
    if not isinstance(obj, dict):
        raise ValidationError(code="http.invalid_json", message="Request body must be a JSON object")
    return obj


def _load_intents_catalog(*, plugins_path: Optional[str]) -> list[Dict[str, str]]:
    reg = PluginRegistry()
    reg.load_from_dir(Path(plugins_path) if plugins_path else plugins_dir())
    return reg.list_intents()


def _parse_scope(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValidationError(code="http.invalid", message="scope must be an object")
    fs_roots = obj.get("fs_roots")
    if not isinstance(fs_roots, list) or not fs_roots or any((not isinstance(x, str) or not x) for x in fs_roots):
        raise ValidationError(code="http.invalid", message="scope.fs_roots must be a non-empty array of strings")
    out: Dict[str, Any] = {"fs_roots": fs_roots, "allow_network": bool(obj.get("allow_network", False))}
    if "network_hosts_allowlist" in obj:
        out["network_hosts_allowlist"] = obj.get("network_hosts_allowlist")
    return out


def _parse_context(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if not isinstance(obj, dict):
        raise ValidationError(code="http.invalid", message="context must be an object when provided")
    return obj


@dataclass(frozen=True)
class HttpApiConfig:
    host: str = "127.0.0.1"
    port: int = 8787
    # Intake provider configuration (LLM or deterministic test providers)
    provider: str = "openai.responses"
    model: str = "gpt-4o-mini"
    api_base: Optional[str] = None
    api_key_env: str = "OPENAI_API_KEY"
    plugins_dir: Optional[str] = None
    # Auth is intentionally a placeholder; adapters can implement any scheme.
    # This reference server supports a simple bearer token when set.
    bearer_token: Optional[str] = None
    # Hosting app must provide planner resolution for /run and /run_text.
    # The resolver should return a Planner for the given intent_id.
    planner_resolver: Optional[Callable[[str], Any]] = None


def serve_http_api(config: HttpApiConfig) -> ThreadingHTTPServer:
    tools = build_tool_registry()
    kernel = Kernel(tools)

    intents_catalog = _load_intents_catalog(plugins_path=config.plugins_dir)

    class Handler(BaseHTTPRequestHandler):
        def _auth_ok(self) -> bool:
            if not config.bearer_token:
                return True
            v = self.headers.get("Authorization", "")
            return v == f"Bearer {config.bearer_token}"

        def do_POST(self) -> None:  # noqa: N802
            if not self._auth_ok():
                _json_response(self, 401, {"error": {"code": "auth.unauthorized", "message": "Unauthorized"}})
                return

            try:
                body = _read_json_body(self)
                if self.path == "/intake":
                    input_text = body.get("input_text")
                    if not isinstance(input_text, str) or not input_text.strip():
                        raise ValidationError(code="http.invalid", message="input_text must be a non-empty string")
                    scope = _parse_scope(body.get("scope"))
                    context = _parse_context(body.get("context"))

                    loaded = load_triage_provider(
                        provider=config.provider,
                        model=config.model,
                        api_base=config.api_base,
                        api_key_env=config.api_key_env,
                    )
                    res = triage_text_to_intent(
                        input_text=input_text,
                        intents_catalog=intents_catalog,
                        scope=scope,
                        context=context,
                        provider=loaded.provider,
                        provider_id=loaded.provider_id,
                        model=loaded.model,
                        allow_network=True,
                    )
                    _json_response(self, 200, {"intent": res.intent, "triage": {"provider": res.provider, "model": res.model}})
                    return

                if self.path == "/run":
                    # Minimal runtime defaults; adapters can expose more knobs.
                    run_id = str(body.get("run_id") or "run_http")
                    trace_path = Path(str(body.get("trace_path") or "trace.jsonl"))
                    dry_run = bool(body.get("dry_run", False))

                    intent = body.get("intent")
                    if not isinstance(intent, dict):
                        raise ValidationError(code="http.invalid", message="intent must be an object")

                    intent_id = intent.get("intent_id")
                    if not isinstance(intent_id, str) or not intent_id:
                        raise ValidationError(code="http.invalid", message="intent.intent_id must be a non-empty string")
                    if config.planner_resolver is None:
                        raise ValidationError(code="http.not_configured", message="planner_resolver is required for /run")
                    planner = config.planner_resolver(intent_id)

                    ctx = RuntimeContext(
                        run_id=run_id,
                        dry_run=dry_run,
                        strict_dry_run=dry_run,
                        allow_destructive=False,
                        trace_path=trace_path,
                    )
                    out = kernel.run_intent(ctx, intent, planner)
                    _json_response(self, 200, {"intent": intent, **out, "trace_path": str(trace_path)})
                    return

                if self.path == "/run_text":
                    input_text = body.get("input_text")
                    if not isinstance(input_text, str) or not input_text.strip():
                        raise ValidationError(code="http.invalid", message="input_text must be a non-empty string")
                    scope = _parse_scope(body.get("scope"))
                    context = _parse_context(body.get("context"))

                    loaded = load_triage_provider(
                        provider=config.provider,
                        model=config.model,
                        api_base=config.api_base,
                        api_key_env=config.api_key_env,
                    )
                    triaged = triage_text_to_intent(
                        input_text=input_text,
                        intents_catalog=intents_catalog,
                        scope=scope,
                        context=context,
                        provider=loaded.provider,
                        provider_id=loaded.provider_id,
                        model=loaded.model,
                        allow_network=True,
                    )

                    run_id = str(body.get("run_id") or "run_http")
                    trace_path = Path(str(body.get("trace_path") or "trace.jsonl"))
                    dry_run = bool(body.get("dry_run", False))

                    intent_id = triaged.intent.get("intent_id")
                    if not isinstance(intent_id, str) or not intent_id:
                        raise ValidationError(code="http.invalid", message="triaged intent is missing intent_id")
                    if config.planner_resolver is None:
                        raise ValidationError(code="http.not_configured", message="planner_resolver is required for /run_text")
                    planner = config.planner_resolver(intent_id)

                    ctx = RuntimeContext(
                        run_id=run_id,
                        dry_run=dry_run,
                        strict_dry_run=dry_run,
                        allow_destructive=False,
                        trace_path=trace_path,
                    )
                    out = kernel.run_intent(ctx, triaged.intent, planner)
                    _json_response(
                        self,
                        200,
                        {
                            "intent": triaged.intent,
                            "triage": {"provider": triaged.provider, "model": triaged.model},
                            **out,
                            "trace_path": str(trace_path),
                        },
                    )
                    return

                _json_response(self, 404, {"error": {"code": "http.not_found", "message": "Not found"}})
            except PolicyDenied as e:
                _json_response(self, 403, {"error": {"code": e.code, "message": e.message, "data": e.data or {}}})
            except ValidationError as e:
                _json_response(self, 400, {"error": {"code": e.code, "message": e.message, "data": e.data or {}}})
            except Exception as e:  # noqa: BLE001
                _json_response(self, 500, {"error": {"code": "http.error", "message": "Internal error", "data": {"error": repr(e)}}})

        def log_message(self, fmt: str, *args: Any) -> None:  # silence default logging
            return

    return ThreadingHTTPServer((config.host, config.port), Handler)

