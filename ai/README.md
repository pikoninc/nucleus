## About `ai/`

This directory is an **AI operations workspace** (versioned in Git).
Its goal is to keep changes to the Nucleus codebase (e.g. `nucleus/`, `contracts/`, `specs/`) traceable and reviewable as:

> intent → plan → tasks → status → run record

### What goes here (versioned)

- `prompts/`: Fixed system prompts (consistency + safety baseline).
- `plans/`: Implementation plans derived from specs (decisions, scope, risks, test plan).
- `tasks/`: Executable task breakdown (acceptance criteria, affected areas, status).
- `status/`: Aggregations (board, milestones, lightweight metrics).
- `runs/`: Thin records of “what was done for which plan/task” (sanitized).
- `scripts/`: Helpers to drive `spec → plan → tasks → status`.

### What does NOT go here (not versioned)

- `.sessions/`: Conversation logs, raw outputs, patch fragments, etc. (**must not be committed**).
  - Excluded via ignore rules:
    - repo root `.gitignore` ignores `ai/.sessions/*`
    - `ai/.sessions/.gitignore` keeps the directory present but ignores all contents

### Naming conventions (recommended)

- Plan: `PLAN-0001-<short-slug>.yml`
- Task: `TASK-0001.yml`
- Run:  `RUN-0001.json`

### Operating principles

- **Public/reviewable**: Keep `ai/` contents at a granularity that is safe to review and (in principle) share.
- **Secrets go to `.sessions/`**: Do not put tokens, PII, customer names, private URLs, internal-only procedures, or raw logs here.
- **Reproducibility**: Prefer deterministic scripts; keep outputs in diff-friendly formats (YAML/JSON).

### Saving Cursor conversation logs (recommended)
If you use Cursor, the agent conversation transcripts are stored outside the repo under `~/.cursor/projects/*/agent-transcripts/`.
To sync them into `ai/.sessions/` (still ignored by git), run:

```bash
python ai/scripts/sync_cursor_transcripts.py
```

