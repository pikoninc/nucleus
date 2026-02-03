from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
PLANS_DIR = AI_DIR / "plans"
TASKS_DIR = AI_DIR / "tasks"
STATUS_DIR = AI_DIR / "status"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def iter_task_files() -> Iterable[Path]:
    if not TASKS_DIR.exists():
        return []
    return sorted([p for p in TASKS_DIR.glob("TASK-*.yml") if p.is_file()])


def iter_plan_files() -> Iterable[Path]:
    if not PLANS_DIR.exists():
        return []
    return sorted([p for p in PLANS_DIR.glob("PLAN-*.yml") if p.is_file()])


def build_board(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    columns = ["todo", "doing", "blocked", "done"]
    cards: list[dict[str, Any]] = []
    for t in tasks:
        cards.append(
            {
                "id": t.get("id"),
                "column": t.get("status", "todo"),
                "title": t.get("title", ""),
            }
        )
    return {"version": 1, "updated_at": date.today().isoformat(), "columns": columns, "cards": cards}


def build_metrics(plans: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    plan_counts = {"draft": 0, "active": 0, "done": 0, "archived": 0}
    for p in plans:
        s = str(p.get("status") or "draft")
        plan_counts[s] = plan_counts.get(s, 0) + 1

    task_counts = {"todo": 0, "doing": 0, "blocked": 0, "done": 0}
    for t in tasks:
        s = str(t.get("status") or "todo")
        task_counts[s] = task_counts.get(s, 0) + 1

    return {
        "version": 1,
        "updated_at": date.today().isoformat(),
        "counts": {"plans": plan_counts, "tasks": task_counts},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild ai/status/board.yml and ai/status/metrics.json from ai/plans & ai/tasks.")
    ap.parse_args()

    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    plans: list[dict[str, Any]] = []
    for p in iter_plan_files():
        doc = load_yaml(p) or {}
        if isinstance(doc, dict):
            plans.append(doc)

    tasks: list[dict[str, Any]] = []
    for t in iter_task_files():
        doc = load_yaml(t) or {}
        if isinstance(doc, dict):
            tasks.append(doc)

    board = build_board(tasks)
    (STATUS_DIR / "board.yml").write_text(yaml.safe_dump(board, sort_keys=False, allow_unicode=True), encoding="utf-8")

    metrics = build_metrics(plans, tasks)
    (STATUS_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Wrote ai/status/board.yml")
    print("Wrote ai/status/metrics.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

