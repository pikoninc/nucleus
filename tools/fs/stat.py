from __future__ import annotations

from typing import Any, Dict

from ._path import expand_user_path


def run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """
    Stat a file or directory (read-only; dry-run identical).
    args:
      - path: string
    """
    path_raw = args.get("path")
    if not isinstance(path_raw, str) or not path_raw:
        raise ValueError("fs.stat: 'path' must be a non-empty string")

    path = expand_user_path(path_raw)
    st = path.stat()
    return {
        "path": str(path),
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
        "size": st.st_size,
        "mtime": int(st.st_mtime),
        "dry_run": dry_run,
    }

