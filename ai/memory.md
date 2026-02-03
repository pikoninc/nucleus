# AI Memory (Summary & Decisions)

This file is a **curated, cross-chat memory** for the repository.
Do not paste raw logs here (keep raw logs under `ai/.sessions/`). Only keep:
- decisions
- assumptions
- current focus
- next actions

## How to use (start of a new chat)
- Cursor: attach `@ai/memory.md` at the start of the chat
- Claude Code: reads `CLAUDE.md` automatically → use this file as the curated context

## Update rule (3 lines)
For each new entry, keep it short:
- **Decision**: what was decided
- **Why**: why it was decided
- **Next**: what to do next

## Project overview (one paragraph)
- Nucleus is a spec-driven runtime/framework centered on strict separation: AI may propose, while execution must happen only via deterministic tools. Schemas under `contracts/` are treated as runtime contracts, and `specs/` is the source of truth for design.

## Key decisions (changelog)
> Add the date (YYYY-MM-DD) and keep the rationale clear.

- **2026-02-03**: Added `pyproject.toml` to make the framework installable via `pip install`, providing console scripts `nuc` (and `nucleus`). Implemented `nuc init` for app scaffolding (interactive + non-interactive). Also aligned resource path resolution so `contracts/` and `plugins/` work in installed environments.
- **2026-02-03**: Standardized AI behavior control by adding entry-point instruction files: `CLAUDE.md`, `.cursor/rules/*.mdc`, and `.github/copilot-instructions.md`. Unified cross-chat continuity: read `ai/memory.md` first instead of raw logs.

## Current focus
- Solidify the curated memory workflow so new chats do not lose context (use `ai/memory.md` as the source of truth).

## Safety / policy notes
- Destructive operations only when explicitly requested by the user.
- `contracts/` is a runtime contract (schema compatibility matters).
- Raw logs under `ai/.sessions/` are not versioned (ignored by `.gitignore`).

## Directory map
- `nucleus/`: framework runtime
- `plugins/`: built-in plugins
- `contracts/`: schemas/contracts (JSON Schema etc.)
- `specs/`: specs (source of truth)
- `ai/`: AI ops workspace (reviewable)
- `ai/.sessions/`: raw logs (not versioned)

## Common commands
- Tests: `python -m unittest -q`
- Install (dev): `pip install -e .`

## Next actions
- Define and document the ongoing maintenance workflow for `ai/memory.md` (template + review discipline).
- If needed, evolve the `nuc init` app scaffold templates (initial specs, README, minimal runnable path).

## References (only when needed)
- Referenced raw logs: `ai/.sessions/...`

