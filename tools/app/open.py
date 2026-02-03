from __future__ import annotations

from typing import Any


def run(args: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """
    Open an application or file.

    Framework note:
    - Real app control is environment-specific.
    - This tool is provided primarily as an I/O contract and is dry-run compatible.
    """
    target = args.get("target")
    if not isinstance(target, str) or not target:
        raise ValueError("app.open: 'target' must be a non-empty string")

    if dry_run:
        return {
            "dry_run": True,
            "expected_effects": [{"kind": "app", "summary": f"Open: {target}", "resources": [target]}],
        }

    raise NotImplementedError("app.open is not implemented in the framework sandbox")

