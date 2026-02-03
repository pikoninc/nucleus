from __future__ import annotations

from typing import Any, Dict

from ._path import expand_user_path


def _with_suffix_increment(dst, *, max_tries: int = 10_000):
    """
    Return a non-existing path by appending (n) before the suffix.
    Examples:
      - file.txt -> file(1).txt
      - file     -> file(1)
    """
    base = dst.name
    stem = dst.stem
    suffix = dst.suffix  # includes leading dot or ""
    parent = dst.parent

    # If name like ".bashrc" (stem == ".bashrc", suffix == ""), still ok.
    for i in range(1, max_tries + 1):
        cand_name = f"{stem}({i}){suffix}"
        cand = parent / cand_name
        if not cand.exists():
            return cand
    raise FileExistsError("fs.move: suffix_increment exhausted")


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
    if on_conflict not in ("error", "overwrite", "skip", "suffix_increment"):
        raise ValueError("fs.move: 'on_conflict' must be one of: error|overwrite|skip|suffix_increment")
    src = expand_user_path(src_raw)
    dst = expand_user_path(dst_raw)

    # Resolve destination under suffix_increment deterministically by filesystem existence.
    # This is safe because the tool is deterministic within the declared environment constraints.
    resolved_dst = dst
    if dst.exists() and on_conflict == "suffix_increment":
        resolved_dst = _with_suffix_increment(dst)

    if dry_run:
        src_exists = src.exists()
        dst_exists = dst.exists()
        resolved_dst_exists = resolved_dst.exists()
        would_skip = bool(dst_exists and on_conflict == "skip")
        would_error = bool(dst_exists and on_conflict == "error")
        would_overwrite = bool(dst_exists and on_conflict == "overwrite")
        would_suffix_increment = bool(dst_exists and on_conflict == "suffix_increment")
        would_move = bool((not would_skip) and (not would_error))
        return {
            "from": str(src),
            "to": str(resolved_dst),
            "dry_run": True,
            "src_exists": src_exists,
            "dst_exists": dst_exists,
            "on_conflict": on_conflict,
            "resolved_to": str(resolved_dst),
            "resolved_dst_exists": resolved_dst_exists,
            "would_move": would_move,
            "would_skip": would_skip,
            "would_error": would_error,
            "would_overwrite": would_overwrite,
            "would_suffix_increment": would_suffix_increment,
            "expected_effects": [
                {
                    "kind": "fs_move",
                    "summary": f"Move {src} -> {resolved_dst} (on_conflict={on_conflict})",
                    "resources": [str(src), str(resolved_dst)],
                }
            ],
        }

    if not src.exists():
        raise FileNotFoundError(f"fs.move: source not found: {src}")

    # Re-resolve in commit path too (TOCTOU is acceptable; deterministic best-effort).
    resolved_dst = dst
    if dst.exists() and on_conflict == "suffix_increment":
        resolved_dst = _with_suffix_increment(dst)

    if dst.exists():
        if on_conflict == "skip":
            return {"from": str(src), "to": str(dst), "dry_run": False, "skipped": True, "reason": "dst_exists"}
        if on_conflict == "error":
            raise FileExistsError(f"fs.move: destination exists (on_conflict=error): {dst}")
        # on_conflict == overwrite|suffix_increment: proceed

    resolved_dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(resolved_dst)
    return {"from": str(src), "to": str(resolved_dst), "dry_run": False, "skipped": False}

