from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from nucleus.core.errors import ValidationError

from .triage import TriageProvider


@dataclass(frozen=True)
class LoadedProvider:
    provider: TriageProvider
    provider_id: str
    model: str


def _import_object(spec: str) -> Any:
    """
    Import by "module:attr" spec.
    """
    if ":" not in spec:
        raise ValidationError(code="intake.provider_invalid", message="provider spec must be 'module:object'")
    mod_name, attr = spec.split(":", 1)
    if not mod_name or not attr:
        raise ValidationError(code="intake.provider_invalid", message="provider spec must be 'module:object'")
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:  # noqa: BLE001
        raise ValidationError(code="intake.provider_not_found", message="Failed to import provider module", data={"module": mod_name}) from e
    if not hasattr(mod, attr):
        raise ValidationError(code="intake.provider_not_found", message="Provider object not found in module", data={"module": mod_name, "attr": attr})
    return getattr(mod, attr)


def _build_with_compatible_kwargs(obj: Any, kwargs: Dict[str, Any]) -> Any:
    """
    Instantiate a class or call a factory with only accepted kwargs.
    """
    try:
        sig = inspect.signature(obj)
    except Exception:  # noqa: BLE001
        return obj(**kwargs)  # best-effort

    accepted = {}
    for name, p in sig.parameters.items():
        if name == "self":
            continue
        if p.kind in (inspect.Parameter.VAR_KEYWORD,):
            accepted = dict(kwargs)
            break
        if name in kwargs:
            accepted[name] = kwargs[name]
    return obj(**accepted)


def load_triage_provider(
    *,
    provider: str,
    model: str,
    api_base: Optional[str] = None,
    api_key_env: Optional[str] = None,
) -> LoadedProvider:
    """
    Thin infra layer:
    - built-in provider IDs (e.g. "openai.responses")
    - external providers via "module:Class" or "module:factory"

    The returned object must satisfy the TriageProvider protocol (have .triage()).
    """
    if not isinstance(provider, str) or not provider:
        raise ValidationError(code="intake.provider_invalid", message="provider must be a non-empty string")
    if not isinstance(model, str) or not model:
        raise ValidationError(code="intake.invalid", message="model must be a non-empty string")

    if provider in ("openai.responses", "openai"):
        from .openai_responses import OpenAIResponsesClient, OpenAIResponsesConfig
        from .providers import OpenAIResponsesTriageProvider

        cfg = OpenAIResponsesConfig()
        if api_base:
            cfg = OpenAIResponsesConfig(api_base=api_base, api_key_env=cfg.api_key_env, timeout_s=cfg.timeout_s)
        if api_key_env:
            cfg = OpenAIResponsesConfig(api_base=cfg.api_base, api_key_env=api_key_env, timeout_s=cfg.timeout_s)
        client = OpenAIResponsesClient(config=cfg)
        return LoadedProvider(provider=OpenAIResponsesTriageProvider(client=client, model=model), provider_id="openai.responses", model=model)

    if provider in ("anthropic.messages", "anthropic"):
        from .anthropic_messages import AnthropicMessagesClient, AnthropicMessagesConfig
        from .providers import AnthropicMessagesTriageProvider

        cfg = AnthropicMessagesConfig()
        if api_base:
            cfg = AnthropicMessagesConfig(
                api_base=api_base,
                api_key_env=cfg.api_key_env,
                timeout_s=cfg.timeout_s,
                anthropic_version=cfg.anthropic_version,
            )
        if api_key_env:
            cfg = AnthropicMessagesConfig(
                api_base=cfg.api_base,
                api_key_env=api_key_env,
                timeout_s=cfg.timeout_s,
                anthropic_version=cfg.anthropic_version,
            )
        client = AnthropicMessagesClient(config=cfg)
        return LoadedProvider(provider=AnthropicMessagesTriageProvider(client=client, model=model), provider_id="anthropic.messages", model=model)

    if provider in ("google.gemini", "gemini", "google"):
        from .google_gemini import GoogleGeminiClient, GoogleGeminiConfig
        from .providers import GoogleGeminiTriageProvider

        cfg = GoogleGeminiConfig()
        if api_base:
            cfg = GoogleGeminiConfig(api_base=api_base, api_key_env=cfg.api_key_env, timeout_s=cfg.timeout_s)
        if api_key_env:
            cfg = GoogleGeminiConfig(api_base=cfg.api_base, api_key_env=api_key_env, timeout_s=cfg.timeout_s)
        client = GoogleGeminiClient(config=cfg)
        return LoadedProvider(provider=GoogleGeminiTriageProvider(client=client, model=model), provider_id="google.gemini", model=model)

    # Dynamic provider: "module:Class" or "module:factory"
    obj = _import_object(provider)
    kwargs: Dict[str, Any] = {"model": model, "api_base": api_base, "api_key_env": api_key_env}
    try:
        if inspect.isclass(obj):
            inst = _build_with_compatible_kwargs(obj, kwargs)
        elif callable(obj):
            inst = _build_with_compatible_kwargs(obj, kwargs)
        else:
            inst = obj
    except TypeError as e:
        raise ValidationError(code="intake.provider_invalid", message="Provider could not be constructed with given arguments", data={"provider": provider}) from e

    if not hasattr(inst, "triage") or not callable(getattr(inst, "triage")):
        raise ValidationError(code="intake.provider_invalid", message="Provider must have a callable triage() method", data={"provider": provider})

    return LoadedProvider(provider=inst, provider_id=provider, model=model)

