# Nucleus: AI Agent Instructions (Entry Point)

AI agents working in this repository must follow these instructions with highest priority.

## Read first
- **Curated context**: `ai/memory.md` (cross-chat continuity)
- **Baseline rules**: `CLAUDE.md` (project policy & safety)

## Non-negotiable rules (short)
- **Language**: Do not hardcode language here. Follow higher-level instructions (default: English).
- **No destructive operations** (delete/overwrite/move) without an explicit user request.
  - `ai/` and `specs/` are especially important framework artifacts.
- **No secrets**: do not output or commit credentials/tokens/PII.
- **Spec-driven**: start from `specs/`.
- **Do not break contracts**: `contracts/` is runtime schema/contract.
- **TDD required**: for behavior changes, start by writing a failing test, then implement to make it pass. Do not ship behavior changes without tests.

## Starting a new chat (template)
In a new chat, attach `ai/memory.md` first (Cursor: `@ai/memory.md`).
Only attach raw logs (`ai/.sessions/...`) or additional files when needed.

