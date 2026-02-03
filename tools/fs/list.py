from __future__ import annotations

from typing import Any

from ._path import expand_user_path


def run(args: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """
    List directory entries (read-only; dry-run identical).
    args:
      - path: string
    """
    path_raw = args.get("path")
    if not isinstance(path_raw, str) or not path_raw:
        raise ValueError("fs.list: 'path' must be a non-empty string")

    path = expand_user_path(path_raw)
    if not path.exists():
        return {"path": str(path), "entries": [], "exists": False}
    if not path.is_dir():
        raise ValueError("fs.list: path is not a directory")

    entries = sorted([p.name for p in path.iterdir()])
    return {"path": str(path), "entries": entries, "exists": True, "dry_run": dry_run}

