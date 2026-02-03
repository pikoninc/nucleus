# 07 UI Adapters

UI adapters translate external I/O into framework contracts.

## Input adapters
- Produce an `Intent` (JSON) that validates against `contracts/core/schemas/intent.schema.json`.
- May attach UI context (metadata) but must not bypass safety invariants.
- May implement (or call) **Input Intake (LLM)** to normalize ambiguous user input into a contract-shaped `Intent`.
  - Intake must have **no tool access** and must not commit configuration or execute actions.
  - The kernel boundary starts at the validated `Intent`.

## Output adapters
- Present plan previews and policy decisions (including denials).
- Present execution summaries and trace locations.
- Can render `TraceEvent` streams for audit/debug.

## Kernel boundary
- Kernel does not depend on a specific UI.
- Kernel outputs are contract-shaped objects + trace events; adapters handle UX.

