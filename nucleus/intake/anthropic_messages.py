from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from nucleus.core.errors import ValidationError


@dataclass(frozen=True)
class AnthropicMessagesConfig:
    api_base: str = "https://api.anthropic.com"
    api_key_env: str = "ANTHROPIC_API_KEY"
    timeout_s: float = 30.0
    anthropic_version: str = "2023-06-01"


def _default_http_post(url: str, *, headers: Dict[str, str], body: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (intake is explicitly network-capable)
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else repr(e)
        raise ValidationError(code="intake.anthropic_http_error", message="Anthropic HTTP error", data={"status": e.code, "body": msg}) from e
    except Exception as e:  # noqa: BLE001
        raise ValidationError(code="intake.anthropic_request_failed", message="Anthropic request failed", data={"error": repr(e)}) from e

    try:
        obj = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        raise ValidationError(code="intake.anthropic_invalid_json", message="Anthropic response was not valid JSON", data={"raw": raw[:1000]}) from e
    if not isinstance(obj, dict):
        raise ValidationError(code="intake.anthropic_invalid_json", message="Anthropic response must be a JSON object")
    return obj


class AnthropicMessagesClient:
    """
    Minimal Anthropic Messages API client (no extra dependency).
    """

    def __init__(
        self,
        *,
        config: Optional[AnthropicMessagesConfig] = None,
        http_post: Optional[Callable[..., Dict[str, Any]]] = None,
    ) -> None:
        self._config = config or AnthropicMessagesConfig()
        self._http_post = http_post or _default_http_post

    def create_message(
        self,
        *,
        model: str,
        input_text: str,
        system_prompt: str,
        max_tokens: int = 800,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(model, str) or not model:
            raise ValidationError(code="intake.invalid", message="model must be a non-empty string")
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValidationError(code="intake.invalid", message="input_text must be a non-empty string")

        key = api_key or os.environ.get(self._config.api_key_env)
        if not isinstance(key, str) or not key:
            raise ValidationError(code="intake.missing_api_key", message=f"Missing Anthropic API key (env: {self._config.api_key_env})")

        url = self._config.api_base.rstrip("/") + "/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": self._config.anthropic_version,
            "content-type": "application/json",
        }
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens),
            "system": system_prompt,
            "messages": [{"role": "user", "content": input_text}],
        }
        return self._http_post(url, headers=headers, body=body, timeout_s=self._config.timeout_s)

