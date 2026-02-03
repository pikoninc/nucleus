from __future__ import annotations

from typing import Any, Dict, Optional

from nucleus.core.errors import ValidationError

from .openai_responses import OpenAIResponsesClient


class OpenAIResponsesTriageProvider:
    """
    Triage provider using OpenAI Responses API.

    The provider returns the parsed JSON object (structured output) as a dict.
    """

    def __init__(self, *, client: OpenAIResponsesClient, model: str, api_key: Optional[str] = None) -> None:
        self._client = client
        self._model = model
        self._api_key = api_key

    @property
    def model(self) -> str:
        return self._model

    def triage(self, *, input_text: str, system_prompt: str, intent_schema: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._client.create_response(
            model=self._model,
            input_text=input_text,
            response_json_schema=intent_schema,
            system_prompt=system_prompt,
            api_key=self._api_key,
        )

        # Responses API returns content in `output`. For structured outputs, the JSON object is typically present
        # as a string in a content item; we accept a few common shapes.
        if not isinstance(resp, dict):
            raise ValidationError(code="intake.invalid_response", message="OpenAI response must be an object")

        # Try the canonical Responses layout first.
        out = resp.get("output")
        if isinstance(out, list) and out:
            # Look for first content item with JSON-ish text.
            for item in out:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    # Many SDKs use {"type":"output_text","text":"..."}.
                    txt = c.get("text")
                    if isinstance(txt, str) and txt.strip().startswith("{"):
                        try:
                            import json

                            return json.loads(txt)
                        except Exception:  # noqa: BLE001
                            continue
                    # Some modes may return already-parsed JSON.
                    if isinstance(c.get("json"), dict):
                        return c["json"]

        # Fallback: accept already structured content under known keys.
        if isinstance(resp.get("output_parsed"), dict):
            return resp["output_parsed"]

        raise ValidationError(code="intake.invalid_response", message="Could not extract structured intent from OpenAI response", data={"keys": list(resp.keys())})

