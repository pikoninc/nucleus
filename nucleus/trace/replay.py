from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable


class Replay:
    """
    Minimal JSONL replay reader.
    """

    def __init__(self, path: Path):
        self._path = path

    def iter_events(self) -> Iterable[Dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

