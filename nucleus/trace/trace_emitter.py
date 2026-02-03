from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .trace_store_jsonl import TraceStoreJSONL


class TraceEmitter:
    def __init__(self, store: TraceStoreJSONL, run_id: str):
        self._store = store
        self._run_id = run_id

    def emit(
        self,
        event_type: str,
        *,
        intent_id: str | None = None,
        plan_id: str | None = None,
        step_id: str | None = None,
        policy: dict[str, Any] | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "run_id": self._run_id,
            "event_type": event_type,
        }
        if intent_id is not None:
            event["intent_id"] = intent_id
        if plan_id is not None:
            event["plan_id"] = plan_id
        if step_id is not None:
            event["step_id"] = step_id
        if policy is not None:
            event["policy"] = policy
        if message is not None:
            event["message"] = message
        if data is not None:
            event["data"] = data

        self._store.append(event)

