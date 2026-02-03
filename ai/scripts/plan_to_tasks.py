from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
TASKS_DIR = AI_DIR / "tasks"


def _next_task_id() -> str:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    nums: list[int] = []
    for p in sorted(TASKS_DIR.glob("TASK-*.yml")):
        stem = p.stem  # TASK-0001
        parts = stem.split("-")
        if len(parts) == 2 and parts[0] == "TASK":
            try:
                nums.append(int(parts[1]))
            except ValueError:
                continue
    n = (max(nums) + 1) if nums else 1
    return f"TASK-{n:04d}"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def task_skeleton(*, plan_id: str, title: str, priority: str) -> dict[str, Any]:
    return {
        "version": 1,
        "id": _next_task_id(),
        "plan_id": plan_id,
        "title": title,
        "status": "todo",
        "priority": priority,
        "description": "",
        "acceptance_criteria": [],
        "scope": {},
        "notes": [],
    }


def upsert_index(entries: list[dict[str, Any]]) -> None:
    index_path = TASKS_DIR / "index.yml"
    index: dict[str, Any] = {"version": 1, "tasks": []}
    if index_path.exists():
        index = load_yaml(index_path)
        if not isinstance(index.get("tasks"), list):
            index["tasks"] = []

    existing_ids = {t.get("id") for t in index["tasks"] if isinstance(t, dict)}
    for e in entries:
        if e["id"] in existing_ids:
            continue
        index["tasks"].append(
            {
                "id": e["id"],
                "plan_id": e["plan_id"],
                "title": e["title"],
                "status": e["status"],
            }
        )

    index_path.write_text(yaml.safe_dump(index, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Create TASK skeletons for a plan and update ai/tasks/index.yml.")
    ap.add_argument("--plan", required=True, help="path to ai/plans/PLAN-xxxx-*.yml")
    ap.add_argument("--title", action="append", default=[], help="task title (repeatable)")
    ap.add_argument("--priority", default="P2", help="P0..P3 (default: P2)")
    args = ap.parse_args()

    plan_path = (ROOT / args.plan).resolve() if not args.plan.startswith("/") else Path(args.plan)
    plan = load_yaml(plan_path)
    plan_id = str(plan.get("id") or "").strip()
    if not plan_id:
        raise SystemExit("plan file missing 'id'")

    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    created: list[dict[str, Any]] = []
    titles = args.title or ["(fill)"]
    for t in titles:
        task = task_skeleton(plan_id=plan_id, title=t, priority=args.priority)
        out = TASKS_DIR / f"{task['id']}.yml"
        out.write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), encoding="utf-8")
        created.append(task)
        print(f"Wrote {out.relative_to(ROOT)}")

    upsert_index(created)
    print(f"Updated { (TASKS_DIR / 'index.yml').relative_to(ROOT) }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

