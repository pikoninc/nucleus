from __future__ import annotations

import datetime as dt
import re
from pathlib import Path


_PATH_RE = re.compile(
    r"""
    (?:
      (?:^|[\s`"'(])               # boundary
      (?P<p>
        (?:[A-Za-z]:\\)?          # windows drive (optional)
        (?:\.{0,2}[\\/])?         # ./, ../ (optional)
        (?:[A-Za-z0-9._-]+[\\/])+ # dirs
        [A-Za-z0-9._-]+\.[A-Za-z0-9]{1,10}  # file.ext
      )
      (?:$|[\s`"')])              # boundary
    )
    """,
    re.VERBOSE,
)

_CMD_RE = re.compile(r"^\s*(?:\$|>)\s*(?P<cmd>.+?)\s*$")


def extract_paths(text: str) -> list[str]:
    paths: set[str] = set()
    for m in _PATH_RE.finditer(text):
        p = (m.group("p") or "").strip()
        if not p:
            continue
        p = p.strip("`'\"()[]{}.,")
        if p:
            paths.add(p)
    return sorted(paths)


def extract_commands(lines: list[str], *, limit: int = 40) -> list[str]:
    out: list[str] = []
    for line in lines:
        m = _CMD_RE.match(line)
        if not m:
            continue
        cmd = (m.group("cmd") or "").strip()
        if not cmd:
            continue
        out.append(cmd)
        if len(out) >= limit:
            break
    return out


def build_stub(*, transcript_path: Path, repo_root: Path | None = None, date: str | None = None) -> str:
    raw = transcript_path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    if not date:
        date = dt.date.today().isoformat()

    paths = extract_paths(raw)
    cmds = extract_commands(lines)

    display_path: Path = transcript_path
    if repo_root is not None:
        try:
            display_path = transcript_path.resolve().relative_to(repo_root.resolve())
        except Exception:
            display_path = transcript_path

    parts: list[str] = []
    parts.append(f"- **{date}**: TODO (summary title)")
    parts.append(f"  - Transcript: `{display_path}`")
    if paths:
        parts.append("  - Related files:")
        for p in paths[:50]:
            parts.append(f"    - `{p}`")
        if len(paths) > 50:
            parts.append(f"    - ({len(paths) - 50} more)")
    if cmds:
        parts.append("  - Commands (excerpt):")
        for c in cmds:
            parts.append(f"    - `{c}`")
    parts.append("  - Decision: TODO")
    parts.append("  - Why: TODO")
    parts.append("  - Next: TODO")
    parts.append("")
    return "\n".join(parts)

