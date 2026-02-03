from __future__ import annotations

from typing import Any, Dict

from ._path import expand_user_path


def run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """
    Move/rename a file or directory (non-delete; may overwrite only if explicitly allowed).
    args:
      - from: string
      - to: string
      - on_conflict: "error" | "overwrite" | "skip" (default "error")
      - overwrite: bool (legacy; if true, treated as on_conflict="overwrite")
    """
    src_raw = args.get("from")
    dst_raw = args.get("to")
    if not isinstance(src_raw, str) or not src_raw:
        raise ValueError("fs.move: 'from' must be a non-empty string")
    if not isinstance(dst_raw, str) or not dst_raw:
        raise ValueError("fs.move: 'to' must be a non-empty string")

    on_conflict = args.get("on_conflict", "error")
    if isinstance(args.get("overwrite", False), bool) and args.get("overwrite", False):
        on_conflict = "overwrite"
    if on_conflict not in ("error", "overwrite", "skip"):
        raise ValueError("fs.move: 'on_conflict' must be one of: error|overwrite|skip")
    src = expand_user_path(src_raw)
    dst = expand_user_path(dst_raw)

    if dry_run:
        src_exists = src.exists()
        dst_exists = dst.exists()
        would_skip = bool(dst_exists and on_conflict == "skip")
        would_error = bool(dst_exists and on_conflict == "error")
        would_overwrite = bool(dst_exists and on_conflict == "overwrite")
        would_move = bool((not would_skip) and (not would_error))
        return {
            "from": str(src),
            "to": str(dst),
            "dry_run": True,
            "src_exists": src_exists,
            "dst_exists": dst_exists,
            "on_conflict": on_conflict,
            "would_move": would_move,
            "would_skip": would_skip,
            "would_error": would_error,
            "would_overwrite": would_overwrite,
            "expected_effects": [
                {"kind": "fs_move", "summary": f"Move {src} -> {dst} (on_conflict={on_conflict})", "resources": [str(src), str(dst)]}
            ],
        }

    if not src.exists():
        raise FileNotFoundError(f"fs.move: source not found: {src}")

    if dst.exists():
        if on_conflict == "skip":
            return {"from": str(src), "to": str(dst), "dry_run": False, "skipped": True, "reason": "dst_exists"}
        if on_conflict == "error":
            raise FileExistsError(f"fs.move: destination exists (on_conflict=error): {dst}")
        # on_conflict == "overwrite": proceed

    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return {"from": str(src), "to": str(dst), "dry_run": False, "skipped": False}

