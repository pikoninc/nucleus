# 07 UI Adapters

UI adapters translate external I/O into framework contracts.

## Input adapters
- Produce an `Intent` (JSON) that validates against `contracts/core/schemas/intent.schema.json`.
- May attach UI context (metadata) but must not bypass safety invariants.

## Output adapters
- Present plan previews and policy decisions (including denials).
- Present execution summaries and trace locations.
- Can render `TraceEvent` streams for audit/debug.

## Kernel boundary
- Kernel does not depend on a specific UI.
- Kernel outputs are contract-shaped objects + trace events; adapters handle UX.

