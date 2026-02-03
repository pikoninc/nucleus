from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nucleus.bootstrap_tools import build_tool_registry
from nucleus.core.kernel import Kernel
from nucleus.core.runtime_context import RuntimeContext
from nucleus.core.errors import ValidationError
from nucleus.registry.plugin_registry import PluginRegistry
from nucleus.plugins.builtin_desktop.planner import get_planner as get_builtin_desktop_planner
from nucleus.trace.replay import Replay


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_check_contracts(_args: argparse.Namespace) -> int:
    from scripts.check_contracts import main as check_main  # local import to avoid sys.path issues

    return int(check_main())

def cmd_list_tools(args: argparse.Namespace) -> int:
    tools = build_tool_registry()
    tool_defs = tools.list_tools()
    if args.json:
        print(json.dumps(tool_defs, ensure_ascii=False, indent=2))
    else:
        for t in tool_defs:
            print("{tool_id} - {title}".format(tool_id=t.get("tool_id"), title=t.get("title")))
    return 0


def _default_plugins_dir() -> Path:
    return ROOT / "plugins"


def _load_plugins(plugins_dir: Path) -> PluginRegistry:
    reg = PluginRegistry()
    reg.load_from_dir(plugins_dir)
    return reg


def _resolve_planner(plugin_id: str):
    if plugin_id == "builtin.desktop":
        return get_builtin_desktop_planner()
    raise ValidationError(code="plugin.unknown", message=f"No planner registered for plugin_id: {plugin_id}")


def cmd_list_intents(args: argparse.Namespace) -> int:
    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else _default_plugins_dir()
    reg = _load_plugins(plugins_dir)
    intents = reg.list_intents()
    if args.json:
        print(json.dumps(intents, ensure_ascii=False, indent=2))
    else:
        for it in intents:
            print("{intent_id} -> {plugin_id}".format(**it))
    return 0


def _build_intent_from_args(args: argparse.Namespace) -> dict:
    intent_id = args.intent
    params = {}
    if args.target_dir:
        params["target_dir"] = args.target_dir

    # Scope: if none provided, default to target_dir (or "~/Desktop" when omitted).
    scope_roots = list(args.scope_root or [])
    if not scope_roots:
        scope_roots = [params.get("target_dir") or "~/Desktop"]

    scope = {"fs_roots": scope_roots, "allow_network": False}
    context = {"source": "cli"}
    return {"intent_id": intent_id, "params": params, "scope": scope, "context": context}


def cmd_dry_run_intent(args: argparse.Namespace) -> int:
    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else _default_plugins_dir()
    reg = _load_plugins(plugins_dir)
    plugin_id = reg.require_plugin_id_for_intent(args.intent)
    planner = _resolve_planner(plugin_id)

    intent = _build_intent_from_args(args)
    tools = build_tool_registry()
    kernel = Kernel(tools)
    ctx = RuntimeContext(
        run_id=args.run_id,
        dry_run=True,
        strict_dry_run=True,
        allow_destructive=False,
        trace_path=Path(args.trace),
    )
    out = kernel.run_intent(ctx, intent, planner)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_run_intent(args: argparse.Namespace) -> int:
    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else _default_plugins_dir()
    reg = _load_plugins(plugins_dir)
    plugin_id = reg.require_plugin_id_for_intent(args.intent)
    planner = _resolve_planner(plugin_id)

    intent = _build_intent_from_args(args)
    tools = build_tool_registry()
    kernel = Kernel(tools)
    ctx = RuntimeContext(
        run_id=args.run_id,
        dry_run=False,
        strict_dry_run=False,
        allow_destructive=bool(args.allow_destructive),
        trace_path=Path(args.trace),
    )
    out = kernel.run_intent(ctx, intent, planner)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_show_trace(args: argparse.Namespace) -> int:
    path = Path(args.trace)
    replay = Replay(path)
    events = list(replay.iter_events())

    if args.event_type:
        events = [e for e in events if e.get("event_type") == args.event_type]

    if args.tail is not None and args.tail >= 0:
        events = events[-args.tail :]

    if args.pretty:
        for e in events:
            print(json.dumps(e, ensure_ascii=False, indent=2))
    else:
        for e in events:
            print(json.dumps(e, ensure_ascii=False))
    return 0


def cmd_dry_run_plan(args: argparse.Namespace) -> int:
    plan = _load_json(Path(args.plan))
    tools = build_tool_registry()
    kernel = Kernel(tools)

    ctx = RuntimeContext(
        run_id=args.run_id,
        dry_run=True,
        strict_dry_run=True,
        allow_destructive=False,
        trace_path=Path(args.trace),
    )
    out = kernel.run_plan(ctx, plan)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_run_plan(args: argparse.Namespace) -> int:
    plan = _load_json(Path(args.plan))
    tools = build_tool_registry()
    kernel = Kernel(tools)

    ctx = RuntimeContext(
        run_id=args.run_id,
        dry_run=False,
        strict_dry_run=False,
        allow_destructive=bool(args.allow_destructive),
        trace_path=Path(args.trace),
    )
    out = kernel.run_plan(ctx, plan)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="nuc", description="Nucleus CLI (framework)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check-contracts", help="Validate contracts/core schemas and examples")
    p_check.set_defaults(func=cmd_check_contracts)

    p_list_tools = sub.add_parser("list-tools", help="List registered deterministic tools")
    p_list_tools.add_argument("--json", action="store_true", help="Output JSON (default)")
    p_list_tools.set_defaults(func=cmd_list_tools)

    p_list_intents = sub.add_parser("list-intents", help="List intents provided by loaded plugins")
    p_list_intents.add_argument("--plugins-dir", default=str(_default_plugins_dir()), help="Plugins directory")
    p_list_intents.add_argument("--json", action="store_true", help="Output JSON")
    p_list_intents.set_defaults(func=cmd_list_intents)

    p_show_trace = sub.add_parser("show-trace", help="Show trace events from a JSONL file")
    p_show_trace.add_argument("--trace", required=True, help="Trace path (jsonl)")
    p_show_trace.add_argument("--event-type", help="Filter by event_type")
    p_show_trace.add_argument("--tail", type=int, help="Show only last N events")
    p_show_trace.add_argument("--pretty", action="store_true", help="Pretty-print each event as JSON")
    p_show_trace.set_defaults(func=cmd_show_trace)

    p_dry = sub.add_parser("dry-run-plan", help="Dry-run a plan JSON via deterministic tools")
    p_dry.add_argument("--plan", required=True, help="Path to plan JSON")
    p_dry.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_dry.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_dry.set_defaults(func=cmd_dry_run_plan)

    p_run = sub.add_parser("run-plan", help="Execute a plan JSON via deterministic tools")
    p_run.add_argument("--plan", required=True, help="Path to plan JSON")
    p_run.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_run.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_run.add_argument("--allow-destructive", action="store_true", help="Allow destructive tools (still policy-checked)")
    p_run.set_defaults(func=cmd_run_plan)

    p_dry_intent = sub.add_parser("dry-run-intent", help="Resolve intent via plugins, plan deterministically, then dry-run")
    p_dry_intent.add_argument("--intent", required=True, help="Intent ID (e.g., desktop.tidy)")
    p_dry_intent.add_argument("--target-dir", help="Plugin param: target_dir (default: ~/Desktop)")
    p_dry_intent.add_argument(
        "--scope-root",
        action="append",
        default=[],
        help="Filesystem scope root (repeatable). Defaults to target_dir.",
    )
    p_dry_intent.add_argument("--plugins-dir", default=str(_default_plugins_dir()), help="Plugins directory")
    p_dry_intent.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_dry_intent.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_dry_intent.set_defaults(func=cmd_dry_run_intent)

    p_run_intent = sub.add_parser("run-intent", help="Resolve intent via plugins, plan deterministically, then execute")
    p_run_intent.add_argument("--intent", required=True, help="Intent ID (e.g., desktop.tidy)")
    p_run_intent.add_argument("--target-dir", help="Plugin param: target_dir (default: ~/Desktop)")
    p_run_intent.add_argument(
        "--scope-root",
        action="append",
        default=[],
        help="Filesystem scope root (repeatable). Defaults to target_dir.",
    )
    p_run_intent.add_argument("--plugins-dir", default=str(_default_plugins_dir()), help="Plugins directory")
    p_run_intent.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_run_intent.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_run_intent.add_argument("--allow-destructive", action="store_true", help="Allow destructive tools (still policy-checked)")
    p_run_intent.set_defaults(func=cmd_run_intent)

    ns = parser.parse_args(argv)
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())

