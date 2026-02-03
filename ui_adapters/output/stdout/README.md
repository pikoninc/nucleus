# Stdout Output Adapter (Contract)

## Outputs
The kernel produces:
- Policy decisions (allow/deny + reason codes)
- Execution results per step (tool outputs)
- Trace JSONL path for audit/debug

Adapters may render:
- plan preview (expected_effects)
- step-by-step progress
- trace summary

## Source of truth
- `contracts/core/schemas/trace_event.schema.json`

