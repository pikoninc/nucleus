from __future__ import annotations

import fnmatch
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema
import yaml

from nucleus.core.errors import ValidationError
from nucleus.core.planner import Planner
from nucleus.resources import plugin_contract_schema_path


class BuiltinDesktopPlanner(Planner):
    """
    Config-driven desktop tidy plugin.

    Design goals:
    - Users own a readable config file (YAML).
    - Plugin developers own a deterministic "sorting engine" (config -> Plan).
    - Execution is always via deterministic tools from a Plan (no AI-generated commands).

    Supported intents (latest implementation only):
    - desktop.tidy: legacy defaults (no config file; deterministic; kept for backward compatibility)
    - desktop.tidy.configure: scaffold config (human-in-the-loop; no filesystem changes)
    - desktop.tidy.preview: config + entries snapshot -> Plan (dry-run friendly)
    - desktop.tidy.run: config + entries snapshot -> Plan (execute)
    - desktop.tidy.restore: config + staging walk snapshot -> Plan (execute)
    """

    def plan(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(intent, dict):
            raise ValidationError(code="intent.invalid", message="Intent must be an object")

        intent_id = intent.get("intent_id")
        if not isinstance(intent_id, str) or not intent_id:
            raise ValidationError(code="intent.invalid", message="Missing or invalid intent_id")

        params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
        scope = intent.get("scope") if isinstance(intent.get("scope"), dict) else {}
        context = intent.get("context") if isinstance(intent.get("context"), dict) else {}

        fs_roots = scope.get("fs_roots")
        if not isinstance(fs_roots, list) or len(fs_roots) < 1:
            raise ValidationError(code="scope.missing", message="scope.fs_roots must be a non-empty array")

        include_dirs = bool(params.get("include_dirs", False))
        exclude = params.get("exclude", [])
        if exclude is None:
            exclude = []
        if not isinstance(exclude, list) or any((not isinstance(x, str)) for x in exclude):
            raise ValidationError(code="intent.invalid", message="params.exclude must be an array of strings when provided")

        config_path = params.get("config_path")
        if intent_id in ("desktop.tidy.preview", "desktop.tidy.run", "desktop.tidy.restore"):
            if not isinstance(config_path, str) or not config_path:
                raise ValidationError(code="intent.invalid", message="params.config_path is required")
        elif intent_id == "desktop.tidy.configure":
            if config_path is not None and (not isinstance(config_path, str) or not config_path):
                raise ValidationError(code="intent.invalid", message="params.config_path must be a non-empty string when provided")
        elif intent_id == "desktop.tidy":
            # Legacy intent: config_path is optional/ignored; planner will use built-in defaults.
            pass

        intent_obj = {
            "intent_id": intent_id,
            "params": {
                "config_path": config_path,
                "target_dir": params.get("target_dir"),
                "staging_dir": params.get("staging_dir"),
                "overwrite_strategy": params.get("overwrite_strategy"),
                "include_dirs": include_dirs,
                "exclude": exclude,
                "entries": params.get("entries"),
                "sorted_entries": params.get("sorted_entries"),
            },
            "scope": {"fs_roots": fs_roots, "allow_network": bool(scope.get("allow_network", False))},
            "context": context or {},
        }

        if intent_id == "desktop.tidy":
            return self._plan_legacy_tidy(intent_obj)
        if intent_id == "desktop.tidy.configure":
            return self._plan_configure(intent_obj)
        if intent_id == "desktop.tidy.preview":
            return self._plan_tidy_from_config(intent_obj, preview=True)
        if intent_id == "desktop.tidy.run":
            return self._plan_tidy_from_config(intent_obj, preview=False)
        if intent_id == "desktop.tidy.restore":
            return self._plan_restore_from_config(intent_obj)
        raise ValidationError(code="intent.unknown", message=f"Unsupported intent_id: {intent_id}")

    def _plan_legacy_tidy(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Backward-compatible intent `desktop.tidy`.

        This path does not require a config file; instead it uses a built-in rule set and a
        default staging directory `<target_dir>/_Sorted`.
        """
        params = intent.get("params", {}) if isinstance(intent.get("params"), dict) else {}
        target_dir = params.get("target_dir")
        if target_dir is None:
            target_dir = "~/Desktop"
        if not isinstance(target_dir, str) or not target_dir:
            raise ValidationError(code="intent.invalid", message="params.target_dir must be a non-empty string when provided")

        root_path = self._expand_user(target_dir)
        staging_dir = params.get("staging_dir")
        if staging_dir is None:
            staging_dir = f"{root_path}/_Sorted"
        if not isinstance(staging_dir, str) or not staging_dir:
            raise ValidationError(code="intent.invalid", message="params.staging_dir must be a non-empty string when provided")
        staging_dir = self._expand_user(staging_dir)

        fs_roots = intent.get("scope", {}).get("fs_roots", [])
        if not isinstance(fs_roots, list):
            fs_roots = []
        fs_roots_expanded = [self._expand_user(x) for x in fs_roots if isinstance(x, str)]
        if root_path not in fs_roots_expanded or staging_dir not in fs_roots_expanded:
            raise ValidationError(
                code="scope.invalid",
                message="scope.fs_roots must include both params.target_dir and the resolved staging_dir",
                data={"required": [root_path, staging_dir], "fs_roots": fs_roots},
            )

        overwrite_strategy = params.get("overwrite_strategy")
        collision_strategy = "suffix_increment"
        if overwrite_strategy in ("error", "overwrite", "skip"):
            collision_strategy = str(overwrite_strategy)

        cfg: Dict[str, Any] = {
            "version": "0.1",
            "plugin": "builtin.desktop",
            "root": {"path": root_path, "staging_dir": staging_dir},
            "folders": {
                "screenshots": "Screenshots",
                "documents": "Documents",
                "images": "Images",
                "archives": "Archives",
                "misc": "Misc",
            },
            "rules": [
                {
                    "id": "legacy_screenshots",
                    "match": {"any": [{"filename_regex": r"^Screen Shot "}]},
                    "action": {"move_to": "screenshots"},
                },
                {
                    "id": "legacy_images",
                    "match": {"any": [{"ext_in": ["png", "jpg", "jpeg", "gif", "webp", "heic", "svg"]}]},
                    "action": {"move_to": "images"},
                },
                {
                    "id": "legacy_documents",
                    "match": {"any": [{"ext_in": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"]}]},
                    "action": {"move_to": "documents"},
                },
                {
                    "id": "legacy_archives",
                    "match": {"any": [{"ext_in": ["zip", "7z", "rar", "tar", "gz", "bz2", "xz"]}]},
                    "action": {"move_to": "archives"},
                },
            ],
            "defaults": {"unmatched_action": {"move_to": "misc"}},
            "safety": {"no_delete": True, "require_staging": True, "collision_strategy": collision_strategy, "ignore_patterns": [".DS_Store"]},
        }

        steps: List[Dict[str, Any]] = [
            {
                "step_id": "staging_list_root",
                "title": "List root directory (staging)",
                "phase": "staging",
                "tool": {"tool_id": "fs.list", "args": {"path": root_path}, "dry_run_ok": True},
                "preconditions": [f"Scope includes {root_path}"],
            },
            {
                "step_id": "commit_create_sorted_dir",
                "title": "Create _Sorted staging dir (commit)",
                "phase": "commit",
                "tool": {"tool_id": "fs.mkdir", "args": {"path": staging_dir, "parents": True, "exist_ok": True}, "dry_run_ok": True},
                "expected_effects": [{"kind": "fs_mkdir", "summary": f"Create {staging_dir} if missing", "resources": [staging_dir]}],
            },
        ]

        entries = params.get("entries")
        move_steps, created_dirs = self._build_moves_from_entries_config(
            root_path=root_path,
            staging_dir=staging_dir,
            cfg=cfg,
            entries=entries,
            include_dirs=bool(params.get("include_dirs", False)),
            exclude=list(params.get("exclude", [])) if isinstance(params.get("exclude"), list) else [],
        )

        for d in created_dirs:
            steps.append(
                {
                    "step_id": f"commit_mkdir_{d.replace('/', '_')}",
                    "title": f"Create folder (commit): {d}",
                    "phase": "commit",
                    "tool": {"tool_id": "fs.mkdir", "args": {"path": d, "parents": True, "exist_ok": True}, "dry_run_ok": True},
                    "expected_effects": [{"kind": "fs_mkdir", "summary": f"Create {d} if missing", "resources": [d]}],
                }
            )

        steps.extend(move_steps)

        summary = "Desktop tidy (legacy): no entries provided"
        if move_steps:
            summary = f"Desktop tidy (legacy): {len(move_steps)} move step(s) planned into {staging_dir}"
        steps.append(
            {
                "step_id": "commit_notify",
                "title": "Notify summary (commit)",
                "phase": "commit",
                "tool": {"tool_id": "notify.send", "args": {"message": summary}, "dry_run_ok": True},
            }
        )

        return {
            "plan_id": "plan_desktop_tidy_legacy_001",
            "intent": intent,
            "risk": {"level": "low", "reasons": ["Built-in legacy rules; no deletes; deterministic tools only."]},
            "steps": steps,
        }

    def _load_rules_config(self, config_path: str) -> Dict[str, Any]:
        p = Path(config_path).expanduser()
        if not p.exists():
            raise ValidationError(code="config.not_found", message=f"Config not found: {config_path}")
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            raise ValidationError(code="config.invalid_yaml", message="Failed to parse YAML config", data={"error": repr(e)}) from e
        if not isinstance(raw, dict):
            raise ValidationError(code="config.invalid", message="Config must be a YAML mapping/object at top-level")

        schema_path = plugin_contract_schema_path("builtin.desktop", "desktop_rules.schema.json")
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            raise ValidationError(code="config.schema_missing", message="Config schema missing or unreadable", data={"path": str(schema_path)}) from e

        try:
            jsonschema.Draft202012Validator(schema).validate(raw)
        except jsonschema.ValidationError as e:
            raise ValidationError(
                code="config.schema_invalid",
                message="Config does not match schema",
                data={"error": e.message, "path": list(e.path), "schema_path": list(e.schema_path)},
            ) from e
        except Exception as e:  # noqa: BLE001
            raise ValidationError(code="config.schema_invalid", message="Config does not match schema", data={"error": repr(e)}) from e

        return raw

    def _expand_user(self, path_str: str) -> str:
        # Use os.path.expanduser so "~" expansion respects tests that patch $HOME.
        return os.path.expanduser(path_str)

    def _plan_configure(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Human-in-the-loop: returns a plan that only prints a scaffold config.
        (No filesystem mutations; dry-run friendly.)
        """
        # Note: plugin can't write files (no tool for it); we return a scaffold as output text.
        target_dir = "~/Desktop"
        staging_dir = "~/Desktop_Staging"
        scaffold = (
            "version: \"0.1\"\n"
            "plugin: \"builtin.desktop\"\n\n"
            "root:\n"
            f"  path: \"{target_dir}\"\n"
            f"  staging_dir: \"{staging_dir}\"\n\n"
            "folders:\n"
            "  screenshots: \"Screenshots\"\n"
            "  images: \"Images\"\n"
            "  documents: \"Documents\"\n"
            "  archives: \"Archives\"\n"
            "  misc: \"Misc\"\n\n"
            "rules:\n"
            "  - id: \"rule_screenshots\"\n"
            "    match:\n"
            "      any:\n"
            "        - filename_regex: \"^Screen Shot \"\n"
            "    action:\n"
            "      move_to: \"screenshots\"\n\n"
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
            "defaults:\n"
            "  unmatched_action:\n"
            "    move_to: \"misc\"\n\n"
            "safety:\n"
            "  no_delete: true\n"
            "  require_staging: true\n"
            "  collision_strategy: \"suffix_increment\"\n"
            "  ignore_patterns: [\".DS_Store\"]\n"
        )
        return {
            "plan_id": "plan_desktop_tidy_configure_001",
            "intent": intent,
            "risk": {"level": "low", "reasons": ["Configuration scaffolding only (no filesystem changes)."]},
            "steps": [
                {
                    "step_id": "commit_notify_scaffold",
                    "title": "Print scaffold config (commit)",
                    "phase": "commit",
                    "tool": {"tool_id": "notify.send", "args": {"message": scaffold}, "dry_run_ok": True},
                }
            ],
        }

    def _plan_tidy_from_config(self, intent: Dict[str, Any], *, preview: bool) -> Dict[str, Any]:
        config_path = intent["params"].get("config_path")
        if not isinstance(config_path, str) or not config_path:
            raise ValidationError(code="intent.invalid", message="params.config_path is required for desktop.tidy.run/preview")

        cfg = self._load_rules_config(config_path)
        root_path = self._expand_user(str(cfg["root"]["path"]))
        staging_dir = self._expand_user(str(cfg["root"]["staging_dir"]))

        fs_roots = intent.get("scope", {}).get("fs_roots", [])
        if not isinstance(fs_roots, list):
            fs_roots = []
        fs_roots_expanded = [self._expand_user(x) for x in fs_roots if isinstance(x, str)]
        if root_path not in fs_roots_expanded or staging_dir not in fs_roots_expanded:
            raise ValidationError(
                code="scope.invalid",
                message="scope.fs_roots must include both config.root.path and config.root.staging_dir",
                data={"required": [root_path, staging_dir], "fs_roots": fs_roots},
            )

        steps: List[Dict[str, Any]] = [
            {
                "step_id": "staging_list_root",
                "title": "List root directory (staging)",
                "phase": "staging",
                "tool": {"tool_id": "fs.list", "args": {"path": root_path}, "dry_run_ok": True},
                "preconditions": [f"Scope includes {root_path}"],
            },
            {
                "step_id": "commit_create_staging_dir",
                "title": "Create staging_dir (commit)",
                "phase": "commit",
                "tool": {"tool_id": "fs.mkdir", "args": {"path": staging_dir, "parents": True, "exist_ok": True}, "dry_run_ok": True},
                "expected_effects": [
                    {"kind": "fs_mkdir", "summary": f"Create {staging_dir} if missing", "resources": [staging_dir]}
                ],
            },
        ]

        entries = intent.get("params", {}).get("entries")
        move_steps, created_dirs = self._build_moves_from_entries_config(
            root_path=root_path,
            staging_dir=staging_dir,
            cfg=cfg,
            entries=entries,
            include_dirs=bool(intent["params"].get("include_dirs", False)),
            exclude=list(intent["params"].get("exclude", [])),
        )

        for d in created_dirs:
            steps.append(
                {
                    "step_id": f"commit_mkdir_{d.replace('/', '_')}",
                    "title": f"Create folder (commit): {d}",
                    "phase": "commit",
                    "tool": {"tool_id": "fs.mkdir", "args": {"path": d, "parents": True, "exist_ok": True}, "dry_run_ok": True},
                    "expected_effects": [{"kind": "fs_mkdir", "summary": f"Create {d} if missing", "resources": [d]}],
                }
            )

        steps.extend(move_steps)

        summary = "Desktop tidy (config): no entries provided"
        if move_steps:
            summary = f"Desktop tidy (config): {len(move_steps)} move step(s) planned into {staging_dir}"

        steps.append(
            {
                "step_id": "commit_notify",
                "title": "Notify summary (commit)",
                "phase": "commit",
                "tool": {"tool_id": "notify.send", "args": {"message": summary}, "dry_run_ok": True},
            }
        )

        return {
            "plan_id": "plan_desktop_tidy_preview_001" if preview else "plan_desktop_tidy_run_001",
            "intent": intent,
            "risk": {"level": "low", "reasons": ["Config-driven staging; no deletes; deterministic tools only."]},
            "steps": steps,
        }

    def _build_moves_from_entries_config(
        self,
        *,
        root_path: str,
        staging_dir: str,
        cfg: Dict[str, Any],
        entries: Any,
        include_dirs: bool,
        exclude: List[str],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        if entries is None:
            return ([], [])
        if not isinstance(entries, list):
            raise ValidationError(code="intent.invalid", message="params.entries must be an array when provided")

        ignore_patterns: List[str] = []
        safety = cfg.get("safety", {}) if isinstance(cfg.get("safety"), dict) else {}
        if isinstance(safety.get("ignore_patterns"), list):
            ignore_patterns = [p for p in safety["ignore_patterns"] if isinstance(p, str)]

        collision_strategy = safety.get("collision_strategy", "suffix_increment")
        if collision_strategy not in ("error", "overwrite", "skip", "suffix_increment"):
            collision_strategy = "suffix_increment"

        folders_map = cfg.get("folders", {}) if isinstance(cfg.get("folders"), dict) else {}
        defaults = cfg.get("defaults", {}) if isinstance(cfg.get("defaults"), dict) else {}
        unmatched_action = defaults.get("unmatched_action", {}) if isinstance(defaults.get("unmatched_action"), dict) else {}
        unmatched_move_to = unmatched_action.get("move_to", "misc")
        if not isinstance(unmatched_move_to, str) or not unmatched_move_to:
            unmatched_move_to = "misc"

        rules = cfg.get("rules", [])
        if not isinstance(rules, list):
            rules = []

        now = int(time.time())

        def _ext(name: str) -> str:
            lower = name.lower()
            if "." not in lower or lower.endswith("."):
                return ""
            return lower.rsplit(".", 1)[-1]

        def should_skip(name: str) -> bool:
            if not name:
                return True
            if name.startswith("."):
                return True
            for pat in (exclude + ignore_patterns):
                if fnmatch.fnmatchcase(name, pat):
                    return True
            return False

        def approx_mime_prefix(name: str) -> Optional[str]:
            e = _ext(name)
            if e in ("png", "jpg", "jpeg", "gif", "webp", "heic", "svg"):
                return "image/"
            if e in ("mp4", "mov", "mkv", "webm"):
                return "video/"
            if e in ("mp3", "wav", "flac", "m4a"):
                return "audio/"
            if e in ("pdf", "txt", "md", "rtf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "csv"):
                return "application/"
            return None

        def match_atom(atom: Dict[str, Any], entry: Dict[str, Any]) -> bool:
            name = str(entry.get("name") or "")
            if "filename_regex" in atom:
                try:
                    return re.search(str(atom["filename_regex"]), name) is not None
                except Exception:  # noqa: BLE001
                    return False
            if "ext_in" in atom:
                exts = atom.get("ext_in")
                if not isinstance(exts, list):
                    return False
                e = _ext(name)
                normalized = []
                for x in exts:
                    if not isinstance(x, str) or not x:
                        continue
                    normalized.append(x.lower().lstrip("."))
                return e in normalized
            if "mime_prefix" in atom:
                want = atom.get("mime_prefix")
                if not isinstance(want, str) or not want:
                    return False
                got = approx_mime_prefix(name)
                return bool(got and got.startswith(want))
            if "created_within_days" in atom:
                days = atom.get("created_within_days")
                if not isinstance(days, int) or days < 0:
                    return False
                mtime = entry.get("mtime")
                if not isinstance(mtime, int):
                    return False
                return (now - mtime) <= int(days) * 86400
            return False

        def match_rule(rule: Dict[str, Any], entry: Dict[str, Any]) -> bool:
            m = rule.get("match", {})
            if not isinstance(m, dict):
                return False
            any_atoms = m.get("any", [])
            all_atoms = m.get("all", [])
            if not isinstance(any_atoms, list):
                any_atoms = []
            if not isinstance(all_atoms, list):
                all_atoms = []

            any_ok = True
            if any_atoms:
                any_ok = any(match_atom(a, entry) for a in any_atoms if isinstance(a, dict))
            all_ok = True
            if all_atoms:
                all_ok = all(match_atom(a, entry) for a in all_atoms if isinstance(a, dict))
            return any_ok and all_ok

        def resolve_move_to(move_to: str) -> str:
            if move_to in folders_map and isinstance(folders_map.get(move_to), str) and folders_map.get(move_to):
                return str(folders_map[move_to])
            return move_to

        def validate_dest_subpath(dest_sub: str, *, rule_id: Optional[str], source: str) -> str:
            if not isinstance(dest_sub, str) or not dest_sub.strip():
                raise ValidationError(
                    code="config.invalid",
                    message="rule.action.move_to must resolve to a non-empty subpath under staging_dir",
                    data={"rule_id": rule_id, "source": source, "value": dest_sub},
                )
            norm = dest_sub.replace("\\", "/")
            parts = [p for p in norm.split("/") if p != ""]
            if not parts:
                raise ValidationError(
                    code="config.invalid",
                    message="rule.action.move_to must resolve to a non-empty subpath under staging_dir",
                    data={"rule_id": rule_id, "source": source, "value": dest_sub},
                )
            if norm.startswith("/") or norm.startswith("../") or "/../" in f"/{norm}/" or norm == "..":
                raise ValidationError(
                    code="config.invalid",
                    message="rule.action.move_to must not be absolute or contain '..' path traversal",
                    data={"rule_id": rule_id, "source": source, "value": dest_sub},
                )
            if any(p in (".", "..") for p in parts):
                raise ValidationError(
                    code="config.invalid",
                    message="rule.action.move_to must not contain '.' or '..' path segments",
                    data={"rule_id": rule_id, "source": source, "value": dest_sub},
                )
            return "/".join(parts)

        move_steps: List[Dict[str, Any]] = []
        created_dirs_set = set()  # type: ignore[var-annotated]

        for i, item in enumerate(entries, start=1):
            if not isinstance(item, dict):
                if isinstance(item, str):
                    item = {"name": item, "is_file": True, "is_dir": False}
                else:
                    continue

            name = item.get("name")
            if not isinstance(name, str) or not name:
                continue
            is_file = bool(item.get("is_file", False))
            is_dir = bool(item.get("is_dir", False))
            if should_skip(name):
                continue
            if is_dir and not include_dirs:
                continue
            if (not is_file) and (not is_dir):
                continue

            if is_dir:
                dest_sub = "Folders"
            else:
                dest_sub = resolve_move_to(unmatched_move_to)
                for r in rules:
                    if isinstance(r, dict) and match_rule(r, item):
                        a = r.get("action", {})
                        if isinstance(a, dict) and isinstance(a.get("move_to"), str) and a.get("move_to"):
                            dest_sub = resolve_move_to(str(a["move_to"]))
                        break

            rule_id = None
            if not is_dir:
                # Best-effort: record the id of the first matching rule (if any) for clearer errors.
                for r in rules:
                    if isinstance(r, dict) and match_rule(r, item):
                        rid = r.get("id")
                        if isinstance(rid, str) and rid:
                            rule_id = rid
                        break
            dest_sub = validate_dest_subpath(dest_sub, rule_id=rule_id, source="folders|literal")

            dest_dir = f"{staging_dir}/{dest_sub}"
            created_dirs_set.add(dest_dir)

            src = f"{root_path}/{name}"
            dst = f"{dest_dir}/{name}"

            move_step_id = f"commit_move_{i:04d}"
            move_steps.append(
                {
                    "step_id": move_step_id,
                    "title": f"Move: {name} -> {dest_sub}",
                    "phase": "commit",
                    "tool": {
                        "tool_id": "fs.move",
                        "args": {"from": src, "to": dst, "on_conflict": collision_strategy},
                        "dry_run_ok": True,
                    },
                    "expected_effects": [
                        {
                            "kind": "fs_move",
                            "summary": f"Move {name} -> {dest_sub} (on_conflict={collision_strategy})",
                            "resources": [src, dst],
                        }
                    ],
                }
            )

        created_dirs = sorted(created_dirs_set)
        return (move_steps, created_dirs)

    def _plan_restore_from_config(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        config_path = intent["params"].get("config_path")
        if not isinstance(config_path, str) or not config_path:
            raise ValidationError(code="intent.invalid", message="params.config_path is required for desktop.tidy.restore")

        cfg = self._load_rules_config(config_path)
        root_path = self._expand_user(str(cfg["root"]["path"]))
        staging_dir = self._expand_user(str(cfg["root"]["staging_dir"]))

        fs_roots = intent.get("scope", {}).get("fs_roots", [])
        if not isinstance(fs_roots, list):
            fs_roots = []
        fs_roots_expanded = [self._expand_user(x) for x in fs_roots if isinstance(x, str)]
        if root_path not in fs_roots_expanded or staging_dir not in fs_roots_expanded:
            raise ValidationError(
                code="scope.invalid",
                message="scope.fs_roots must include both config.root.path and config.root.staging_dir",
                data={"required": [root_path, staging_dir], "fs_roots": fs_roots},
            )

        safety = cfg.get("safety", {}) if isinstance(cfg.get("safety"), dict) else {}
        collision_strategy = safety.get("collision_strategy", "suffix_increment")
        if not isinstance(collision_strategy, str):
            collision_strategy = "suffix_increment"

        sorted_entries = intent.get("params", {}).get("sorted_entries")
        move_steps = self._build_restore_moves_config(
            root_path=root_path,
            staging_dir=staging_dir,
            sorted_entries=sorted_entries,
            collision_strategy=collision_strategy,
            exclude=list(intent["params"].get("exclude", [])),
        )

        return {
            "plan_id": "plan_desktop_tidy_restore_001",
            "intent": intent,
            "risk": {"level": "low", "reasons": ["Config-driven restore (no deletes)."]},
            "steps": [
                {
                    "step_id": "commit_notify_restore",
                    "title": "Notify (commit)",
                    "phase": "commit",
                    "tool": {"tool_id": "notify.send", "args": {"message": f"Desktop restore (config): root={root_path}"}, "dry_run_ok": True},
                },
                *move_steps,
            ],
        }

    def _build_restore_moves_config(
        self,
        *,
        root_path: str,
        staging_dir: str,
        sorted_entries: Any,
        collision_strategy: str,
        exclude: List[str],
    ) -> List[Dict[str, Any]]:
        if sorted_entries is None:
            return []
        if not isinstance(sorted_entries, list):
            raise ValidationError(code="intent.invalid", message="params.sorted_entries must be an array when provided")

        if collision_strategy not in ("error", "overwrite", "skip", "suffix_increment"):
            collision_strategy = "suffix_increment"

        def should_skip(rel_path: str) -> bool:
            base = rel_path.split("/")[-1] if "/" in rel_path else rel_path
            if not base:
                return True
            if base.startswith("."):
                return True
            for pat in exclude:
                if fnmatch.fnmatchcase(base, pat):
                    return True
            return False

        move_steps: List[Dict[str, Any]] = []

        file_entries = [
            e for e in sorted_entries if isinstance(e, dict) and isinstance(e.get("path"), str) and bool(e.get("is_file", False))
        ]
        file_entries.sort(key=lambda x: str(x.get("path")))

        for i, e in enumerate(file_entries, start=1):
            rel_path = str(e["path"])
            if should_skip(rel_path):
                continue

            base = rel_path.split("/")[-1] if "/" in rel_path else rel_path
            src = f"{staging_dir}/{rel_path}"
            dst = f"{root_path}/{base}"

            move_step_id = f"commit_restore_{i:04d}"
            move_steps.append(
                {
                    "step_id": move_step_id,
                    "title": f"Restore: {base}",
                    "phase": "commit",
                    "tool": {"tool_id": "fs.move", "args": {"from": src, "to": dst, "on_conflict": collision_strategy}, "dry_run_ok": True},
                    "expected_effects": [
                        {
                            "kind": "fs_move",
                            "summary": f"Restore {base} (on_conflict={collision_strategy})",
                            "resources": [src, dst],
                        }
                    ],
                }
            )

        return move_steps


def get_planner() -> Planner:
    return BuiltinDesktopPlanner()

