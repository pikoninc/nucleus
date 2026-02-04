from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

from nucleus.bootstrap_tools import build_tool_registry
from nucleus.contract_store import ContractStore
from nucleus.core.kernel import Kernel
from nucleus.core.runtime_context import RuntimeContext
from nucleus.core.errors import NucleusError, ValidationError
from nucleus.resources import core_contracts_examples_dir, core_contracts_schemas_dir, plugins_dir
from nucleus.resources import plugin_contract_schema_path
from nucleus.registry.plugin_registry import PluginRegistry
from plugins.builtin_desktop.planner import get_planner as get_builtin_desktop_planner
from nucleus.trace.replay import Replay
from nucleus.cli.memory_stub import build_stub as build_memory_stub


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


_APP_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


def _default_desktop_config_path() -> Path:
    """
    Default per-user config location.

    - If XDG_CONFIG_HOME is set, use it.
    - Else use ~/.config
    """
    base = os.environ.get("XDG_CONFIG_HOME")
    if isinstance(base, str) and base.strip():
        return Path(base).expanduser() / "nucleus" / "desktop_rules.yml"
    return Path("~/.config").expanduser() / "nucleus" / "desktop_rules.yml"


def _render_desktop_rules_yaml(*, root_path: str, staging_dir: str) -> str:
    # Keep this in sync with the plugin's schema and common expectations.
    # New spec: folders are absolute paths (or ~-prefixed paths).
    return (
        "version: \"0.1\"\n"
        "plugin: \"builtin.desktop\"\n\n"
        "root:\n"
        f"  path: \"{root_path}\"\n"
        f"  staging_dir: \"{staging_dir}\"\n\n"
        "folders:\n"
        "  documents: \"~/Documents\"\n"
        "  images: \"~/Pictures\"\n"
        "  downloads: \"~/Downloads\"\n\n"
        "rules:\n"
        "  - id: \"rule_screenshots\"\n"
        "    match:\n"
        "      any:\n"
        "        - filename_regex: \"^Screen Shot \"\n"
        "    action:\n"
        "      move_to: \"images\"\n\n"
        "  - id: \"rule_images\"\n"
        "    match:\n"
        "      any:\n"
        "        - mime_prefix: \"image/\"\n"
        "    action:\n"
        "      move_to: \"images\"\n\n"
        "  - id: \"rule_docs\"\n"
        "    match:\n"
        "      any:\n"
        "        - ext_in: [\"pdf\", \"docx\", \"xlsx\", \"pptx\", \"txt\", \"md\"]\n"
        "    action:\n"
        "      move_to: \"documents\"\n\n"
        "  - id: \"rule_tmp_delete\"\n"
        "    match:\n"
        "      any:\n"
        "        - ext_in: [\"tmp\", \"crdownload\", \"download\"]\n"
        "    action:\n"
        "      delete: true\n\n"
        "defaults:\n"
        "  unmatched_action:\n"
        "    move_to: \"downloads\"\n\n"
        "safety:\n"
        "  no_delete: true\n"
        "  collision_strategy: \"suffix_increment\"\n"
        "  ignore_patterns: [\".DS_Store\"]\n"
    )


def _ensure_desktop_config_via_stdio(*, config_path: Path) -> Path | None:
    """
    If config_path exists, return it. Otherwise, offer an interactive wizard to create it.
    Returns None if user declines.
    """
    p = config_path.expanduser()
    if p.exists():
        return p

    def _prompt_stderr(text: str, *, default: str | None = None) -> str:
        suffix = f" [{default}]" if default else ""
        print(f"{text}{suffix}: ", end="", file=sys.stderr, flush=True)
        v = input("").strip()
        if not v and default is not None:
            return default
        return v

    def _confirm_bool_stderr(text: str, *, default: bool = False) -> bool:
        d = "Y/n" if default else "y/N"
        print(f"{text} ({d}): ", end="", file=sys.stderr, flush=True)
        v = input("").strip().lower()
        if not v:
            return bool(default)
        return v in ("y", "yes")

    print(f"Desktop rules config not found: {p}", file=sys.stderr)
    if not _confirm_bool_stderr("Create it now?", default=True):
        print("Cancelled.", file=sys.stderr)
        return None

    root_path = _prompt_stderr("Desktop root path", default="~/Desktop")
    staging_default = f"{root_path}_Staging"
    staging_dir = _prompt_stderr("Staging dir path", default=staging_default)
    content = _render_desktop_rules_yaml(root_path=str(root_path), staging_dir=str(staging_dir))
    _write_text(p, content)
    print(f"OK: wrote config to {p}", file=sys.stderr)
    return p


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


def _load_dotenv_from_file(path: Path) -> None:
    """
    Minimal dotenv loader (no dependencies).

    - Supports lines like KEY=VALUE (optionally prefixed with 'export ')
    - Ignores empty lines and comments (# ...)
    - Strips single/double quotes around values
    - Does not override already-present environment variables
    """
    p = path
    if not p.exists() or not p.is_file():
        return
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return
    for raw_line in txt.splitlines():
        s = raw_line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[len("export ") :].lstrip()
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or not _ENV_KEY_RE.match(k):
            continue
        if k in os.environ:
            continue
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        os.environ[k] = v


def _maybe_load_dotenv() -> None:
    # Default to current working directory.
    cwd = Path.cwd()
    # Common patterns:
    # - `.env` (most tools)
    # - `env` (repo-safe sample can be copied/renamed)
    for name in (".env", "env"):
        _load_dotenv_from_file(cwd / name)


def _format_cli_error(e: Exception) -> str:
    """
    Print-friendly error formatting for CLI commands.
    - Always includes code/message (via __str__) when it's a NucleusError
    - Includes structured `data` payload when present (useful for HTTP errors)
    """
    if isinstance(e, NucleusError) and isinstance(e.data, dict) and e.data:
        data = dict(e.data)
        # Keep error bodies bounded to avoid dumping huge blobs.
        if isinstance(data.get("body"), str) and len(data["body"]) > 2000:
            data["body"] = data["body"][:2000] + "...(truncated)"
        return str(e) + "\n" + json.dumps(data, ensure_ascii=False, indent=2)
    return str(e)


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


def _load_desktop_rules_summary(config_path: str) -> tuple[str, str, Dict[str, str]]:
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
    folders = raw.get("folders", {})
    folders_out: Dict[str, str] = {}
    if isinstance(folders, dict):
        for k, v in folders.items():
            if isinstance(k, str) and k and isinstance(v, str) and v:
                folders_out[k] = v
    return (root_path, staging_dir, folders_out)


def _compute_desktop_scope_roots(config_path: str) -> List[str]:
    root_path, staging_dir, folders = _load_desktop_rules_summary(config_path)
    root_path_e = os.path.expanduser(root_path)
    staging_dir_e = os.path.expanduser(staging_dir)
    to_delete = f"{staging_dir_e}/ToDelete"
    roots: List[str] = [root_path_e, staging_dir_e, to_delete]
    for _k, v in folders.items():
        roots.append(os.path.expanduser(v))
    # de-dupe while preserving order
    out: List[str] = []
    seen = set()
    for r in roots:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


def _desktop_config_is_valid(config_path: Path) -> tuple[bool, str]:
    """
    Validate a desktop rules YAML against the shipped plugin schema.
    Returns (ok, error_summary). Intended for UX/bootstrapping.
    """
    p = config_path.expanduser()
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return (False, f"read_failed: {e!r}")
    if not isinstance(raw, dict):
        return (False, "top_level_not_object")
    try:
        schema_path = plugin_contract_schema_path("builtin.desktop", "desktop_rules.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        import jsonschema

        jsonschema.Draft202012Validator(schema).validate(raw)
    except Exception as e:  # noqa: BLE001
        return (False, str(e))

    # Semantic checks (schema doesn't ensure move_to references a folders key)
    folders = raw.get("folders", {})
    if not isinstance(folders, dict):
        folders = {}
    folder_keys = {k for k in folders.keys() if isinstance(k, str) and k}
    defaults = raw.get("defaults", {})
    if isinstance(defaults, dict):
        ua = defaults.get("unmatched_action")
        if isinstance(ua, dict):
            mt = ua.get("move_to")
            if isinstance(mt, str) and mt and mt not in folder_keys:
                return (False, f"unmatched_action.move_to references unknown folder key: {mt}")
    rules = raw.get("rules", [])
    if isinstance(rules, list):
        for r in rules:
            if not isinstance(r, dict):
                continue
            a = r.get("action")
            if isinstance(a, dict) and isinstance(a.get("move_to"), str):
                mt = str(a["move_to"])
                if mt and mt not in folder_keys:
                    return (False, f"rule.action.move_to references unknown folder key: {mt}")
    return (True, "")


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

    # Validate shipped plugin contract examples (e.g. builtin desktop.tidy sample).
    from nucleus.contract_checks import validate_plugin_contract_examples  # local import to keep CLI startup light
    from nucleus.resources import contracts_dir

    plugin_failures = validate_plugin_contract_examples(contracts_dir() / "plugins")
    if plugin_failures:
        print("Plugin contract examples failed validation:")
        for f in plugin_failures:
            print("- {}: {}".format(f.plugin_id, f.error))
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
            scope_roots = _compute_desktop_scope_roots(str(params["config_path"]))
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
        root_path, _staging_dir, _folders = _load_desktop_rules_summary(config_path)
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
    if bool(getattr(args, "ai", False)):
        return cmd_desktop_configure_ai(args)
    root_path = args.root_path or "~/Desktop"
    staging_dir = args.staging_dir or f"{root_path}_Staging"
    out = _render_desktop_rules_yaml(root_path=str(root_path), staging_dir=str(staging_dir))
    if args.output:
        Path(args.output).expanduser().write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


def cmd_desktop_configure_ai(args: argparse.Namespace) -> int:
    """
    Interactive AI-assisted config generation.

    Users specify only scan roots:
    - source-root (Desktop)
    - dest-root(s) (candidate destinations)

    CLI scans only those roots deterministically, asks an LLM to propose a YAML config,
    then loops review -> feedback -> regenerate until accepted.
    """
    if not bool(getattr(args, "allow_network_intake", False)):
        print("intake.network_denied: pass --allow-network-intake to enable AI config generation")
        return 2

    source_root = getattr(args, "source_root", None)
    dest_roots = list(getattr(args, "dest_root", []) or [])
    if not isinstance(source_root, str) or not source_root.strip():
        raise ValidationError(code="desktop.configure.invalid", message="--source-root is required when --ai is set")
    if not dest_roots:
        raise ValidationError(code="desktop.configure.invalid", message="At least one --dest-root is required when --ai is set")

    source_root = source_root.strip()
    dest_roots = [str(x).strip() for x in dest_roots if isinstance(x, str) and str(x).strip()]
    if not dest_roots:
        raise ValidationError(code="desktop.configure.invalid", message="At least one --dest-root is required when --ai is set")

    # Derived staging dir (aux area for ToDelete aggregation).
    staging_dir = getattr(args, "staging_dir", None)
    if not isinstance(staging_dir, str) or not staging_dir.strip():
        staging_dir = f"{source_root}_Aux"

    config_out = getattr(args, "config_path", None) or getattr(args, "output", None) or str(_default_desktop_config_path())
    config_out_path = Path(str(config_out)).expanduser()

    # Deterministic scan (only user-specified roots)
    tools = build_tool_registry()
    kernel = Kernel(tools)
    run_id = getattr(args, "run_id", "run_cli_configure")
    trace_path = Path(getattr(args, "trace", "trace.jsonl"))

    scope_roots = [os.path.expanduser(source_root), os.path.expanduser(staging_dir)] + [os.path.expanduser(d) for d in dest_roots]
    scope = {"fs_roots": scope_roots, "allow_network": False}

    def scan_source_entries() -> List[Dict[str, Any]]:
        ctx = RuntimeContext(run_id=f"{run_id}_scan_source", dry_run=True, strict_dry_run=True, allow_destructive=False, trace_path=trace_path)
        # list
        list_plan = {
            "plan_id": "plan_configure_scan_source_list_001",
            "intent": {"intent_id": "cli.configure.scan_source", "params": {}, "scope": scope, "context": {"source": "cli"}},
            "steps": [{"step_id": "list", "title": "List source", "phase": "staging", "tool": {"tool_id": "fs.list", "args": {"path": source_root}, "dry_run_ok": True}}],
        }
        out = kernel.run_plan(ctx, list_plan)
        list_res = next((r for r in out.get("results", []) if r.get("step_id") == "list"), None)
        names: List[str] = []
        if isinstance(list_res, dict):
            o = list_res.get("output", {})
            if isinstance(o, dict) and isinstance(o.get("entries"), list):
                names = [e for e in o.get("entries") if isinstance(e, str)]

        if not names:
            return []

        stat_steps = []
        for i, name in enumerate(names, start=1):
            stat_steps.append(
                {
                    "step_id": f"stat_{i:04d}",
                    "title": f"Stat: {name}",
                    "phase": "staging",
                    "tool": {"tool_id": "fs.stat", "args": {"path": f"{source_root}/{name}"}, "dry_run_ok": True},
                }
            )
        stat_plan = {
            "plan_id": "plan_configure_scan_source_stat_001",
            "intent": {"intent_id": "cli.configure.scan_source_stat", "params": {}, "scope": scope, "context": {"source": "cli"}},
            "steps": stat_steps,
        }
        out2 = kernel.run_plan(ctx, stat_plan)
        results = out2.get("results", [])
        snapshot: List[Dict[str, Any]] = []
        if isinstance(results, list):
            for i, name in enumerate(names, start=1):
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

    def scan_dest_tree(dest_root: str, *, max_depth: int) -> List[Dict[str, Any]]:
        ctx = RuntimeContext(run_id=f"{run_id}_scan_dest", dry_run=True, strict_dry_run=True, allow_destructive=False, trace_path=trace_path)
        plan = {
            "plan_id": "plan_configure_scan_dest_walk_001",
            "intent": {"intent_id": "cli.configure.scan_dest", "params": {}, "scope": scope, "context": {"source": "cli"}},
            "steps": [
                {
                    "step_id": "walk",
                    "title": "Walk dest",
                    "phase": "staging",
                    "tool": {"tool_id": "fs.walk", "args": {"path": dest_root, "include_dirs": True, "max_depth": int(max_depth)}, "dry_run_ok": True},
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

    max_depth = int(getattr(args, "max_depth", 2))
    source_entries = scan_source_entries()
    dest_trees = {d: scan_dest_tree(d, max_depth=max_depth) for d in dest_roots}

    # Summarize source extensions (keep small).
    ext_counts: Dict[str, int] = {}
    for e in source_entries:
        name = str(e.get("name") or "")
        lower = name.lower()
        ext = lower.rsplit(".", 1)[-1] if "." in lower and not lower.endswith(".") else ""
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    scan_summary = {
        "source_root": source_root,
        "dest_roots": dest_roots,
        "staging_dir": staging_dir,
        "source": {
            "total": len(source_entries),
            "ext_counts": ext_counts,
            "sample": source_entries[:30],
        },
        "dest": {
            "max_depth": max_depth,
            "trees": dest_trees,
        },
    }

    # LLM request: return YAML config as a string.
    response_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "config_yaml": {"type": "string"},
            "rationale": {"type": "string"},
            "clarify": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["config_yaml", "rationale", "clarify"],
    }

    system_prompt = "\n".join(
        [
            "You are Nucleus Desktop Configure AI.",
            "Your job: propose a desktop tidy YAML config for plugin builtin.desktop.",
            "Constraints:",
            "- Output must be a single YAML config string in config_yaml.",
            "- The user specified scan roots only; you must base your proposal solely on the provided scan_summary.",
            "- root.path MUST equal scan_summary.source_root exactly.",
            "- root.staging_dir MUST equal scan_summary.staging_dir exactly.",
            "- folders values MUST be absolute paths or ~-prefixed paths, and MUST be under one of scan_summary.dest_roots.",
            "- rules.action:",
            "  - move_to: <folders_key> (folders key only)",
            "  - delete: true (means move to staging_dir/ToDelete for later manual deletion)",
            "- Use defaults.unmatched_action.move_to to route unmatched items.",
            "- Do not propose any deletes. Use delete:true only (move to ToDelete).",
            "- Prefer creating subfolders under the given dest_roots when helpful (fs.mkdir will be allowed).",
        ]
    )

    def _validate_and_normalize_config_yaml(yaml_text: str) -> str:
        try:
            obj = yaml.safe_load(yaml_text)
        except Exception as e:  # noqa: BLE001
            raise ValidationError(code="config.invalid_yaml", message="Proposed config_yaml is not valid YAML", data={"error": repr(e)}) from e
        if not isinstance(obj, dict):
            raise ValidationError(code="config.invalid", message="Proposed config must be a YAML mapping/object")

        # Enforce required top-level keys deterministically (LLM may omit them).
        obj["version"] = "0.1"
        obj["plugin"] = "builtin.desktop"
        if "rules" not in obj:
            obj["rules"] = []

        # Enforce root.path and staging_dir deterministically.
        obj.setdefault("root", {})
        if not isinstance(obj.get("root"), dict):
            obj["root"] = {}
        obj["root"]["path"] = source_root
        obj["root"]["staging_dir"] = staging_dir

        # Normalize common LLM YAML mistakes for folders:
        # - folders.key: ["/abs/path"]  -> folders.key: "/abs/path"
        folders_obj = obj.get("folders", {})
        if isinstance(folders_obj, dict):
            for k, v in list(folders_obj.items()):
                if isinstance(v, list):
                    # Some models emit a list of one folder path, or even a list of file paths.
                    # Best-effort: convert into a single directory path using commonpath.
                    if not v:
                        raise ValidationError(
                            code="config.invalid",
                            message="folders values must be strings (absolute paths). Got an empty list.",
                            data={"key": k, "value": v},
                        )
                    if not all(isinstance(item, str) and item.strip() for item in v):
                        raise ValidationError(
                            code="config.invalid",
                            message="folders values must be strings (absolute paths). Got a list with non-strings.",
                            data={"key": k, "value": v},
                        )
                    if len(v) == 1:
                        folders_obj[k] = v[0]
                    else:
                        expanded_items = [os.path.expanduser(item) for item in v]
                        try:
                            cp = os.path.commonpath(expanded_items)
                        except Exception:  # noqa: BLE001
                            cp = expanded_items[0]
                        # If commonpath points to a file (all entries identical), use its dirname.
                        if cp in expanded_items:
                            cp = os.path.dirname(cp) or cp
                        folders_obj[k] = cp
                # Some models emit an object like {path: "/abs/path", ...}
                elif isinstance(v, dict):
                    path_val = v.get("path")
                    if isinstance(path_val, list) and len(path_val) == 1 and isinstance(path_val[0], str):
                        path_val = path_val[0]
                    if not isinstance(path_val, str) or not path_val.strip():
                        path_val = v.get("value")
                    if isinstance(path_val, str) and path_val.strip():
                        folders_obj[k] = path_val
                    else:
                        raise ValidationError(
                            code="config.invalid",
                            message="folders values must be strings (absolute paths). Got an object without a usable 'path'.",
                            data={"key": k, "value": v},
                        )
                # Some models omit the slash after "~" (e.g. "~Downloads")
                elif isinstance(v, str) and v.startswith("~") and not v.startswith("~/"):
                    # Best-effort: interpret "~X" as "~/X"
                    folders_obj[k] = "~/" + v[1:]
            obj["folders"] = folders_obj

            # Coerce folders destinations to be under specified dest_roots.
            # Some models wrongly propose folders under source_root (e.g. Desktop/Archives).
            dest_roots_exp = [os.path.expanduser(d) for d in dest_roots if isinstance(d, str) and d.strip()]
            primary_dest = dest_roots_exp[0] if dest_roots_exp else None
            source_root_exp = os.path.expanduser(source_root)

            def _is_under(root: str, path: str) -> bool:
                try:
                    return os.path.commonpath([root, path]) == root
                except Exception:  # noqa: BLE001
                    return False

            if isinstance(primary_dest, str) and primary_dest:
                for k, v in list(folders_obj.items()):
                    if not isinstance(k, str) or not isinstance(v, str) or not v.strip():
                        continue
                    p = os.path.expanduser(v)

                    # If it's not absolute, place it safely under primary_dest.
                    if not os.path.isabs(p):
                        safe = re.sub(r"[\\/]+", "_", k).strip("_")[:64] or "folder"
                        folders_obj[k] = os.path.join(primary_dest, safe)
                        continue

                    # If already under any dest root, keep as-is.
                    if any(_is_under(dr, p) for dr in dest_roots_exp):
                        continue

                    # If it points under source_root, relocate under primary_dest by its top-level name.
                    if _is_under(source_root_exp, p):
                        rel = os.path.relpath(p, source_root_exp).replace("\\", "/")
                        top = rel.split("/", 1)[0] if isinstance(rel, str) and rel and rel != "." else ""
                        name = top or os.path.basename(p) or k
                        safe = re.sub(r"[\\/]+", "_", str(name)).strip("_")[:64] or "folder"
                        folders_obj[k] = os.path.join(primary_dest, safe)
                        continue

                    # Otherwise, relocate unknown/out-of-scope paths safely under primary_dest by basename.
                    base = os.path.basename(p) or k
                    safe = re.sub(r"[\\/]+", "_", str(base)).strip("_")[:64] or "folder"
                    folders_obj[k] = os.path.join(primary_dest, safe)

        # Normalize common LLM YAML mistakes for defaults/rules:
        # - rules: {unmatched_action: {move_to: ...}}  -> defaults.unmatched_action, rules: []
        rules_obj = obj.get("rules")
        if isinstance(rules_obj, dict) and "unmatched_action" in rules_obj and "defaults" not in obj:
            obj["defaults"] = {"unmatched_action": rules_obj.get("unmatched_action")}
            obj["rules"] = []

        # Case-insensitive normalization for move_to keys (folders keys).
        folders_keys = []
        folders_map = obj.get("folders", {})
        if isinstance(folders_map, dict):
            folders_keys = [k for k in folders_map.keys() if isinstance(k, str)]
        key_by_lower = {k.lower(): k for k in folders_keys}

        def normalize_move_to_key(v: Any) -> Any:
            if not isinstance(v, str) or not v:
                return v
            if v in folders_keys:
                return v
            hit = key_by_lower.get(v.lower())
            return hit or v

        def ensure_folder_key_for_move_to(raw_move_to: Any) -> Any:
            """
            Enforce that move_to points to a folder key.
            If LLM provides a path-like value (e.g. 'Documents/Unmatched' or '/abs/path'),
            create a new folders key mapping to an absolute path under dest_roots.
            """
            mt = normalize_move_to_key(raw_move_to)
            if not isinstance(mt, str) or not mt:
                return mt
            if mt in folders_keys:
                return mt

            # If pattern: "<folderKey>/<subpath>" then derive a new key.
            if "/" in mt and not mt.startswith("/") and not mt.startswith("~/"):
                base, rest = mt.split("/", 1)
                base2 = normalize_move_to_key(base)
                if isinstance(base2, str) and base2 in folders_keys and isinstance(folders_map, dict):
                    base_path_raw = folders_map.get(base2)
                    if isinstance(base_path_raw, str) and base_path_raw:
                        base_path = os.path.expanduser(base_path_raw)
                        if os.path.isabs(base_path):
                            dest_path = f"{base_path}/{rest}"
                            new_key = re.sub(r"[^a-z0-9_]+", "_", f"{base2}_{rest}".lower()).strip("_")[:64] or "unmatched"
                            # Avoid collisions
                            suffix = 1
                            candidate = new_key
                            while candidate in folders_keys:
                                suffix += 1
                                candidate = f"{new_key}_{suffix}"
                            folders_map[candidate] = dest_path
                            folders_keys.append(candidate)
                            key_by_lower[candidate.lower()] = candidate
                            return candidate

            # Absolute path / ~ path: create a new key if it's within dest_roots.
            if mt.startswith("/") or mt.startswith("~/"):
                p = os.path.expanduser(mt)
                if os.path.isabs(p):
                    dest_roots_exp = [os.path.expanduser(d) for d in dest_roots]
                    for dr in dest_roots_exp:
                        try:
                            if os.path.commonpath([dr, p]) == dr:
                                # derive key from relative path
                                rel = os.path.relpath(p, dr).replace("\\", "/")
                                new_key = re.sub(r"[^a-z0-9_]+", "_", rel.lower()).strip("_")[:64] or "unmatched"
                                suffix = 1
                                candidate = new_key
                                while candidate in folders_keys:
                                    suffix += 1
                                    candidate = f"{new_key}_{suffix}"
                                if isinstance(folders_map, dict):
                                    folders_map[candidate] = p
                                folders_keys.append(candidate)
                                key_by_lower[candidate.lower()] = candidate
                                return candidate
                        except Exception:  # noqa: BLE001
                            continue

            # Fallback: keep as-is (schema validation will catch), but this is informative for debugging.
            # If it's just an unknown key, pick a safe existing key (prefer downloads) so config is runnable.
            if folders_keys:
                preferred = None
                for cand in ("downloads", "documents", "images", "pictures"):
                    hit = key_by_lower.get(cand)
                    if hit:
                        preferred = hit
                        break
                return preferred or folders_keys[0]
            return mt

        defaults_obj = obj.get("defaults", {})
        if isinstance(defaults_obj, dict):
            ua = defaults_obj.get("unmatched_action")
            if isinstance(ua, dict):
                # Some models add stray keys like delete: false under unmatched_action.
                if "delete" in ua:
                    ua.pop("delete", None)
                ua_move = ua.get("move_to")
                ua["move_to"] = ensure_folder_key_for_move_to(ua_move)
                defaults_obj["unmatched_action"] = ua
                obj["defaults"] = defaults_obj

        rules_list = obj.get("rules", [])
        if isinstance(rules_list, list):
            # Drop or repair malformed rule items (LLM sometimes outputs partial rules like {"action": {...}}).
            normalized_rules: List[Dict[str, Any]] = []
            for idx, r in enumerate(rules_list, start=1):
                if not isinstance(r, dict):
                    continue
                m = r.get("match")
                a = r.get("action")
                # Must have both match and action to be meaningful; otherwise drop.
                if not isinstance(m, dict) or not isinstance(a, dict):
                    continue
                # Ensure action has a valid move_to/delete shape.
                if isinstance(a.get("move_to"), str):
                    a["move_to"] = ensure_folder_key_for_move_to(a.get("move_to"))
                r["action"] = a

                rid = r.get("id")
                if not isinstance(rid, str) or not rid.strip():
                    r["id"] = f"rule_{idx:03d}"

                # Keep only schema-relevant keys (id/match/action)
                normalized_rules.append({"id": r["id"], "match": m, "action": r["action"]})

            obj["rules"] = normalized_rules

        # Validate against plugin schema.
        schema_path = plugin_contract_schema_path("builtin.desktop", "desktop_rules.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            import jsonschema

            jsonschema.Draft202012Validator(schema).validate(obj)
        except Exception as e:  # noqa: BLE001
            raise ValidationError(code="config.schema_invalid", message="Proposed config does not match schema", data={"error": str(e)}) from e

        # Enforce folder destinations stay under specified dest_roots.
        dest_roots_exp = [os.path.expanduser(d) for d in dest_roots]
        folders = obj.get("folders", {})
        if isinstance(folders, dict):
            for k, v in folders.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    continue
                p = os.path.expanduser(v)
                ok = False
                for dr in dest_roots_exp:
                    try:
                        if os.path.commonpath([dr, p]) == dr:
                            ok = True
                            break
                    except Exception:  # noqa: BLE001
                        continue
                if not ok:
                    raise ValidationError(
                        code="config.invalid",
                        message="folders destination is outside specified --dest-root",
                        data={"key": k, "path": v, "dest_roots": dest_roots},
                    )

        # Return normalized YAML.
        return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)

    def _call_provider(*, input_text: str, extra: str = "") -> Dict[str, Any]:
        from nucleus.intake.provider_loading import load_triage_provider

        api_base = args.api_base
        if api_base is None:
            env_base = os.environ.get("OPENAI_API_BASE")
            if isinstance(env_base, str) and env_base.strip():
                api_base = env_base.strip()

        loaded = load_triage_provider(provider=args.provider, model=args.model, api_base=api_base, api_key_env=args.api_key_env)
        full_input = input_text if not extra else input_text + "\n\n" + extra
        return loaded.provider.triage(input_text=full_input, system_prompt=system_prompt, intent_schema=response_schema)

    base_input = json.dumps(scan_summary, ensure_ascii=False, indent=2)

    max_iters = int(getattr(args, "max_iters", 5))
    accept_first = bool(getattr(args, "accept", False))
    prev_yaml: str | None = None
    for it in range(1, max_iters + 1):
        extra = ""
        if prev_yaml is not None:
            extra = "\n".join(["Previous proposal (YAML):", prev_yaml])
        raw = _call_provider(input_text=base_input, extra=extra)
        if not isinstance(raw, dict):
            raise ValidationError(code="intake.invalid_response", message="Provider did not return an object")
        config_yaml = raw.get("config_yaml")
        rationale = raw.get("rationale", "")
        clarify = raw.get("clarify", [])
        if not isinstance(config_yaml, str) or not config_yaml.strip():
            raise ValidationError(code="intake.invalid_response", message="Provider response missing config_yaml")

        normalized_yaml = _validate_and_normalize_config_yaml(config_yaml)

        # Show proposal.
        print(normalized_yaml)
        if isinstance(rationale, str) and rationale.strip():
            print(f"Rationale: {rationale}", file=sys.stderr)
        if isinstance(clarify, list) and clarify:
            qs = [q for q in clarify if isinstance(q, str) and q.strip()]
            if qs:
                print("Questions:", file=sys.stderr)
                for q in qs:
                    print(f"- {q}", file=sys.stderr)

        if accept_first:
            _write_text(config_out_path, normalized_yaml)
            print(f"OK: wrote config to {config_out_path}")
            return 0

        ans = input("Accept this config? (y/N): ").strip().lower()
        if ans in ("y", "yes"):
            _write_text(config_out_path, normalized_yaml)
            print(f"OK: wrote config to {config_out_path}")
            return 0

        feedback = input("Describe what to improve (free text): ").strip()
        if not feedback:
            print("No feedback provided; stopping.", file=sys.stderr)
            return 2
        prev_yaml = normalized_yaml + "\n\nUser feedback:\n" + feedback

    raise ValidationError(code="desktop.configure.max_iters", message="Max iterations reached without acceptance", data={"max_iters": max_iters})


def _run_desktop_intent_with_scan(*, intent_id: str, config_path: str, run_id: str, trace: str, execute: bool) -> int:
    scope_roots = _compute_desktop_scope_roots(config_path)

    plugins_dir = _default_plugins_dir()
    reg = _load_plugins(plugins_dir)
    plugin_id = reg.require_plugin_id_for_intent(intent_id)
    planner = _resolve_planner(plugin_id)

    intent = {
        "intent_id": intent_id,
        "params": {"config_path": config_path},
        "scope": {"fs_roots": scope_roots, "allow_network": False},
        "context": {"source": "cli"},
    }

    tools = build_tool_registry()
    kernel = Kernel(tools)

    scan_trace = Path(trace).with_suffix(".preflight.jsonl")
    # tidy.run / tidy.preview
    intent["params"]["entries"] = _preflight_scan_entries(kernel=kernel, plugins_intent=intent, run_id=f"{run_id}_preflight", trace_path=scan_trace)

    ctx = RuntimeContext(
        run_id=run_id,
        dry_run=not execute,
        strict_dry_run=not execute,
        allow_destructive=False,
        trace_path=Path(trace),
    )
    try:
        out = kernel.run_intent(ctx, intent, planner)
    except Exception as e:  # noqa: BLE001
        print(_format_cli_error(e))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_desktop_preview(args: argparse.Namespace) -> int:
    cfg = Path(args.config_path).expanduser() if args.config_path else _default_desktop_config_path()
    if not cfg.exists():
        print(f"config.not_found: {cfg} (run: nuc desktop configure --ai ...)")
        return 2
    return _run_desktop_intent_with_scan(
        intent_id="desktop.tidy.preview",
        config_path=str(cfg),
        run_id=args.run_id,
        trace=args.trace,
        execute=False,
    )


def cmd_desktop_run(args: argparse.Namespace) -> int:
    cfg = Path(args.config_path).expanduser() if args.config_path else _default_desktop_config_path()
    if not cfg.exists():
        print(f"config.not_found: {cfg} (run: nuc desktop configure --ai ...)")
        return 2
    return _run_desktop_intent_with_scan(
        intent_id="desktop.tidy.run",
        config_path=str(cfg),
        run_id=args.run_id,
        trace=args.trace,
        execute=True,
    )


def cmd_desktop_ai(args: argparse.Namespace) -> int:
    """
    Natural-language desktop tidy via intake (OpenAI or other provider), then execute deterministically.

    Flow:
    - ensure config exists (stdio wizard on first run)
    - set strict scope roots from config
    - intake triage to select an intent_id
    - execute preview/run/restore deterministically with preflight scans
    """
    if not bool(getattr(args, "allow_network_intake", False)):
        print("intake.network_denied: pass --allow-network-intake to enable LLM triage")
        return 2

    text = args.text
    if text is None:
        try:
            text = sys.stdin.read()
        except Exception:  # noqa: BLE001
            text = ""
    if not isinstance(text, str) or not text.strip():
        print("intake.invalid: missing input text (use --text or pipe stdin)")
        return 2

    cfg = Path(args.config_path).expanduser() if args.config_path else _default_desktop_config_path()
    desired_source_root = getattr(args, "source_root", None)
    desired_dest_roots = list(getattr(args, "dest_root", []) or [])
    wants_bootstrap = bool((isinstance(desired_source_root, str) and desired_source_root.strip()) or desired_dest_roots)
    force_bootstrap = False
    if cfg.exists():
        ok, _err = _desktop_config_is_valid(cfg)
        if not ok:
            # Existing config is incompatible with the current schema (e.g., old relative folder names like "Screenshots").
            # Keep it intact and generate a new config next to it.
            generated = cfg.with_name(cfg.stem + ".generated" + cfg.suffix)
            print(f"config.schema_invalid: existing config is incompatible; generating new config at {generated}", file=sys.stderr)
            cfg = generated
            force_bootstrap = True
        elif wants_bootstrap:
            # User provided scan roots; prefer them over an existing config (which may point elsewhere).
            generated = cfg.with_name(cfg.stem + ".generated" + cfg.suffix)
            print(f"config.bootstrap: generating config from --source-root/--dest-root at {generated}", file=sys.stderr)
            cfg = generated
            force_bootstrap = True

    if force_bootstrap or (not cfg.exists()):
        # Bootstrap config via configure --ai, then continue.
        source_root = getattr(args, "source_root", None)
        dest_roots = list(getattr(args, "dest_root", []) or [])
        if not isinstance(source_root, str) or not source_root.strip():
            source_root = input("Source root to scan (e.g. ~/Desktop): ").strip()
        if not dest_roots:
            raw = input("Destination roots to scan (comma-separated, e.g. ~/Documents,~/Pictures): ").strip()
            dest_roots = [s.strip() for s in raw.split(",") if s.strip()]
        if not dest_roots:
            print("desktop.ai.invalid: missing --dest-root (or interactive input)", file=sys.stderr)
            return 2

        class _Shim:
            pass

        shim = _Shim()
        # Configure --ai args
        shim.allow_network_intake = True
        shim.source_root = str(source_root)
        shim.dest_root = list(dest_roots)
        shim.staging_dir = getattr(args, "staging_dir", None)
        shim.config_path = str(cfg)
        shim.output = None
        shim.accept = True  # accept first proposal for bootstrap
        shim.max_iters = int(getattr(args, "configure_max_iters", 3))
        shim.max_depth = int(getattr(args, "configure_max_depth", 2))
        shim.trace = getattr(args, "trace", "trace.jsonl")
        shim.run_id = getattr(args, "run_id", "run_cli") + "_bootstrap"
        shim.provider = getattr(args, "configure_provider", None) or args.provider
        shim.model = getattr(args, "configure_model", None) or args.model
        shim.api_base = getattr(args, "api_base", None)
        shim.api_key_env = getattr(args, "api_key_env", "OPENAI_API_KEY")

        rc = cmd_desktop_configure_ai(shim)  # writes cfg
        if rc != 0:
            return int(rc)
        if not cfg.exists():
            print("config.not_found: bootstrap did not write config", file=sys.stderr)
            return 2

    # Use config to define scope (intake must not invent roots).
    scope = {"fs_roots": _compute_desktop_scope_roots(str(cfg)), "allow_network": False}

    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else _default_plugins_dir()
    reg = _load_plugins(plugins_dir)
    intents = reg.list_intents()
    # Constrain to desktop intents for safety/clarity.
    intents = [it for it in intents if isinstance(it, dict) and str(it.get("intent_id", "")).startswith("desktop.")]

    try:
        from nucleus.intake.provider_loading import load_triage_provider
        from nucleus.intake.triage import triage_text_to_intent

        api_base = args.api_base
        if api_base is None:
            env_base = os.environ.get("OPENAI_API_BASE")
            if isinstance(env_base, str) and env_base.strip():
                api_base = env_base.strip()

        loaded = load_triage_provider(
            provider=args.provider,
            model=args.model,
            api_base=api_base,
            api_key_env=args.api_key_env,
        )
        res = triage_text_to_intent(
            input_text=str(text),
            intents_catalog=intents,
            scope=scope,
            context={"source": "cli.desktop.ai"},
            provider=loaded.provider,
            provider_id=loaded.provider_id,
            model=loaded.model,
            allow_network=True,
        )
    except Exception as e:  # noqa: BLE001
        print(_format_cli_error(e))
        return 1

    intent = res.intent
    iid = intent.get("intent_id")
    if iid in ("desktop.tidy.preview", "desktop.tidy.run"):
        params = intent.get("params", {}) if isinstance(intent.get("params"), dict) else {}
        if not isinstance(params.get("config_path"), str) or not params.get("config_path"):
            params["config_path"] = str(cfg)
        intent["params"] = params

    # Execute based on chosen intent.
    if iid == "desktop.tidy.preview":
        return _run_desktop_intent_with_scan(
            intent_id="desktop.tidy.preview",
            config_path=str(cfg),
            run_id=args.run_id,
            trace=args.trace,
            execute=False,
        )
    if iid == "desktop.tidy.run":
        return _run_desktop_intent_with_scan(
            intent_id="desktop.tidy.run",
            config_path=str(cfg),
            run_id=args.run_id,
            trace=args.trace,
            execute=True,
        )

    # Fallback: just print the selected intent for unsupported desktop intents.
    print(json.dumps(intent, ensure_ascii=False, indent=2))
    return 0


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


def cmd_intake(args: argparse.Namespace) -> int:
    """
    LLM-based triage to produce a contract-shaped Intent (no tool execution).
    """
    # Require explicit opt-in for network usage in intake.
    if not bool(getattr(args, "allow_network_intake", False)):
        print("intake.network_denied: pass --allow-network-intake to enable LLM triage")
        return 2

    text = args.text
    if text is None:
        # Read from stdin if not provided.
        try:
            text = sys.stdin.read()
        except Exception:  # noqa: BLE001
            text = ""
    if not isinstance(text, str) or not text.strip():
        print("intake.invalid: missing input text (use --text or pipe stdin)")
        return 2

    # Load available intents from plugins (builtin samples included).
    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else _default_plugins_dir()
    reg = _load_plugins(plugins_dir)
    intents = reg.list_intents()

    scope_roots = list(args.scope_root or [])
    if not scope_roots:
        scope_roots = ["."]
    scope = {"fs_roots": scope_roots, "allow_network": False}

    try:
        from nucleus.intake.provider_loading import load_triage_provider
        from nucleus.intake.triage import triage_text_to_intent

        api_base = args.api_base
        if api_base is None:
            env_base = os.environ.get("OPENAI_API_BASE")
            if isinstance(env_base, str) and env_base.strip():
                api_base = env_base.strip()

        loaded = load_triage_provider(
            provider=args.provider,
            model=args.model,
            api_base=api_base,
            api_key_env=args.api_key_env,
        )
        res = triage_text_to_intent(
            input_text=text,
            intents_catalog=intents,
            scope=scope,
            context={"source": "cli"},
            provider=loaded.provider,
            provider_id=loaded.provider_id,
            model=loaded.model,
            allow_network=True,
        )
    except Exception as e:  # noqa: BLE001
        print(_format_cli_error(e))
        return 1

    if args.full:
        out = {
            "intent": res.intent,
            "triage": {"provider": res.provider, "model": res.model},
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps(res.intent, ensure_ascii=False, indent=2))
    return 0


def _alfred_query_to_intent(*, query: str) -> Dict[str, Any]:
    """
    Alfred input adapter (minimal):
    - parses a query string into a contract-shaped Intent
    - does not execute tools
    """
    if not isinstance(query, str) or not query.strip():
        raise ValidationError(code="alfred.invalid", message="query must be a non-empty string")

    tokens = shlex.split(query.strip())
    if not tokens:
        raise ValidationError(code="alfred.invalid", message="query must be a non-empty string")

    # Normalize leading command tokens.
    if tokens[0] == "desktop" and len(tokens) >= 2 and tokens[1] == "tidy":
        tokens = ["tidy", *tokens[2:]]
    if tokens[0] == "desktop.tidy":
        tokens = ["tidy", *tokens[1:]]

    if tokens[0] != "tidy":
        raise ValidationError(code="alfred.invalid", message="Unsupported command (expected: tidy ...)", data={"tokens": tokens})

    subcmd = tokens[1] if len(tokens) >= 2 else ""

    # Defaults:
    # - `tidy <config_path>` => preview
    # - `tidy preview|run|restore <config_path>`
    # - `tidy configure`
    if subcmd in ("configure",):
        intent_id = "desktop.tidy.configure"
        params: Dict[str, Any] = {}
        scope_roots = ["."]
    elif subcmd in ("preview", "run", "restore"):
        if len(tokens) < 3:
            raise ValidationError(code="alfred.invalid", message=f"Missing config_path for tidy {subcmd}")
        config_path = tokens[2]
        if subcmd == "restore":
            raise ValidationError(code="alfred.invalid", message="Unsupported command: tidy restore")
        intent_id = f"desktop.tidy.{subcmd}"
        params = {"config_path": config_path}
        scope_roots = _compute_desktop_scope_roots(config_path)
    else:
        # `tidy <config_path>`
        if len(tokens) < 2:
            raise ValidationError(code="alfred.invalid", message="Missing config_path (try: tidy preview <config_path>)")
        config_path = tokens[1]
        intent_id = "desktop.tidy.preview"
        params = {"config_path": config_path}
        scope_roots = _compute_desktop_scope_roots(config_path)

    return {
        "intent_id": intent_id,
        "params": params,
        "scope": {"fs_roots": scope_roots, "allow_network": False},
        "context": {"source": "alfred"},
    }


def cmd_alfred(args: argparse.Namespace) -> int:
    """
    Alfred input adapter: query -> Intent JSON (no execution).
    Alfred can pass its `{query}` string into `--query`.
    """
    query = args.query
    if query is None:
        try:
            query = sys.stdin.read()
        except Exception:  # noqa: BLE001
            query = ""
    try:
        intent = _alfred_query_to_intent(query=str(query))
    except Exception as e:  # noqa: BLE001
        print(_format_cli_error(e))
        return 1
    print(json.dumps(intent, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    if str(os.environ.get("NUCLEUS_DISABLE_DOTENV", "")).strip().lower() not in ("1", "true", "yes"):
        _maybe_load_dotenv()
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

    p_intake = sub.add_parser("intake", help="LLM triage: text -> Intent (no execution)")
    p_intake.add_argument("--text", help="Input text. If omitted, read from stdin.")
    p_intake.add_argument("--provider", default="openai.responses", help="Provider ID or 'module:object' spec")
    p_intake.add_argument("--model", default="gpt-4o-mini", help="Model name (provider-specific)")
    p_intake.add_argument("--api-base", help="Provider API base URL (when supported)")
    p_intake.add_argument("--api-key-env", default="OPENAI_API_KEY", help="API key env var name (when supported)")
    p_intake.add_argument("--plugins-dir", default=str(_default_plugins_dir()), help="Plugins directory (for intent catalog)")
    p_intake.add_argument("--scope-root", action="append", default=[], help="Filesystem scope root for emitted Intent (repeatable)")
    p_intake.add_argument("--allow-network-intake", action="store_true", help="Enable OpenAI API call for intake triage")
    p_intake.add_argument("--full", action="store_true", help="Output intent + triage metadata JSON")
    p_intake.set_defaults(func=cmd_intake)

    p_alfred = sub.add_parser("alfred", help="Alfred input adapter: query -> Intent JSON (no execution)")
    p_alfred.add_argument("--query", help="Alfred query string (if omitted, read stdin)")
    p_alfred.set_defaults(func=cmd_alfred)

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
    p_dc.add_argument("--ai", action="store_true", help="Generate config via AI + deterministic scans (interactive)")
    p_dc.add_argument("--source-root", help="Scan source root (e.g. ~/Desktop) (required with --ai)")
    p_dc.add_argument("--dest-root", action="append", default=[], help="Destination root (repeatable) (required with --ai)")
    p_dc.add_argument("--config-path", help="Write generated config to this path (default: XDG config)")
    p_dc.add_argument("--accept", action="store_true", help="Accept first proposal and write without prompts")
    p_dc.add_argument("--max-iters", type=int, default=5, help="Max propose/review iterations (default: 5)")
    p_dc.add_argument("--max-depth", type=int, default=2, help="Max depth for dest-root scan (default: 2)")
    p_dc.add_argument("--provider", default="openai.responses", help="Provider ID or 'module:object' spec (used with --ai)")
    p_dc.add_argument("--model", default="gpt-4o-mini", help="Model name (provider-specific) (used with --ai)")
    p_dc.add_argument("--api-base", help="Provider API base URL (when supported)")
    p_dc.add_argument("--api-key-env", default="OPENAI_API_KEY", help="API key env var name (when supported)")
    p_dc.add_argument("--allow-network-intake", action="store_true", help="Enable provider API call for AI config generation")
    p_dc.set_defaults(func=cmd_desktop_configure)

    p_dp = desktop_sub.add_parser("preview", help="Dry-run tidy using config_path + deterministic preflight scan")
    p_dp.add_argument("--config-path", help="Path to desktop rules YAML (default: XDG config)")
    p_dp.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_dp.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_dp.set_defaults(func=cmd_desktop_preview)

    p_dr = desktop_sub.add_parser("run", help="Execute tidy using config_path + deterministic preflight scan")
    p_dr.add_argument("--config-path", help="Path to desktop rules YAML (default: XDG config)")
    p_dr.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_dr.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_dr.set_defaults(func=cmd_desktop_run)

    p_dai = desktop_sub.add_parser("ai", help="Desktop tidy via intake (natural language -> intent -> deterministic execution)")
    p_dai.add_argument("--text", help="Natural language input. If omitted, read from stdin.")
    p_dai.add_argument("--config-path", help="Desktop rules config path (default: XDG config)")
    p_dai.add_argument("--source-root", help="(Bootstrap) Scan source root when config is missing")
    p_dai.add_argument("--dest-root", action="append", default=[], help="(Bootstrap) Destination root (repeatable) when config is missing")
    p_dai.add_argument("--configure-provider", help="(Bootstrap) Provider for configure --ai (default: --provider)")
    p_dai.add_argument("--configure-model", help="(Bootstrap) Model for configure --ai (default: --model)")
    p_dai.add_argument("--configure-max-iters", type=int, default=3, help="(Bootstrap) Max configure iterations (default: 3)")
    p_dai.add_argument("--configure-max-depth", type=int, default=2, help="(Bootstrap) Max dest scan depth (default: 2)")
    p_dai.add_argument("--plugins-dir", default=str(_default_plugins_dir()), help="Plugins directory (for intent catalog)")
    p_dai.add_argument("--provider", default="openai.responses", help="Provider ID or 'module:object' spec")
    p_dai.add_argument("--model", default="gpt-4o-mini", help="Model name (provider-specific)")
    p_dai.add_argument("--api-base", help="Provider API base URL (when supported)")
    p_dai.add_argument("--api-key-env", default="OPENAI_API_KEY", help="API key env var name (when supported)")
    p_dai.add_argument("--allow-network-intake", action="store_true", help="Enable OpenAI API call for intake triage")
    p_dai.add_argument("--trace", default="trace.jsonl", help="Trace output path (jsonl)")
    p_dai.add_argument("--run-id", default="run_cli", help="Run ID for trace correlation")
    p_dai.set_defaults(func=cmd_desktop_ai)

    ns = parser.parse_args(argv)
    try:
        return int(ns.func(ns))
    except Exception as e:  # noqa: BLE001
        print(_format_cli_error(e))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

