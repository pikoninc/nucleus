# Stdout UI Adapter (Output facet)

## Outputs
The kernel produces:
- Policy decisions (allow/deny + reason codes)
- Execution results per step (tool outputs)
- Trace JSONL path for audit/debug

Adapters may render:
- plan preview (expected_effects)
- step-by-step progress
- trace summary

## Relationship to input adapters
Stdout is the default output channel for terminal-based adapters.
Some adapters may only emit JSON (e.g. `Intent`) and rely on terminal stdout/stderr as the effective UI.

## Source of truth
- `contracts/core/schemas/trace_event.schema.json`

