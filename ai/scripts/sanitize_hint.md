## sanitize_hint.md (what NOT to include in versioned logs)

Because `ai/runs/` is intended to be versioned in Git, do **not** put secrets or raw logs there.
Keep chat logs, long outputs, and non-public details under `ai/.sessions/`, and only store curated summaries in `ai/runs/` when needed.

### Do NOT include (examples)

- API keys / tokens / credentials, `.env`-equivalent data
- Personal data (names, emails, addresses, account IDs, etc.)
- Customer names, internal-only URLs, non-public incident information
- Raw terminal output pasted as-is (long logs, environment details, paths, hostnames, etc.)
- Patch fragments or full unreviewed code dumps (prefer PR/commit references)

### What is OK to keep (recommended granularity)

- Which `PLAN-*` / `TASK-*` you worked on
- File paths you touched (as long as non-sensitive)
- Verification you ran (e.g., `python scripts/check_contracts.py`, unit tests) and the outcome (pass/fail)
- If something failed: a **short summary** (not full error logs; include category + next action)

