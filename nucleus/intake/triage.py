from __future__ import annotations

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
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent_id": {"type": "string", "minLength": 1},
            "params": {"type": "object"},
            "scope": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "fs_roots": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                    "allow_network": {"type": "boolean"},
                },
                "required": ["fs_roots"],
            },
            "context": {"type": "object"},
        },
        "required": ["intent_id", "params", "scope"],
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
            "Your job is to triage user input into a single contract-shaped Intent JSON object.",
            "Hard constraints:",
            "- No tool execution. No side effects. Output JSON only.",
            "- intent_id MUST be one of the allowed intents listed below.",
            "- scope MUST be preserved exactly as provided (do not add new roots; do not enable allow_network).",
            "",
            "Allowed intents:",
            *[f"- {iid}" for iid in sorted(set(intent_ids))],
            "",
            "Provided scope (must copy exactly):",
            f"{scope}",
            "",
            "If the user request is ambiguous, choose the safest intent and put clarifying needs into params.clarify (array of strings).",
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
    if "params" not in intent or not isinstance(intent.get("params"), dict):
        intent["params"] = {}

    # Validate against core Intent contract.
    store = _core_contracts()
    errs = store.validate("intent.schema.json", intent)
    if errs:
        raise ValidationError(code="intake.intent_invalid", message="Triage intent failed contract validation", data={"errors": errs})

    return IntakeTriageResult(intent=intent, provider=provider_id, model=model, raw_response=raw if isinstance(raw, dict) else {})

