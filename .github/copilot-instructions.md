# Nucleus Repository: GitHub Copilot Instructions

When using Copilot Chat / Coding Agent in this repository, follow these instructions.

## Language
- Do not hardcode language in repo rules. Follow higher-level instructions (default: English).

## Cross-chat continuity
- Raw chat logs are not automatically loaded in new chats.
- **Read `ai/memory.md` first** (curated summary & decisions).

## What this repo is
- This is the **Nucleus framework** repository.
- Nucleus enforces separation: AI may propose; deterministic runtime/tools may execute.

## Safety (highest priority)
- **No destructive operations** (delete/overwrite/move) without an explicit user request.
  - `ai/` and `specs/` are important framework artifacts.
- **No secrets**: do not output or commit tokens/credentials/PII.

## Workflow
- **Spec-driven**: start from `specs/`.
- **Do not break contracts**: JSON Schema / examples under `contracts/` are runtime contracts.
- CLI is `nuc` (console script). App scaffolding is `nuc init`.

## Verification
- When possible, run tests: `python -m unittest -q`

## Test-driven development (required)
For behavior changes (features/bugfixes), use TDD:
- Write/update a failing test first (Red).
- Implement the minimal fix (Green).
- Refactor and rerun tests.

Do not ship behavior changes without tests unless you explicitly justify why tests are impractical and propose a minimal alternative verification.

