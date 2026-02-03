from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, Optional


def run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """
    Deterministic-ish HTTP tool (network side effects).

    Args schema (see bootstrap_tools):
      - method: "GET"|"POST"|"PUT"|"PATCH"|"DELETE"
      - url: string
      - headers: object (string->string)
      - json: any (will be json.dumps)
      - body: string (utf-8)
      - timeout_s: number
    """
    method = str(args.get("method") or "POST").upper()
    url = args.get("url")
    if not isinstance(url, str) or not url:
        raise ValueError("net.http: 'url' must be a non-empty string")

    headers = args.get("headers") or {}
    if headers is None:
        headers = {}
    if not isinstance(headers, dict) or any((not isinstance(k, str) or not isinstance(v, str)) for k, v in headers.items()):
        raise ValueError("net.http: 'headers' must be an object of string->string when provided")

    timeout_s = args.get("timeout_s", 10)
    if not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        timeout_s = 10

    body_bytes: Optional[bytes] = None
    if "json" in args and args.get("json") is not None:
        body_bytes = json.dumps(args.get("json"), ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json; charset=utf-8")
    elif "body" in args and args.get("body") is not None:
        b = args.get("body")
        if not isinstance(b, str):
            raise ValueError("net.http: 'body' must be a string when provided")
        body_bytes = b.encode("utf-8")

    if dry_run:
        summary = f"HTTP {method} {url}"
        return {"dry_run": True, "expected_effects": [{"kind": "net_http", "summary": summary, "resources": [url]}]}

    req = urllib.request.Request(url=url, data=body_bytes, method=method, headers=dict(headers))
    with urllib.request.urlopen(req, timeout=float(timeout_s)) as resp:  # noqa: S310
        raw = resp.read()
        # Keep response small and stable-ish.
        text = raw[:65536].decode("utf-8", errors="replace")
        return {
            "dry_run": False,
            "status": int(getattr(resp, "status", 0) or 0),
            "headers": {k: v for (k, v) in resp.headers.items()},
            "body_text": text,
            "truncated": len(raw) > 65536,
        }

