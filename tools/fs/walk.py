from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ._path import expand_user_path


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:  # noqa: BLE001
        return str(path)


def run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """
    Recursively list entries under a directory.
    args:
      - path: string (directory root)
      - max_depth: int (optional; default 20; 0 means only root)
      - include_dirs: bool (optional; default false)
    output:
      - entries: [{"path": "relative/path", "is_file": bool, "is_dir": bool}, ...]
    """
    path_raw = args.get("path")
    if not isinstance(path_raw, str) or not path_raw:
        raise ValueError("fs.walk: 'path' must be a non-empty string")

    max_depth = args.get("max_depth", 20)
    if max_depth is None:
        max_depth = 20
    if not isinstance(max_depth, int) or max_depth < 0:
        raise ValueError("fs.walk: 'max_depth' must be a non-negative integer")

    include_dirs = bool(args.get("include_dirs", False))

    root = expand_user_path(path_raw)
    if not root.exists():
        return {"path": str(root), "entries": [], "exists": False, "dry_run": dry_run}
    if not root.is_dir():
        raise ValueError("fs.walk: path is not a directory")

    entries: List[Dict[str, Any]] = []

    # Deterministic DFS with sorted children.
    stack: List[tuple[Path, int]] = [(root, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            continue

        try:
            children = sorted(list(cur.iterdir()), key=lambda p: p.name)
        except Exception:  # noqa: BLE001
            continue

        # Push dirs in reverse order to preserve deterministic order in DFS.
        dirs_to_visit: List[Path] = []
        for ch in children:
            is_dir = ch.is_dir()
            is_file = ch.is_file()
            if is_dir and include_dirs:
                entries.append({"path": _rel(ch, root), "is_file": False, "is_dir": True})
            if is_file:
                entries.append({"path": _rel(ch, root), "is_file": True, "is_dir": False})
            if is_dir:
                dirs_to_visit.append(ch)

        for d in reversed(dirs_to_visit):
            stack.append((d, depth + 1))

    return {"path": str(root), "entries": entries, "exists": True, "dry_run": dry_run}

