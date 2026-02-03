from __future__ import annotations

from typing import Any

from ._path import expand_user_path


def run(args: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """
    Move/rename a file or directory (non-delete; may overwrite only if explicitly allowed).
    args:
      - from: string
      - to: string
      - overwrite: bool (default false)
    """
    src_raw = args.get("from")
    dst_raw = args.get("to")
    if not isinstance(src_raw, str) or not src_raw:
        raise ValueError("fs.move: 'from' must be a non-empty string")
    if not isinstance(dst_raw, str) or not dst_raw:
        raise ValueError("fs.move: 'to' must be a non-empty string")

    overwrite = bool(args.get("overwrite", False))
    src = expand_user_path(src_raw)
    dst = expand_user_path(dst_raw)

    if not src.exists():
        raise FileNotFoundError(f"fs.move: source not found: {src}")

    if dst.exists() and not overwrite:
        raise FileExistsError(f"fs.move: destination exists (overwrite=false): {dst}")

    if dry_run:
        return {
            "from": str(src),
            "to": str(dst),
            "dry_run": True,
            "expected_effects": [
                {"kind": "fs_move", "summary": f"Move {src} -> {dst}", "resources": [str(src), str(dst)]}
            ],
        }

    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return {"from": str(src), "to": str(dst), "dry_run": False}

