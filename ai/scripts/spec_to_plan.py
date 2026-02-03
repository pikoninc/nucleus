from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
PLANS_DIR = AI_DIR / "plans"


def _next_plan_id() -> str:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    nums: list[int] = []
    for p in sorted(PLANS_DIR.glob("PLAN-*.yml")):
        stem = p.stem  # PLAN-0001-foo
        parts = stem.split("-")
        if len(parts) >= 2 and parts[0] == "PLAN":
            try:
                nums.append(int(parts[1]))
            except ValueError:
                continue
    n = (max(nums) + 1) if nums else 1
    return f"PLAN-{n:04d}"


def build_plan(*, title: str, slug: str, specs: list[str], contracts: list[str], code: list[str]) -> dict[str, Any]:
    plan_id = _next_plan_id()
    return {
        "version": 1,
        "id": plan_id,
        "slug": slug,
        "title": title,
        "status": "draft",
        "source": {
            "specs": specs,
            "contracts": contracts,
            "code": code,
        },
        "goals": [],
        "non_goals": [],
        "constraints": [],
        "deliverables": [],
        "risk_assessment": {"level": "low", "notes": []},
        "test_plan": [],
        "created_at": date.today().isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a new ai/plans/PLAN-xxxx-<slug>.yml skeleton.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--slug", required=True, help="short slug used in filename")
    ap.add_argument("--spec", action="append", default=[], dest="specs")
    ap.add_argument("--contract", action="append", default=[], dest="contracts")
    ap.add_argument("--code", action="append", default=[], dest="code")
    args = ap.parse_args()

    plan = build_plan(
        title=args.title,
        slug=args.slug,
        specs=args.specs,
        contracts=args.contracts,
        code=args.code,
    )

    out = PLANS_DIR / f"{plan['id']}-{args.slug}.yml"
    out.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

