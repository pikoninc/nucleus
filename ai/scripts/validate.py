from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def require_keys(obj: dict[str, Any], keys: list[str], *, where: str) -> list[str]:
    errs: list[str] = []
    for k in keys:
        if k not in obj:
            errs.append(f"{where}: missing '{k}'")
    return errs


def validate_plan(path: Path) -> list[str]:
    doc = load_yaml(path) or {}
    if not isinstance(doc, dict):
        return [f"{path}: not a mapping"]
    errs = []
    errs.extend(require_keys(doc, ["version", "id", "title", "status"], where=str(path)))
    return errs


def validate_task(path: Path) -> list[str]:
    doc = load_yaml(path) or {}
    if not isinstance(doc, dict):
        return [f"{path}: not a mapping"]
    errs = []
    errs.extend(require_keys(doc, ["version", "id", "plan_id", "title", "status"], where=str(path)))
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate ai/ YAML files (minimal structural checks).")
    ap.add_argument("--ai-dir", default=str(AI_DIR))
    args = ap.parse_args()

    ai_dir = Path(args.ai_dir)
    plans_dir = ai_dir / "plans"
    tasks_dir = ai_dir / "tasks"

    errors: list[str] = []

    for p in sorted(plans_dir.glob("PLAN-*.yml")) if plans_dir.exists() else []:
        errors.extend(validate_plan(p))

    for t in sorted(tasks_dir.glob("TASK-*.yml")) if tasks_dir.exists() else []:
        errors.extend(validate_task(t))

    if errors:
        print("AI ops validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1

    print("AI ops validation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

