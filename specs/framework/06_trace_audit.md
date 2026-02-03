# 06 Trace & Audit

Nucleus emits an append-only trace stream for every run.

## Why trace exists
- Auditing: who/what/why executed
- Safety: verify invariants were enforced
- Debugging: reproduce and replay decisions deterministically

## Trace format
- Storage: **JSON Lines** (`.jsonl`) — one `TraceEvent` per line.
- Schema: `contracts/core/schemas/trace_event.schema.json`

## Minimum events (recommended)
- `intent_received`
- `plan_generated`
- `policy_decision`
- `step_started`
- `step_finished`
- `step_denied`
- `run_finished`
- `error`

## Replay
Replay reads trace JSONL and can:
- reconstruct plan execution timeline
- verify that policy/guard decisions match recorded outcomes
- support dry-run style analysis

