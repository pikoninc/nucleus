from __future__ import annotations

from typing import Any, Dict, List, Optional

from nucleus.core.errors import ValidationError
from nucleus.core.planner import Planner


def _require_str(d: Dict[str, Any], key: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v:
        raise ValidationError(code="intent.invalid", message=f"Missing or invalid '{key}'")
    return v


class BuiltinDesktopPlanner(Planner):
    """
    Minimal builtin planner for the reference plugin `builtin.desktop`.

    Current behavior is intentionally small: it produces a valid Plan that is safe by default
    and easy to extend during `desktop.tidy` development.
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
            # Avoid silently expanding scope.
            raise ValidationError(code="scope.invalid", message="scope.fs_roots must include params.target_dir")

        allow_network = scope.get("allow_network", False)
        if not isinstance(allow_network, bool):
            allow_network = False

        intent_obj = {
            "intent_id": intent_id,
            "params": {"target_dir": target_dir},
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
            {
                "step_id": "commit_notify",
                "title": "Notify summary (commit)",
                "phase": "commit",
                "tool": {"tool_id": "notify.send", "args": {"message": f"Desktop tidy: prepared {sorted_dir}"}, "dry_run_ok": True},
            },
        ]

        return {
            "plan_id": "plan_desktop_tidy_001",
            "intent": intent,
            "risk": {"level": "low", "reasons": ["Creates a staging folder; no deletes; move steps are plugin-defined."]},
            "steps": steps,
        }

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

