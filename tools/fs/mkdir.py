from __future__ import annotations

from typing import Any

from ._path import expand_user_path


def run(args: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """
    Create a directory (non-destructive; no delete).
    args:
      - path: string
      - parents: bool (default true)
      - exist_ok: bool (default true)
    """
    path_raw = args.get("path")
    if not isinstance(path_raw, str) or not path_raw:
        raise ValueError("fs.mkdir: 'path' must be a non-empty string")

    parents = bool(args.get("parents", True))
    exist_ok = bool(args.get("exist_ok", True))
    path = expand_user_path(path_raw)

    if dry_run:
        return {
            "path": str(path),
            "would_create": not path.exists(),
            "dry_run": True,
            "expected_effects": [
                {"kind": "fs_mkdir", "summary": f"Create directory {path}", "resources": [str(path)]}
            ],
        }

    before = path.exists()
    path.mkdir(parents=parents, exist_ok=exist_ok)
    after = path.exists()
    return {"path": str(path), "created": (not before) and after, "dry_run": False}

