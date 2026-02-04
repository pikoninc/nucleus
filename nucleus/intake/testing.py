from __future__ import annotations

import json
from typing import Any, Dict, List

from nucleus.core.errors import ValidationError


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


class RaiseValidationErrorProvider:
    """
    Provider for CLI tests: always raises a ValidationError with a data payload.
    """

    def __init__(self, model: str = "stub", **_kwargs: Any) -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def triage(self, *, input_text: str, system_prompt: str, intent_schema: Dict[str, Any]) -> Dict[str, Any]:
        _ = (input_text, system_prompt, intent_schema)
        raise ValidationError(
            code="intake.openai_http_error",
            message="OpenAI HTTP error",
            data={"status": 401, "body": "invalid_api_key"},
        )


class ModelAsJsonProvider:
    """
    Deterministic provider for tests/examples.

    It returns a JSON object parsed from the provided model string.
    Useful for testing non-intent LLM flows (e.g. config generation) without network.
    """

    def __init__(self, model: str = "{}", **_kwargs: Any) -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def triage(self, *, input_text: str, system_prompt: str, intent_schema: Dict[str, Any]) -> Dict[str, Any]:
        _ = (input_text, system_prompt, intent_schema)
        try:
            obj = json.loads(self._model)
        except Exception as e:  # noqa: BLE001
            raise ValidationError(code="intake.invalid_response", message="ModelAsJsonProvider model was not valid JSON", data={"error": repr(e)}) from e
        if not isinstance(obj, dict):
            raise ValidationError(code="intake.invalid_response", message="ModelAsJsonProvider must decode to a JSON object")
        return obj

