# Nucleus: AI Instructions (Read First)

AI agents working in this repository (Claude Code / Cursor / Copilot Chat, etc.) must follow these instructions with highest priority.

## 0. Language
- Do **not** hardcode a language preference in repo-level rules.
- Follow higher-level instructions. Default is **English** unless otherwise specified.

## 0.5. Cross-chat continuity (important)
- Raw chat logs are **not** automatically loaded in new chats.
- **Read `ai/memory.md` first** (curated decisions and current context).
- Only reference `ai/.sessions/` logs when necessary.

## 1. What this repo is
- This is the **Nucleus framework** repository.
- Nucleus enforces a strict separation: AI may propose; only deterministic runtime/tools may execute.

## 2. Hard safety rules
- **Do not perform destructive operations** (delete/overwrite/move) without an explicit user request.
  - `ai/` and `specs/` are especially important framework artifacts.
- **Do not output or commit secrets**
  - `.env`, credentials, tokens, personal data, etc.
- **Do not assume data can be sent externally**
  - If external sharing is needed, explain why, minimize scope, and provide alternatives.

## 3. Development workflow
- Spec-driven: start from `specs/`.
- CLI: `nuc` is provided.
  - App scaffold: `nuc init`

## 4. Working agreement
- Keep changes small and reviewable.
- Do not break existing design, tests, or contracts (`contracts/`).
- When possible, run verification (e.g., tests).

## 4.1 Test-Driven Development (TDD) is required
For any behavior change (feature/bugfix), follow TDD:
- **Red**: write or update a test that fails for the current behavior.
- **Green**: implement the minimal change to make the test pass.
- **Refactor**: clean up without changing behavior.
- **Run tests**: at minimum the relevant tests; ideally `python -m unittest -q`.

**Do not ship behavior changes without tests.**
If a test is truly impractical, explicitly document why and propose the smallest acceptable alternative (e.g., contract validation, deterministic plan snapshot test).

## 5. Common commands
- Tests:
  - `python -m unittest -q`
- Install (dev):
  - `pip install -e .`

## 6. Directory map
- `nucleus/`: framework runtime (Python)
- `plugins/`: built-in plugins (e.g. `builtin_desktop`)
- `contracts/`: schemas/contracts (JSON Schema etc.), used at runtime
- `specs/`: framework specs (source of truth)
- `ai/`: AI ops workspace (reviewable artifacts; no raw logs)

## 7. `nuc init` expectations
New apps created by `nuc init` should include at least:
- `<app_id>/specs/` (spec-driven starting point)
- `<app_id>/ai/` (optional but recommended)
- `<app_id>/pyproject.toml` (app package definition)

