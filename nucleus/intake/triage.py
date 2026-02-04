from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence

from nucleus.contract_store import ContractStore
from nucleus.core.errors import ValidationError
from nucleus.resources import core_contracts_schemas_dir


@dataclass(frozen=True)
class IntakeTriageResult:
    """
    Intake output: a validated Intent plus optional metadata for audit/UX.
    """

    intent: Dict[str, Any]
    provider: str
    model: str
    raw_response: Dict[str, Any]


class TriageProvider(Protocol):
    def triage(self, *, input_text: str, system_prompt: str, intent_schema: Dict[str, Any]) -> Dict[str, Any]: ...


def _intent_json_schema_for_llm() -> Dict[str, Any]:
    # Self-contained JSON Schema (no $ref) suitable for OpenAI structured outputs.
    #
    # NOTE:
    # OpenAI structured outputs currently requires `additionalProperties: false` for object schemas.
    # The core Intent contract allows arbitrary params/context, so we carry params as a JSON string.
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent_id": {"type": "string", "minLength": 1},
            # JSON-encoded params object (arbitrary keys allowed once decoded).
            "params_json": {"type": "string"},
            # Optional clarifying questions (mapped to params.clarify).
            # NOTE: OpenAI structured outputs currently expects all top-level properties
            # to be included in `required` (even if semantically optional). Use an empty
            # array when there are no clarifying questions.
            "clarify": {"type": "array", "items": {"type": "string"}, "default": []},
        },
        "required": ["intent_id", "params_json", "clarify"],
    }


def _core_contracts() -> ContractStore:
    store = ContractStore(core_contracts_schemas_dir())
    store.load()
    return store


def triage_text_to_intent(
    *,
    input_text: str,
    intents_catalog: Sequence[Dict[str, str]],
    scope: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    provider: TriageProvider,
    provider_id: str,
    model: str,
    allow_network: bool = False,
) -> IntakeTriageResult:
    """
    Framework-standard intake triage:
    - accepts natural language input
    - calls an LLM provider (only if allow_network=True)
    - returns a contract-valid Intent (no execution; side-effect free)
    """
    if not allow_network:
        raise ValidationError(code="intake.network_denied", message="Network is disabled for intake triage")

    if not isinstance(input_text, str) or not input_text.strip():
        raise ValidationError(code="intake.invalid", message="input_text must be a non-empty string")
    if not isinstance(scope, dict):
        raise ValidationError(code="intake.invalid", message="scope must be an object")

    # Catalog is used to constrain intent selection.
    intent_ids: List[str] = []
    for it in intents_catalog:
        if isinstance(it, dict) and isinstance(it.get("intent_id"), str) and it.get("intent_id"):
            intent_ids.append(str(it["intent_id"]))
    if not intent_ids:
        raise ValidationError(code="intake.invalid", message="intents_catalog must contain at least one intent_id")

    system_prompt = "\n".join(
        [
            "You are Nucleus Intake.",
            "Your job is to triage user input into a single JSON object.",
            "Hard constraints:",
            "- No tool execution. No side effects. Output JSON only.",
            "- intent_id MUST be one of the allowed intents listed below.",
            "- You must NOT invent or expand filesystem scope; scope is adapter-owned and will be applied by the system.",
            "",
            "Output shape (JSON):",
            '- intent_id: string (required; choose from allowed intents)',
            '- params_json: string (required; JSON-encoded object of parameters)',
            '- clarify: string[] (optional; clarifying questions if needed)',
            "",
            "Allowed intents:",
            *[f"- {iid}" for iid in sorted(set(intent_ids))],
            "",
            "Provided scope (must copy exactly):",
            f"{scope}",
            "",
            "If the user request is ambiguous, choose the safest intent and put clarifying needs into clarify (array of strings).",
            "For params_json, if you have no params, use '{}' exactly.",
        ]
    )

    schema = _intent_json_schema_for_llm()
    raw = provider.triage(input_text=input_text, system_prompt=system_prompt, intent_schema=schema)

    # Extract the JSON object from provider output. Provider may return the intent directly.
    intent = raw.get("intent") if isinstance(raw, dict) else None
    if intent is None and isinstance(raw, dict):
        intent = raw
    if not isinstance(intent, dict):
        raise ValidationError(code="intake.invalid_response", message="Provider did not return an intent object")

    # Enforce intent_id allowlist
    iid = intent.get("intent_id")
    if iid not in set(intent_ids):
        raise ValidationError(
            code="intake.invalid_intent_id",
            message="Provider returned an unknown intent_id",
            data={"intent_id": iid, "allowed": sorted(set(intent_ids))},
        )

    # Scope/context are adapter-owned; intake must not invent safety boundaries.
    intent["scope"] = scope
    if context is not None:
        intent["context"] = context
    elif "context" not in intent:
        intent["context"] = {}

    params: Dict[str, Any] = {}
    if isinstance(intent.get("params"), dict):
        params = dict(intent["params"])
    elif isinstance(intent.get("params_json"), str):
        try:
            parsed = json.loads(str(intent["params_json"]))
            if isinstance(parsed, dict):
                params = dict(parsed)
        except Exception:  # noqa: BLE001
            params = {}

    clarify = intent.get("clarify")
    if isinstance(clarify, list):
        qs = [q for q in clarify if isinstance(q, str) and q.strip()]
        if qs:
            params["clarify"] = qs

    intent["params"] = params
    # Drop helper fields if present.
    if "params_json" in intent:
        intent.pop("params_json", None)
    if "clarify" in intent:
        intent.pop("clarify", None)

    # Validate against core Intent contract.
    store = _core_contracts()
    errs = store.validate("intent.schema.json", intent)
    if errs:
        raise ValidationError(code="intake.intent_invalid", message="Triage intent failed contract validation", data={"errors": errs})

    return IntakeTriageResult(intent=intent, provider=provider_id, model=model, raw_response=raw if isinstance(raw, dict) else {})

