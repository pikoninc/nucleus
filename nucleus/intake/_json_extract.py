from __future__ import annotations

import json
from typing import Any, Dict, Optional


def extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort extraction of the first JSON object from a text response.

    Many LLM APIs return a text blob even when instructed to output JSON only.
    This helper attempts to locate and parse the first JSON object.
    """
    if not isinstance(text, str) or not text:
        return None

    dec = json.JSONDecoder()
    # Try raw_decode at each '{' occurrence.
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _end = dec.raw_decode(text[i:])
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict):
            return obj
    return None

