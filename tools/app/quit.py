from __future__ import annotations

from typing import Any, Dict


def run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """
    Quit an application.

    Framework note:
    - Real app control is environment-specific.
    - This tool is provided primarily as an I/O contract and is dry-run compatible.
    """
    app_id = args.get("app_id")
    if not isinstance(app_id, str) or not app_id:
        raise ValueError("app.quit: 'app_id' must be a non-empty string")

    if dry_run:
        return {
            "dry_run": True,
            "expected_effects": [{"kind": "app", "summary": f"Quit: {app_id}", "resources": [app_id]}],
        }

    raise NotImplementedError("app.quit is not implemented in the framework sandbox")

