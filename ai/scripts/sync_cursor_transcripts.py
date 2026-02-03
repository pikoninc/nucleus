from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _repo_root() -> Path:
    # ai/scripts/sync_cursor_transcripts.py -> repo root
    return Path(__file__).resolve().parents[2]


def _detect_cursor_project_dir(cursor_projects_dir: Path, repo_root: Path) -> Path | None:
    """
    Try to find the Cursor project directory that corresponds to this repo by:
    - scanning ~/.cursor/projects/*/terminals/*.txt for the repo root path
    - falling back to "newest agent-transcripts" directory
    """
    repo_root_s = str(repo_root)
    candidates: list[Path] = []
    for d in sorted(cursor_projects_dir.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "agent-transcripts").exists():
            continue
        candidates.append(d)

    # Primary: terminals mention repo path
    for d in candidates:
        terminals_dir = d / "terminals"
        if not terminals_dir.exists():
            continue
        for t in sorted(terminals_dir.glob("*.txt")):
            try:
                txt = t.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if repo_root_s in txt:
                return d

    # Fallback: newest transcript file
    newest: tuple[float, Path] | None = None
    for d in candidates:
        transcripts_dir = d / "agent-transcripts"
        for p in transcripts_dir.glob("*.txt"):
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if newest is None or mtime > newest[0]:
                newest = (mtime, d)
    return newest[1] if newest else None


def _copy_if_changed(src: Path, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            if src.read_bytes() == dst.read_bytes():
                return False
        except OSError:
            pass
    shutil.copy2(src, dst)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Cursor agent transcripts into ai/.sessions/ (ignored by git).")
    parser.add_argument("--cursor-project", help="Cursor project directory name under ~/.cursor/projects/ (optional).")
    args = parser.parse_args()

    repo_root = _repo_root()
    cursor_projects_dir = Path.home() / ".cursor" / "projects"
    if not cursor_projects_dir.exists():
        raise SystemExit("Cursor projects dir not found: ~/.cursor/projects")

    project_dir: Path | None
    if args.cursor_project:
        project_dir = cursor_projects_dir / args.cursor_project
        if not project_dir.exists():
            raise SystemExit(f"Cursor project not found: {project_dir}")
    else:
        project_dir = _detect_cursor_project_dir(cursor_projects_dir, repo_root)

    if project_dir is None:
        raise SystemExit("Could not detect Cursor project directory for this repo.")

    src_dir = project_dir / "agent-transcripts"
    if not src_dir.exists():
        raise SystemExit(f"agent-transcripts not found: {src_dir}")

    dst_dir = repo_root / "ai" / ".sessions" / "agent-transcripts"
    dst_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    total = 0
    for p in sorted(src_dir.glob("*.txt")):
        total += 1
        if _copy_if_changed(p, dst_dir / p.name):
            copied += 1

    print(f"Synced Cursor transcripts: {copied}/{total} updated -> {dst_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

