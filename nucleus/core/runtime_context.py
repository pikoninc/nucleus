from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeContext:
    """
    Runtime configuration that influences policy and execution.

    Hard rules:
    - Deterministic execution only (no arbitrary shell).
    - Safety invariants must hold.
    """

    run_id: str
    dry_run: bool = True
    strict_dry_run: bool = True
    allow_destructive: bool = False
    trace_path: Path = Path("trace.jsonl")
    meta: dict[str, Any] = field(default_factory=dict)

