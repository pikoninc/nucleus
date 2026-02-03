# 07 UI Adapters

UI adapters translate external I/O into framework contracts.

## UI adapter = Input + Output (same concept)
In practice, a UI adapter is a **request/response boundary**:
- **Input**: accept external input (text, button clicks, webhook payloads, etc.)
- **Output**: present the result back to the user/channel (HTTP response, Slack/Discord message, terminal output, etc.)

The repository documents adapters under `ui_adapters/<adapter_id>/` (e.g. `http`, `cli`, `alfred`).
Historically, some content lived under `ui_adapters/input` and `ui_adapters/output`, but those are only
organizational facets; the adapter concept remains the same.
Some adapters may be effectively one-way (e.g. emit JSON to stdout) and rely on a default renderer.

## Input facet
- Accept external input and produce (or obtain via intake) an `Intent` that validates against `contracts/core/schemas/intent.schema.json`.
- May attach UI context (metadata) but must not bypass safety invariants.
- May implement (or call) **Input Intake (LLM)** to normalize ambiguous user input into a contract-shaped `Intent`.
  - Intake must have **no tool access** and must not commit configuration or execute actions.
  - The kernel boundary starts at the validated `Intent`.

## Output facet
- Present plan previews and policy decisions (including denials).
- Present execution summaries and trace locations.
- Can render `TraceEvent` streams for audit/debug.

## Kernel boundary
- Kernel does not depend on a specific UI.
- Kernel outputs are contract-shaped objects + trace events; adapters handle UX.

