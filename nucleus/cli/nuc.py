from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

import yaml

from nucleus.bootstrap_tools import build_tool_registry
from nucleus.contract_store import ContractStore
from nucleus.core.kernel import Kernel
from nucleus.core.runtime_context import RuntimeContext
from nucleus.core.errors import ValidationError
from nucleus.resources import core_contracts_examples_dir, core_contracts_schemas_dir, plugins_dir
from nucleus.registry.plugin_registry import PluginRegistry
from plugins.builtin_desktop.planner import get_planner as get_builtin_desktop_planner
from nucleus.trace.replay import Replay
from nucleus.cli.memory_stub import build_stub as build_memory_stub


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


_APP_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


def _validate_app_id(app_id: str) -> str:
    app_id = app_id.strip()
    if not app_id or app_id in (".", ".."):
        raise ValidationError(code="init.invalid", message="app_id must be non-empty")
    if "/" in app_id or "\\" in app_id:
        raise ValidationError(code="init.invalid", message="app_id must not contain path separators")
    if not _APP_ID_RE.match(app_id):
        raise ValidationError(
            code="init.invalid",
            message="app_id must match: ^[a-z][a-z0-9_-]{1,63}$ (e.g. my_app, my-app)",
            data={"app_id": app_id},
        )
    return app_id


def _prompt(text: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    v = input(f"{text}{suffix}: ").strip()
    if not v and default is not None:
        return default
    return v


def _confirm_bool(text: str, *, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    v = input(f"{text} ({d}): ").strip().lower()
    if not v:
        return bool(default)
    return v in ("y", "yes")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _render_app_pyproject(*, app_id: str, app_name: str) -> str:
    return "\n".join(
        [
            "[build-system]",
            'requires = ["setuptools>=68", "wheel"]',
            'build-backend = "setuptools.build_meta"',
            "",
            "[project]",
            f'name = "{app_id}"',
            'version = "0.1.0"',
            f'description = "{app_name} (Nucleus app)"',
            'readme = "README.md"',
            'requires-python = ">=3.10"',
            "dependencies = [",
            '  "nucleus>=0.1.0",',
            "]",
            "",
            "[tool.setuptools.packages.find]",
            'where = ["src"]',
            "",
        ]
    ) + "\n"


def _scaffold_app_dir(*, project_dir: Path, app_id: str, app_name: str) -> None:
    package_name = app_id.replace("-", "_")

    _write_text(
        project_dir / "README.md",
        "\n".join(
            [
                f"# {app_name}",
                "",
                "This repository was bootstrapped by `nuc init`.",
                "",
                "## Getting started",
                "",
                "```bash",
                "python -m venv .venv",
                "source .venv/bin/activate",
                "pip install -U pip",
                "pip install -e .",
                "```",
                "",
                "## Specs (spec-driven)",
                "",
                "- Start by editing `specs/` and drive implementation from specs.",
                "",
            ]
        )
        + "\n",
    )
    _write_text(
        project_dir / ".gitignore",
        "\n".join(
            [
                ".venv/",
                "__pycache__/",
                "*.pyc",
                ".pytest_cache/",
                "dist/",
                "build/",
                "*.egg-info/",
                "",
            ]
        ),
    )
    _write_text(project_dir / "pyproject.toml", _render_app_pyproject(app_id=app_id, app_name=app_name))

    _write_text(project_dir / "src" / package_name / "__init__.py", '__all__ = ["__version__"]\n\n__version__ = "0.1.0"\n')
    _write_text(
        project_dir / "src" / package_name / "app.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "def main() -> int:",
                f'    print("Hello from {app_name} ({app_id})")',
                "    return 0",
                "",
                'if __name__ == "__main__":',
                "    raise SystemExit(main())",
                "",
            ]
        ),
    )

    _write_text(
        project_dir / "specs" / "INDEX.md",
        "\n".join(
            [
                f"# Specs: {app_name}",
                "",
                "- `00_overview.md`",
                "- `01_architecture.md`",
                "",
            ]
        ),
    )
    _write_text(
        project_dir / "specs" / "00_overview.md",
        "\n".join(
            [
                f"# {app_name} — Overview",
                "",
                "## Goal",
                "- TODO: Describe what this app should do.",
                "",
                "## Non-goals",
                "- TODO",
                "",
                "## Constraints",
                "- TODO",
                "",
            ]
        ),
    )
    _write_text(
        project_dir / "specs" / "01_architecture.md",
        "\n".join(
            [
                f"# {app_name} — Architecture",
                "",
                "## Components",
                "- TODO",
                "",
                "## Data & contracts",
                "- TODO",
                "",
                "## Safety / policy",
                "- TODO",
                "",
            ]
        ),
    )

    _write_text(
        project_dir / "ai" / "README.md",
        "\n".join(
            [
                "# AI workspace",
                "",
                "This folder is for app-local AI collaboration artifacts (plans, notes, run logs).",
                "",
                "Keep specs authoritative under `specs/`. Treat chat logs as auxiliary context only.",
                "",
            ]
        ),
    )

    _write_text(
        project_dir / "ai" / "memory.md",
        "\n".join(
            [
                "# AI Memory (Summary & Decisions)",
                "",
                "This file is a curated, cross-chat memory for the app.",
                "Do not paste raw chat logs here. Keep only decisions and next actions.",
                "",
                "## Update rule (3 lines)",
                "- Decision: what was decided",
                "- Why: why it was decided",
                "- Next: what to do next",
                "",
                "## Key decisions (changelog)",
                f"- **{app_id}**: Initialization (`nuc init`)",
                "  - Decision: scaffold the project",
                "  - Why: to start spec-driven development immediately",
                "  - Next: fill in `specs/00_overview.md`",
                "",
                "## Current focus",
                "- TODO",
                "",
                "## Next Actions",
                "- TODO",
                "",
            ]
        )
        + "\n",
    )


def _maybe_prune_framework_artifacts(*, cwd: Path, interactive: bool) -> None:
    targets = [cwd / "ai", cwd / "specs"]
    existing = [p for p in targets if p.exists()]
    if not existing:
        return

    if not interactive:
        raise ValidationError(
            code="init.prune_requires_confirmation",
            message="Refusing to delete existing framework artifacts without interactive confirmation",
            data={"paths": [str(p) for p in existing]},
        )

    print("The following directories will be deleted (pruning framework artifacts):")
    for p in existing:
        print(f"- {p}")
    print("")
    token = input("Type 'DELETE' to confirm: ").strip()
    if token != "DELETE":
        print("Skipped deletion.")
        return

    for p in existing:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    print("Deleted.")


def cmd_init(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    interactive = not bool(getattr(args, "no_input", False))

    app_id = args.app_id
    app_name = args.name

    if not app_id and not interactive:
        raise ValidationError(code="init.invalid", message="--app-id is required when --no-input is set")

    if interactive:
        if not app_id:
            app_id = _prompt("App ID (directory name)", default="my_app")
        app_id = _validate_app_id(str(app_id))
        if not app_name:
            app_name = _prompt("App name (display name)", default=app_id)
        prune = bool(getattr(args, "prune_framework_artifacts", False))
        if not prune:
            prune = _confirm_bool("Delete framework artifacts (`ai/` and `specs/`) in the current directory?", default=False)
        if prune:
            _maybe_prune_framework_artifacts(cwd=cwd, interactive=True)
    else:
        app_id = _validate_app_id(str(app_id))
        if not app_name:
            app_name = app_id
        if bool(getattr(args, "prune_framework_artifacts", False)):
            _maybe_prune_framework_artifacts(cwd=cwd, interactive=False)

    base = Path(args.target_dir or ".").expanduser()
    project_dir = base / str(app_id)

    if project_dir.exists():
        if not bool(args.force):
            raise ValidationError(
                code="init.target_exists",
                message=f"Target already exists: {project_dir} (use --force to overwrite)",
                data={"target": str(project_dir)},
            )
        shutil.rmtree(project_dir)

    _scaffold_app_dir(project_dir=project_dir, app_id=str(app_id), app_name=str(app_name))
    print(f"OK: created {project_dir}.")
    return 0


def cmd_memory_stub(args: argparse.Namespace) -> int:
    t = Path(args.transcript).expanduser()
    if not t.exists():
        raise ValidationError(code="memory_stub.not_found", message=f"Transcript not found: {t}")

    repo_root = Path.cwd()
    stub = build_memory_stub(transcript_path=t, repo_root=repo_root, date=args.date)

    if args.append:
        mem = Path(args.memory).expanduser()
        if not mem.exists():
            raise ValidationError(code="memory_stub.memory_missing", message=f"Memory file not found: {mem}")
        txt = mem.read_text(encoding="utf-8", errors="replace")
        marker = "## Key decisions (changelog)"
        idx = txt.find(marker)
        if idx < 0:
            raise ValidationError(code="memory_stub.marker_missing", message=f"Marker not found in memory file: {marker}")
        after = txt.find("\n\n", idx)
        if after < 0:
            after = idx + len(marker)
        insert_at = after + 2
        new_txt = txt[:insert_at] + stub + txt[insert_at:]
        mem.write_text(new_txt, encoding="utf-8")
        print(f"Appended stub to: {mem}")
        return 0

    print(stub, end="")
    return 0


def _load_desktop_rules_paths(config_path: str) -> tuple[str, str]:
    """
    Best-effort config reader used by CLI to set scope and preflight scans.
    Schema validation is performed inside the plugin planner.
    """
    p = Path(config_path).expanduser()
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError(code="config.invalid", message="Config must be a YAML mapping/object at top-level")
    root = raw.get("root", {})
    if not isinstance(root, dict):
        raise ValidationError(code="config.invalid", message="Config.root must be an object")
    root_path = root.get("path")
    staging_dir = root.get("staging_dir")
    if not isinstance(root_path, str) or not root_path:
        raise ValidationError(code="config.invalid", message="Config.root.path must be a non-empty string")
    if not isinstance(staging_dir, str) or not staging_dir:
        raise ValidationError(code="config.invalid", message="Config.root.staging_dir must be a non-empty string")
    return (root_path, staging_dir)


def cmd_check_contracts(_args: argparse.Namespace) -> int:
    schemas_dir = core_contracts_schemas_dir()
    examples_dir = core_contracts_examples_dir()

    store = ContractStore(schemas_dir)
    store.load()

    schema_errors = store.check_schemas()
    if schema_errors:
        print("Schema validation failed:")
        for name, err in schema_errors:
            print("- {}: {}".format(name, err))
        return 1

    failures = []
    failures.extend([("intent.example.json", store.validate_json_file("intent.schema.json", examples_dir / "intent.example.json"))])
    failures.extend([("plan.example.json", store.validate_json_file("plan.schema.json", examples_dir / "plan.example.json"))])
    failures.extend(
        [
            (
                "plugin_manifest.example.json",
                store.validate_json_file("plugin_manifest.schema.json", examples_dir / "plugin_manifest.example.json"),
            )
        ]
    )
    failures.extend([("trace.sample.jsonl", store.validate_jsonl_file("trace_event.schema.json", examples_dir / "trace.sample.jsonl"))])

    ok = True
    for name, errs in failures:
        if errs:
            ok = False
            print("Example {} failed validation:".format(name))
            for e in errs:
                print("  - {}".format(e))

    if not ok:
        return 1

    print("Contracts OK")
    return 0

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
    return plugins_dir()


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
    if getattr(args, "config_path", None):
        params["config_path"] = args.config_path
    if getattr(args, "include_dirs", False):
        params["include_dirs"] = True
    excludes = list(getattr(args, "exclude", []) or [])
    if excludes:
        params["exclude"] = excludes
    overwrite_strategy = getattr(args, "overwrite_strategy", None)
    if overwrite_strategy:
        params["overwrite_strategy"] = overwrite_strategy

    # Scope: if none provided, default to target_dir (or "~/Desktop" when omitted).
    scope_roots = list(args.scope_root or [])
    if not scope_roots:
        # If config_path is provided, include both root and staging_dir so policy scope checks pass.
        if isinstance(params.get("config_path"), str) and params.get("config_path"):
            root_path, staging_dir = _load_desktop_rules_paths(str(params["config_path"]))
            scope_roots = [root_path, staging_dir]
        else:
            scope_roots = [params.get("target_dir") or "~/Desktop"]

    scope = {"fs_roots": scope_roots, "allow_network": False}
    context = {"source": "cli"}
    return {"intent_id": intent_id, "params": params, "scope": scope, "context": context}


def _preflight_scan_entries(*, kernel: Kernel, plugins_intent: dict, run_id: str, trace_path: Path) -> List[Dict[str, Any]]:
    """
    Scan target_dir via deterministic tools (fs.list + fs.stat) and return an entries snapshot
    suitable for passing into plugin planner as params.entries.
    """
    params = plugins_intent.get("params", {}) if isinstance(plugins_intent.get("params"), dict) else {}
    # Prefer config-driven root if config_path is provided.
    config_path = params.get("config_path")
    if isinstance(config_path, str) and config_path:
        root_path, _staging_dir = _load_desktop_rules_paths(config_path)
        target_dir = root_path
    else:
        target_dir = params.get("target_dir", "~/Desktop")
        if not isinstance(target_dir, str) or not target_dir:
            target_dir = "~/Desktop"

    scope = plugins_intent.get("scope", {})
    if not isinstance(scope, dict):
        scope = {"fs_roots": [target_dir], "allow_network": False}

    ctx = RuntimeContext(
        run_id=run_id,
        dry_run=True,
        strict_dry_run=True,
        allow_destructive=False,
        trace_path=trace_path,
    )

    list_plan = {
        "plan_id": "plan_preflight_list_001",
        "intent": {"intent_id": "cli.preflight_list", "params": {}, "scope": scope, "context": {"source": "cli"}},
        "steps": [
            {"step_id": "list", "title": "List target", "phase": "staging", "tool": {"tool_id": "fs.list", "args": {"path": target_dir}, "dry_run_ok": True}}
        ],
    }
    out = kernel.run_plan(ctx, list_plan)
    list_res = next((r for r in out.get("results", []) if r.get("step_id") == "list"), None)
    entries = []
    if isinstance(list_res, dict):
        o = list_res.get("output", {})
        if isinstance(o, dict) and isinstance(o.get("entries"), list):
            entries = [e for e in o.get("entries") if isinstance(e, str)]

    # Build a stat plan for each entry (to filter out directories).
    stat_steps = []
    for i, name in enumerate(entries, start=1):
        stat_steps.append(
            {
                "step_id": f"stat_{i:04d}",
                "title": f"Stat: {name}",
                "phase": "staging",
                "tool": {"tool_id": "fs.stat", "args": {"path": f"{target_dir}/{name}"}, "dry_run_ok": True},
            }
        )

    if not stat_steps:
        return []

    stat_plan = {
        "plan_id": "plan_preflight_stat_001",
        "intent": {"intent_id": "cli.preflight_stat", "params": {}, "scope": scope, "context": {"source": "cli"}},
        "steps": stat_steps,
    }
    out2 = kernel.run_plan(ctx, stat_plan)
    results = out2.get("results", [])
    snapshot: List[Dict[str, Any]] = []
    if isinstance(results, list):
        # Map back by index (deterministic; stable across run)
        for i, name in enumerate(entries, start=1):
            step_id = f"stat_{i:04d}"
            r = next((x for x in results if isinstance(x, dict) and x.get("step_id") == step_id), None)
            o = r.get("output", {}) if isinstance(r, dict) else {}
            if isinstance(o, dict):
                snapshot.append(
                    {
                        "name": name,
                        "is_file": bool(o.get("is_file", False)),
                        "is_dir": bool(o.get("is_dir", False)),
                        "size": int(o.get("size")) if isinstance(o.get("size"), int) else None,
                        "mtime": int(o.get("mtime")) if isinstance(o.get("mtime"), int) else None,
                    }
                )
    return snapshot


def cmd_desktop_configure(args: argparse.Namespace) -> int:
    root_path = args.root_path or "~/Desktop"
    staging_dir = args.staging_dir or f"{root_path}_Staging"
    out = (
        "version: \"0.1\"\n"
        "plugin: \"builtin.desktop\"\n\n"
        "root:\n"
        f"  path: \"{root_path}\"\n"
        f"  staging_dir: \"{staging_dir}\"\n\n"
        "folders:\n"
        "  screenshots: \"Screenshots\"\n"
        "  documents: \"Documents\"\n"
        "  images: \"Images\"\n"
        "  archives: \"Archives\"\n"
        "  misc: \"Misc\"\n\n"
        "rules:\n"
        "  - id: \"rule_screenshots\"\n"
        "    match:\n"
        "      any:\n"
        "        - filename_regex: \"^Screen Shot \"\n"
        "        - mime_prefix: \"image/\"\n"
        "    action:\n"
        "      move_to: \"screenshots\"\n\n"
        "  - id: \"rule_docs\"\n"
        "    match:\n"
        "      any:\n"
        "        - ext_in: [\"pdf\", \"docx\", \"xlsx\", \"pptx\", \"txt\", \"md\"]\n"
        "    action:\n"
        "      move_to: \"documents\"\n\n"
        "defaults:\n"
        "  unmatched_action:\n"
        "    move_to: \"misc\"\n\n"
        "safety:\n"
        "  no_delete: true\n"
        "  require_staging: true\n"
        "  collision_strategy: \"suffix_increment\"\n"
        "  ignore_patterns: [\".DS_Store\"]\n"
    )
    if args.output:
        Path(args.output).expanduser().write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


def _run_desktop_intent_with_scan(*, intent_id: str, config_path: str, run_id: str, trace: str, execute: bool) -> int:
    root_path, staging_dir = _load_desktop_rules_paths(config_path)

    plugins_dir = _default_plugins_dir()
    reg = _load_plugins(plugins_dir)
    plugin_id = reg.require_plugin_id_for_intent(intent_id)
    planner = _resolve_planner(plugin_id)

    intent = {
        "intent_id": intent_id,
        "params": {"config_path": config_path},
        "scope": {"fs_roots": [root_path, staging_dir], "allow_network": False},
        "context": {"source": "cli"},
    }

    tools = build_tool_registry()
    kernel = Kernel(tools)

    scan_trace = Path(trace).with_suffix(".preflight.jsonl")
    if intent_id in ("desktop.tidy.restore",):
        intent["params"]["sorted_entries"] = _preflight_walk_entries(
            kernel=kernel,
            plugins_intent=intent,
            root_path=staging_dir,
            run_id=f"{run_id}_preflight",
            trace_path=scan_trace,
            include_dirs=False,
        )
    else:
        # tidy.run / tidy.preview
        intent["params"]["entries"] = _preflight_scan_entries(
            kernel=kernel, plugins_intent=intent, run_id=f"{run_id}_preflight", trace_path=scan_trace
        )

    ctx = RuntimeContext(
        run_id=run_id,
        dry_run=not execute,
        strict_dry_run=not execute,
        allow_destructive=False,
        trace_path=Path(trace),
    )
    out = kernel.run_intent(ctx, intent, planner)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_desktop_preview(args: argparse.Namespace) -> int:
    return _run_desktop_intent_with_scan(
        intent_id="desktop.tidy.preview",
        config_path=args.config_path,
        run_id=args.run_id,
        trace=args.trace,
        execute=False,
    )


def cmd_desktop_run(args: argparse.Namespace) -> int:
    return _run_desktop_intent_with_scan(
        intent_id="desktop.tidy.run",
        config_path=args.config_path,
        run_id=args.run_id,
        trace=args.trace,
        execute=True,
    )


def cmd_desktop_restore(args: argparse.Namespace) -> int:
    return _run_desktop_intent_with_scan(
        intent_id="desktop.tidy.restore",
        config_path=args.config_path,
        run_id=args.run_id,
        trace=args.trace,
        execute=True,
    )


def _preflight_walk_entries(
    *, kernel: Kernel, plugins_intent: dict, root_path: str, run_id: str, trace_path: Path, include_dirs: bool
) -> List[Dict[str, Any]]:
    """
    Walk root_path via deterministic tool fs.walk and return entries:
      [{"path": "relative/path", "is_file": bool, "is_dir": bool}, ...]
    """
    scope = plugins_intent.get("scope", {})
    if not isinstance(scope, dict):
        scope = {"fs_roots": [root_path], "allow_network": False}

    ctx = RuntimeContext(
        run_id=run_id,
        dry_run=True,
        strict_dry_run=True,
        allow_destructive=False,
        trace_path=trace_path,
    )
    plan = {
        "plan_id": "plan_preflight_walk_001",
        "intent": {"intent_id": "cli.preflight_walk", "params": {}, "scope": scope, "context": {"source": "cli"}},
        "steps": [
            {
                "step_id": "walk",
                "title": "Walk root",
                "phase": "staging",
                "tool": {
                    "tool_id": "fs.walk",
                    "args": {"path": root_path, "include_dirs": bool(include_dirs)},
                    "dry_run_ok": True,
                },
            }
        ],
    }
    out = kernel.run_plan(ctx, plan)
    walk_res = next((r for r in out.get("results", []) if r.get("step_id") == "walk"), None)
    if isinstance(walk_res, dict):
        o = walk_res.get("output", {})
        if isinstance(o, dict) and isinstance(o.get("entries"), list):
            entries = []
            for e in o["entries"]:
                if isinstance(e, dict) and isinstance(e.get("path"), str):
                    entries.append(
                        {"path": e["path"], "is_file": bool(e.get("is_file", False)), "is_dir": bool(e.get("is_dir", False))}
                    )
            return entries
    return []


def cmd_dry_run_intent(args: argparse.Namespace) -> int:
    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else _default_plugins_dir()
    reg = _load_plugins(plugins_dir)
    plugin_id = reg.require_plugin_id_for_intent(args.intent)
    planner = _resolve_planner(plugin_id)

    intent = _build_intent_from_args(args)
    tools = build_tool_registry()
    kernel = Kernel(tools)
    if args.scan:
        scan_trace = Path(args.trace).with_suffix(".preflight.jsonl")
        if args.intent == "desktop.restore":
            target_dir = intent.get("params", {}).get("target_dir", "~/Desktop")
            sorted_root = f"{target_dir}/_Sorted"
            # Ensure scope includes sorted_root if user explicitly provided roots.
            intent["params"]["sorted_entries"] = _preflight_walk_entries(
                kernel=kernel,
                plugins_intent=intent,
                root_path=sorted_root,
                run_id=f"{args.run_id}_preflight",
                trace_path=scan_trace,
                include_dirs=bool(getattr(args, "include_dirs", False)),
            )
        else:
            intent["params"]["entries"] = _preflight_scan_entries(
                kernel=kernel, plugins_intent=intent, run_id=f"{args.run_id}_preflight", trace_path=scan_trace
            )
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
    if args.scan:
        scan_trace = Path(args.trace).with_suffix(".preflight.jsonl")
        if args.intent == "desktop.restore":
            target_dir = intent.get("params", {}).get("target_dir", "~/Desktop")
            sorted_root = f"{target_dir}/_Sorted"
            intent["params"]["sorted_entries"] = _preflight_walk_entries(
                kernel=kernel,
                plugins_intent=intent,
                root_path=sorted_root,
                run_id=f"{args.run_id}_preflight",
                trace_path=scan_trace,
                include_dirs=bool(getattr(args, "include_dirs", False)),
            )
        else:
            intent["params"]["entries"] = _preflight_scan_entries(
                kernel=kernel, plugins_intent=intent, run_id=f"{args.run_id}_preflight", trace_path=scan_trace
            )
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

    p_init = sub.add_parser("init", help="Initialize a new app scaffold (spec-driven)")
    p_init.add_argument("--app-id", help="App ID / directory name (e.g. my_app or my-app)")
    p_init.add_argument("--name", help="Human readable app name")
    p_init.add_argument("--target-dir", default=".", help="Base directory to create the app directory in")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing target directory if present")
    p_init.add_argument(
        "--prune-framework-artifacts",
        action="store_true",
        help="(Danger) Delete ./ai and ./specs in the current directory after confirmation",
    )
    p_init.add_argument("--no-input", action="store_true", help="Disable prompts (requires --app-id)")
    p_init.set_defaults(func=cmd_init)

    p_mem = sub.add_parser("memory-stub", help="Generate a stub entry for ai/memory.md from a transcript (no AI summarization)")
    p_mem.add_argument("--transcript", required=True, help="Path to transcript txt (usually under ai/.sessions/...)")
    p_mem.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p_mem.add_argument("--append", action="store_true", help="Append to memory file instead of printing to stdout")
    p_mem.add_argument("--memory", default="ai/memory.md", help="Path to memory file (default: ai/memory.md)")
    p_mem.set_defaults(func=cmd_memory_stub)

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
    p_dry_intent.add_argument("--include-dirs", action="store_true", help="Also move directories (default: false)")
    p_dry_intent.add_argument("--exclude", action="append", default=[], help="Exclude entry name by glob pattern (repeatable)")
    p_dry_intent.add_argument(
        "--overwrite-strategy",
        default="error",
        choices=["error", "overwrite", "skip"],
        help="When destination exists: error|overwrite|skip (default: error)",
    )
    p_dry_intent.add_argument(
        "--scope-root",
        action="append",
        default=[],
        help="Filesystem scope root (repeatable). Defaults to target_dir.",
    )
    p_dry_intent.add_argument("--plugins-dir", default=str(_default_plugins_dir()), help="Plugins directory")
    p_dry_intent.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_dry_intent.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_dry_intent.add_argument("--scan", action="store_true", help="Preflight scan target_dir via tools and pass entries into planner")
    p_dry_intent.set_defaults(func=cmd_dry_run_intent)

    p_run_intent = sub.add_parser("run-intent", help="Resolve intent via plugins, plan deterministically, then execute")
    p_run_intent.add_argument("--intent", required=True, help="Intent ID (e.g., desktop.tidy)")
    p_run_intent.add_argument("--target-dir", help="Plugin param: target_dir (default: ~/Desktop)")
    p_run_intent.add_argument("--include-dirs", action="store_true", help="Also move directories (default: false)")
    p_run_intent.add_argument("--exclude", action="append", default=[], help="Exclude entry name by glob pattern (repeatable)")
    p_run_intent.add_argument(
        "--overwrite-strategy",
        default="error",
        choices=["error", "overwrite", "skip"],
        help="When destination exists: error|overwrite|skip (default: error)",
    )
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
    p_run_intent.add_argument("--scan", action="store_true", help="Preflight scan target_dir via tools and pass entries into planner")
    p_run_intent.add_argument("--config-path", help="Plugin param: config_path (YAML) for config-driven intents")
    p_run_intent.set_defaults(func=cmd_run_intent)

    p_dry_intent.add_argument("--config-path", help="Plugin param: config_path (YAML) for config-driven intents")

    p_desktop = sub.add_parser("desktop", help="Desktop tidy UX commands (builtin.desktop)")
    desktop_sub = p_desktop.add_subparsers(dest="desktop_cmd", required=True)

    p_dc = desktop_sub.add_parser("configure", help="Print or write a scaffold desktop rules config")
    p_dc.add_argument("--root-path", default="~/Desktop", help="Root desktop path")
    p_dc.add_argument("--staging-dir", help="Staging dir path (default: <root>_Staging)")
    p_dc.add_argument("--output", help="Write config to file instead of stdout")
    p_dc.set_defaults(func=cmd_desktop_configure)

    p_dp = desktop_sub.add_parser("preview", help="Dry-run tidy using config_path + deterministic preflight scan")
    p_dp.add_argument("--config-path", required=True, help="Path to desktop rules YAML")
    p_dp.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_dp.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_dp.set_defaults(func=cmd_desktop_preview)

    p_dr = desktop_sub.add_parser("run", help="Execute tidy using config_path + deterministic preflight scan")
    p_dr.add_argument("--config-path", required=True, help="Path to desktop rules YAML")
    p_dr.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_dr.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_dr.set_defaults(func=cmd_desktop_run)

    p_drs = desktop_sub.add_parser("restore", help="Execute restore using config_path + deterministic preflight walk")
    p_drs.add_argument("--config-path", required=True, help="Path to desktop rules YAML")
    p_drs.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_drs.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_drs.set_defaults(func=cmd_desktop_restore)

    ns = parser.parse_args(argv)
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())

