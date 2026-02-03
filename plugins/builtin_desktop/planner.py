from __future__ import annotations

import fnmatch
from typing import Any, Dict, List

from nucleus.core.errors import ValidationError
from nucleus.core.planner import Planner


def _require_str(d: Dict[str, Any], key: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v:
        raise ValidationError(code="intent.invalid", message=f"Missing or invalid '{key}'")
    return v


class BuiltinDesktopPlanner(Planner):
    """
    Reference plugin implementation for `builtin.desktop`.
    Lives under top-level `plugins/` (plugins are apps; nucleus is the framework runtime).
    """

    def plan(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(intent, dict):
            raise ValidationError(code="intent.invalid", message="Intent must be an object")

        intent_id = _require_str(intent, "intent_id")
        params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
        scope = intent.get("scope") if isinstance(intent.get("scope"), dict) else {}
        context = intent.get("context") if isinstance(intent.get("context"), dict) else {}

        target_dir = params.get("target_dir")
        if target_dir is None:
            target_dir = "~/Desktop"
        if not isinstance(target_dir, str) or not target_dir:
            raise ValidationError(code="intent.invalid", message="params.target_dir must be a non-empty string")

        fs_roots = scope.get("fs_roots")
        if fs_roots is None:
            fs_roots = [target_dir]
        if not isinstance(fs_roots, list) or len(fs_roots) < 1:
            raise ValidationError(code="scope.missing", message="scope.fs_roots must be a non-empty array")
        if target_dir not in fs_roots:
            raise ValidationError(code="scope.invalid", message="scope.fs_roots must include params.target_dir")

        allow_network = scope.get("allow_network", False)
        if not isinstance(allow_network, bool):
            allow_network = False

        entries = params.get("entries")
        include_dirs = bool(params.get("include_dirs", False))
        exclude = params.get("exclude", [])
        if exclude is None:
            exclude = []
        if not isinstance(exclude, list) or any((not isinstance(x, str)) for x in exclude):
            raise ValidationError(code="intent.invalid", message="params.exclude must be an array of strings when provided")
        overwrite_strategy = params.get("overwrite_strategy", "error")
        if overwrite_strategy not in ("error", "overwrite", "skip"):
            raise ValidationError(code="intent.invalid", message="params.overwrite_strategy must be one of: error|overwrite|skip")

        intent_obj = {
            "intent_id": intent_id,
            "params": {
                "target_dir": target_dir,
                "include_dirs": include_dirs,
                "exclude": exclude,
                "overwrite_strategy": overwrite_strategy,
                "entries": entries,
            },
            "scope": {"fs_roots": fs_roots, "allow_network": allow_network},
            "context": context or {},
        }

        if intent_id == "desktop.tidy":
            return self._plan_tidy(intent_obj)
        if intent_id == "desktop.restore":
            return self._plan_restore(intent_obj)
        raise ValidationError(code="intent.unknown", message=f"Unsupported intent_id: {intent_id}")

    def _plan_tidy(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        target_dir = intent["params"]["target_dir"]
        sorted_dir = f"{target_dir}/_Sorted"

        steps: List[Dict[str, Any]] = [
            {
                "step_id": "staging_list_target",
                "title": "List target directory (staging)",
                "phase": "staging",
                "tool": {"tool_id": "fs.list", "args": {"path": target_dir}, "dry_run_ok": True},
                "preconditions": [f"Scope includes {target_dir}"],
            },
            {
                "step_id": "commit_create_sorted_dir",
                "title": "Create _Sorted folder (commit)",
                "phase": "commit",
                "tool": {
                    "tool_id": "fs.mkdir",
                    "args": {"path": sorted_dir, "parents": True, "exist_ok": True},
                    "dry_run_ok": True,
                },
                "expected_effects": [
                    {"kind": "fs_mkdir", "summary": f"Create {sorted_dir} if missing", "resources": [sorted_dir]}
                ],
            },
        ]

        entries = intent.get("params", {}).get("entries")
        move_steps, rollback_steps, created_dirs = self._build_moves_from_entries(
            target_dir,
            sorted_dir,
            entries,
            include_dirs=bool(intent["params"].get("include_dirs", False)),
            exclude=list(intent["params"].get("exclude", [])),
            overwrite_strategy=str(intent["params"].get("overwrite_strategy", "error")),
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
        steps.extend(rollback_steps)

        summary = f"Desktop tidy: prepared {sorted_dir}"
        if move_steps:
            summary = f"Desktop tidy: {len(move_steps)} move step(s) planned into {sorted_dir}"

        steps.append(
            {
                "step_id": "commit_notify",
                "title": "Notify summary (commit)",
                "phase": "commit",
                "tool": {"tool_id": "notify.send", "args": {"message": summary}, "dry_run_ok": True},
            }
        )

        return {
            "plan_id": "plan_desktop_tidy_001",
            "intent": intent,
            "risk": {"level": "low", "reasons": ["Creates a staging folder; no deletes; move steps are plugin-defined."]},
            "steps": steps,
        }

    def _build_moves_from_entries(
        self,
        target_dir: str,
        sorted_dir: str,
        entries: Any,
        *,
        include_dirs: bool,
        exclude: List[str],
        overwrite_strategy: str,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        if entries is None:
            return ([], [], [])
        if not isinstance(entries, list):
            raise ValidationError(code="intent.invalid", message="params.entries must be an array when provided")

        def should_skip(name: str) -> bool:
            if name in ("_Sorted",):
                return True
            if name in (".DS_Store",):
                return True
            if name.startswith("."):
                return True
            for pat in exclude:
                if fnmatch.fnmatchcase(name, pat):
                    return True
            return False

        def category_for(name: str) -> str:
            lower = name.lower()
            exts = [
                ("Images", [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".heic"]),
                ("Archives", [".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz"]),
                (
                    "Documents",
                    [".pdf", ".txt", ".md", ".rtf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv"],
                ),
            ]
            for cat, suffixes in exts:
                for s in suffixes:
                    if lower.endswith(s):
                        return cat
            return "Other"

        move_steps: List[Dict[str, Any]] = []
        rollback_steps: List[Dict[str, Any]] = []
        created_dirs_set = set()  # type: ignore[var-annotated]

        for i, item in enumerate(entries, start=1):
            if isinstance(item, str):
                name = item
                is_file = True
                is_dir = False
            elif isinstance(item, dict):
                name = item.get("name")
                is_file = bool(item.get("is_file", False))
                is_dir = bool(item.get("is_dir", False))
            else:
                continue

            if not isinstance(name, str) or not name:
                continue
            if should_skip(name):
                continue
            is_dir = bool(is_dir)
            is_file = bool(is_file)
            if is_dir and not include_dirs:
                continue
            if (not is_file) and (not is_dir):
                continue

            if is_dir:
                cat = "Folders"
                dest_dir = f"{sorted_dir}/{cat}"
            else:
                cat = category_for(name)
                dest_dir = f"{sorted_dir}/{cat}"
            created_dirs_set.add(dest_dir)

            src = f"{target_dir}/{name}"
            dst = f"{dest_dir}/{name}"

            move_step_id = f"commit_move_{i:04d}"
            move_args: Dict[str, Any] = {"from": src, "to": dst, "on_conflict": overwrite_strategy}
            move_steps.append(
                {
                    "step_id": move_step_id,
                    "title": f"Move into {cat}: {name}",
                    "phase": "commit",
                    "tool": {"tool_id": "fs.move", "args": move_args, "dry_run_ok": True},
                    "expected_effects": [
                        {"kind": "fs_move", "summary": f"Move {name} -> {cat} (on_conflict={overwrite_strategy})", "resources": [src, dst]}
                    ],
                }
            )
            rollback_steps.append(
                {
                    "step_id": f"rollback_move_{i:04d}",
                    "title": f"Rollback move: {name}",
                    "phase": "rollback",
                    "tool": {"tool_id": "fs.move", "args": {"from": dst, "to": src, "on_conflict": "error"}, "dry_run_ok": True},
                    "compensates_step_id": move_step_id,
                }
            )

        created_dirs = sorted(created_dirs_set)
        return (move_steps, rollback_steps, created_dirs)

    def _plan_restore(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        target_dir = intent["params"]["target_dir"]
        return {
            "plan_id": "plan_desktop_restore_001",
            "intent": intent,
            "risk": {"level": "low", "reasons": ["Restore behavior is plugin-defined (no deletes)."]},
            "steps": [
                {
                    "step_id": "commit_notify_restore",
                    "title": "Notify (commit)",
                    "phase": "commit",
                    "tool": {"tool_id": "notify.send", "args": {"message": f"Desktop restore: target={target_dir}"}, "dry_run_ok": True},
                }
            ],
        }


def get_planner() -> Planner:
    return BuiltinDesktopPlanner()

