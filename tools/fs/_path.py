from __future__ import annotations

import os
from pathlib import Path


def expand_user_path(p: str) -> Path:
    # Keep deterministic: expand ~ and environment vars in a standard way.
    return Path(os.path.expandvars(os.path.expanduser(p))).resolve()

