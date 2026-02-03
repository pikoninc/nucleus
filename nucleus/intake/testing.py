from __future__ import annotations

from typing import Any, Dict, List


class FirstAllowedIntentProvider:
    """
    Deterministic provider for tests/examples.

    It parses the system prompt produced by triage_text_to_intent() to find the first
    allowed intent_id and returns a minimal Intent-like object.
    """

    def __init__(self, model: str = "stub", **_kwargs: Any) -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def triage(self, *, input_text: str, system_prompt: str, intent_schema: Dict[str, Any]) -> Dict[str, Any]:
        _ = (input_text, intent_schema)
        intent_ids: List[str] = []
        in_allowed = False
        for line in system_prompt.splitlines():
            if line.strip() == "Allowed intents:":
                in_allowed = True
                continue
            if in_allowed:
                s = line.strip()
                if not s:
                    break
                if s.startswith("- "):
                    intent_ids.append(s[2:].strip())
        intent_id = intent_ids[0] if intent_ids else "unknown.intent"
        return {"intent_id": intent_id, "params": {}, "scope": {"fs_roots": ["."], "allow_network": False}, "context": {}}


class ModelAsIntentProvider:
    """
    Deterministic provider for tests/examples.

    It returns an Intent whose intent_id is exactly the provided model string.
    This lets tests select a specific intent without adding extra constructor kwargs.
    """

    def __init__(self, model: str = "stub", **_kwargs: Any) -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def triage(self, *, input_text: str, system_prompt: str, intent_schema: Dict[str, Any]) -> Dict[str, Any]:
        _ = (input_text, system_prompt, intent_schema)
        return {"intent_id": self._model, "params": {}, "scope": {"fs_roots": ["."], "allow_network": False}, "context": {}}

