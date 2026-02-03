from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List


def _normalize_path(p: str) -> Path:
    # Deterministic normalization: expand env + ~ then resolve to absolute path.
    return Path(os.path.expandvars(os.path.expanduser(p))).resolve()


def normalize_roots(fs_roots: Iterable[str]) -> List[Path]:
    roots: List[Path] = []
    for r in fs_roots:
        if not isinstance(r, str) or not r:
            continue
        roots.append(_normalize_path(r))
    return roots


def is_within_any_root(path_str: str, roots: List[Path]) -> bool:
    p = _normalize_path(path_str)
    for root in roots:
        try:
            # Python 3.7 compatible ancestor check
            if str(p) == str(root) or str(p).startswith(str(root) + os.sep):
                return True
        except Exception:
            continue
    return False

