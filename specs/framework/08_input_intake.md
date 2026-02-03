# 08 Input Intake

Input Intake is the **LLM-facing** layer that turns ambiguous user input into a contract-shaped `Intent`.
It exists to tolerate ambiguity while keeping the runtime deterministic and auditable.

## Role
- Accept natural language input (and UI context).
- Clarify/normalize intent.
- Produce a structured `Intent` that validates against `contracts/core/schemas/intent.schema.json`.

In the README, this output is called an **IntentEnvelope**. In the framework, the authoritative boundary object is the `Intent` contract.

## Constraints (hard)
- **No execution**: Intake must not invoke tools or cause side effects.
- **No configuration commitment**: Intake may suggest changes, but it must not apply them.
- **No hidden state**: conversation logs are context only; the emitted `Intent` is the explicit state handed to the kernel.

## Relationship to UI adapters
- Intake can be implemented inside an input adapter (e.g., CLI, web) or as a separate service called by an adapter.
- The kernel boundary starts at the **validated `Intent`**. Everything before that is UI/intake territory.

## Recommended outputs
An input adapter should emit:
- the `Intent` JSON payload (contract-valid)
- optional UI metadata (non-authoritative, for UX)
- a preview/summary suitable for user confirmation (UX-level)

## Out of scope (framework)
- Prompt engineering and model selection
- Domain heuristics (belong to Apps/Plugins)
- Any tool execution

