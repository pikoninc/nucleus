# CLI Input Adapter (Contract)

## Input format
CLI input produces an **Intent JSON** that validates against:
- `contracts/core/schemas/intent.schema.json`

Minimum required fields:
- `intent_id` (string)
- `params` (object)
- `scope` (object; must include `fs_roots`)

## Notes
- Adapters must not bypass safety invariants.
- Execution requires a validated `Plan` (plan-first gating).

