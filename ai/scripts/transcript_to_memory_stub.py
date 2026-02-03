from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path


def _repo_root() -> Path:
    # ai/scripts/transcript_to_memory_stub.py -> repo root
    return Path(__file__).resolve().parents[2]


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


def _extract_paths(text: str) -> list[str]:
    paths: set[str] = set()
    for m in _PATH_RE.finditer(text):
        p = m.group("p")
        if not p:
            continue
        # normalize trivial markdown punctuation
        p = p.strip("`'\"()[]{}.,")
        if not p:
            continue
        paths.add(p)
    return sorted(paths)


def _extract_commands(lines: list[str], *, limit: int = 40) -> list[str]:
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


def build_stub(*, transcript_path: Path, date: str | None) -> str:
    raw = transcript_path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    if not date:
        date = dt.date.today().isoformat()

    paths = _extract_paths(raw)
    cmds = _extract_commands(lines)

    rel = None
    try:
        rel = transcript_path.resolve().relative_to(_repo_root())
    except Exception:
        rel = transcript_path

    parts: list[str] = []
    parts.append(f"- **{date}**: TODO (summary title)")
    parts.append(f"  - Transcript: `{rel}`")
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


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate a stub entry for ai/memory.md from a session transcript (no AI summarization)."
    )
    ap.add_argument("--transcript", required=True, help="Path to transcript txt (usually under ai/.sessions/...)")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--append", action="store_true", help="Append to ai/memory.md instead of printing to stdout")
    ap.add_argument("--memory", default=str(_repo_root() / "ai" / "memory.md"), help="Path to ai/memory.md")
    args = ap.parse_args()

    t = Path(args.transcript)
    if not t.exists():
        raise SystemExit(f"Transcript not found: {t}")

    stub = build_stub(transcript_path=t, date=args.date)

    if args.append:
        mem = Path(args.memory)
        if not mem.exists():
            raise SystemExit(f"Memory file not found: {mem}")
        txt = mem.read_text(encoding="utf-8", errors="replace")
        marker = "## Key decisions (changelog)"
        idx = txt.find(marker)
        if idx < 0:
            raise SystemExit("Could not find section marker in memory.md: '## Key decisions (changelog)'")

        # Insert after the section header block (a simple heuristic: after first blank line following marker).
        after = txt.find("\n\n", idx)
        if after < 0:
            after = idx + len(marker)
        insert_at = after + 2

        new_txt = txt[:insert_at] + stub + txt[insert_at:]
        mem.write_text(new_txt, encoding="utf-8")
        print(f"Appended stub to: {mem}")
        return 0

    print(stub, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

