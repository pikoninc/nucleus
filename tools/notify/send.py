from __future__ import annotations

import sys
from typing import Any, Dict


def run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """
    Send a notification (deterministic stdout implementation).
    args:
      - message: string
    """
    message = args.get("message")
    if not isinstance(message, str) or not message:
        raise ValueError("notify.send: 'message' must be a non-empty string")

    if dry_run:
        return {
            "dry_run": True,
            "expected_effects": [{"kind": "notify", "summary": f"Notify: {message}", "resources": []}],
        }

    # Deterministic side-effect: write to stderr (keeps JSON stdout stable for CLIs).
    print(message, file=sys.stderr)
    return {"dry_run": False, "sent": True}

