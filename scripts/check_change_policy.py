from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


TARGET_PREFIXES_DEFAULT = (
    "nucleus/",
    "tools/",
    "contracts/core/",
    "scripts/",
)

TESTS_PREFIX = "tests/"

# If *all* changes are within these prefixes/files, the guard is skipped.
DOC_ONLY_PREFIXES = (
    "specs/",
    "work/",
    ".github/",
)
DOC_ONLY_FILES = (
    "README.md",
)


PR_OVERRIDE_TAG = re.compile(r"(?im)^\s*Test-Impact\s*:\s*none\s*$")
PR_OVERRIDE_REASON = re.compile(r"(?im)^\s*Test-Impact-Reason\s*:\s*\S.+$")

WORK_TASK_OVERRIDE_TAG = re.compile(r"(?im)^\s*TestImpact\s*:\s*none\s*$")
WORK_TASK_OVERRIDE_REASON = re.compile(r"(?im)^\s*TestImpactReason\s*:\s*\S.+$")


@dataclass(frozen=True)
class ChangePolicyResult:
    exit_code: int
    message: str


def _is_docs_only(changed_files: Iterable[str]) -> bool:
    files = [f for f in changed_files if f and f.strip()]
    if not files:
        return True
    for f in files:
        if f in DOC_ONLY_FILES:
            continue
        if any(f.startswith(p) for p in DOC_ONLY_PREFIXES):
            continue
        return False
    return True


def _has_target_changes(changed_files: Iterable[str], target_prefixes: Iterable[str]) -> bool:
    return any(any(f.startswith(p) for p in target_prefixes) for f in changed_files)


def _has_tests_changes(changed_files: Iterable[str]) -> bool:
    return any(f.startswith(TESTS_PREFIX) for f in changed_files)


def _has_pr_override(pr_body: str | None) -> tuple[bool, str]:
    if not pr_body:
        return False, ""
    if not PR_OVERRIDE_TAG.search(pr_body):
        return False, ""
    if not PR_OVERRIDE_REASON.search(pr_body):
        return False, "`Test-Impact: none` in the PR body requires `Test-Impact-Reason:`."
    return True, ""


def _has_work_task_override(work_tasks_files: dict[str, str]) -> tuple[bool, str]:
    if not work_tasks_files:
        return False, ""
    for _path, content in work_tasks_files.items():
        if not content:
            continue
        if not WORK_TASK_OVERRIDE_TAG.search(content):
            continue
        if not WORK_TASK_OVERRIDE_REASON.search(content):
            return False, "`TestImpact: none` requires `TestImpactReason:` (work task)."
        return True, ""
    return False, ""


def evaluate_change_policy(
    *,
    changed_files: list[str],
    pr_body: str | None = None,
    work_tasks_files: dict[str, str] | None = None,
    target_prefixes: tuple[str, ...] = TARGET_PREFIXES_DEFAULT,
) -> tuple[int, str]:
    """
    Returns (exit_code, message).

    Policy:
    - If changes are docs-only -> pass.
    - If no target code changes -> pass.
    - If target code changes and tests changed -> pass.
    - Else require explicit override:
        - PR body includes Test-Impact: none + Test-Impact-Reason, OR
        - A changed work/tasks file includes TestImpact: none + TestImpactReason.
    """
    work_tasks_files = work_tasks_files or {}

    if _is_docs_only(changed_files):
        return 0, "Docs-only change: guard skipped."

    if not _has_target_changes(changed_files, target_prefixes):
        return 0, "No guarded code changes detected."

    if _has_tests_changes(changed_files):
        return 0, "Tests changed alongside code: OK."

    pr_ok, pr_err = _has_pr_override(pr_body)
    if pr_ok:
        return 0, "Override accepted via PR body (Test-Impact: none)."
    if pr_err:
        return 1, pr_err

    work_ok, work_err = _has_work_task_override(work_tasks_files)
    if work_ok:
        return 0, "Override accepted via work/tasks (TestImpact: none)."
    if work_err:
        return 1, work_err

    msg = (
        "Guarded code changed but no tests changed.\n"
        "- Add/update tests under `tests/**`, OR\n"
        "- Add PR body override:\n"
        "  Test-Impact: none\n"
        "  Test-Impact-Reason: <why IO is unchanged>\n"
        "- Or update a `work/tasks/*.md` (in this PR) with:\n"
        "  TestImpact: none\n"
        "  TestImpactReason: <why IO is unchanged>\n"
    )
    return 1, msg


def _run_git_diff_name_only(base: str, head: str) -> list[str]:
    cp = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if cp.returncode != 0:
        raise RuntimeError("git diff failed: {}".format(cp.stderr.strip() or cp.stdout.strip()))
    return [l.strip() for l in cp.stdout.splitlines() if l.strip()]


def _read_pr_body_from_event(event_path: Path) -> str | None:
    if not event_path.exists():
        return None
    try:
        data = json.loads(event_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    pr = data.get("pull_request") or {}
    body = pr.get("body")
    return body if isinstance(body, str) else None


def _read_changed_work_tasks_files(changed_files: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in changed_files:
        if not f.startswith("work/tasks/"):
            continue
        p = ROOT / f
        if not p.exists():
            continue
        out[f] = p.read_text(encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CI guard: require tests or explicit Test-Impact override.")
    ap.add_argument("--base", default=os.environ.get("GITHUB_BASE_SHA") or "origin/main", help="Base ref/SHA")
    ap.add_argument("--head", default=os.environ.get("GITHUB_SHA") or "HEAD", help="Head ref/SHA")
    ap.add_argument(
        "--target-prefix",
        action="append",
        default=list(TARGET_PREFIXES_DEFAULT),
        help="Guarded path prefix (repeatable).",
    )
    ap.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"), help="GitHub event JSON path")
    ns = ap.parse_args(argv)

    changed_files = _run_git_diff_name_only(ns.base, ns.head)
    pr_body = _read_pr_body_from_event(Path(ns.event_path)) if ns.event_path else None
    work_tasks_files = _read_changed_work_tasks_files(changed_files)

    rc, msg = evaluate_change_policy(
        changed_files=changed_files,
        pr_body=pr_body,
        work_tasks_files=work_tasks_files,
        target_prefixes=tuple(ns.target_prefix),
    )
    stream = sys.stdout if rc == 0 else sys.stderr
    stream.write(msg.rstrip() + "\n")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())

