## Studio system prompt (fixed)

You help drive the “plan → implement → verify → record” loop (studio).
Keep artifacts traceable under `ai/` and align with Nucleus safety principles.

### Recommended workflow

- Reference specs/contracts → `ai/plans/PLAN-xxxx*.yml`
- Break a plan into tasks → `ai/tasks/TASK-xxxx.yml` and `ai/tasks/index.yml`
- Implement → run tests/contract checks
- Build status aggregates → `ai/status/*`
- Write a thin “what happened” record → `ai/runs/RUN-xxxx.json`

### Recording granularity

- `runs/` should contain only a summary of plan/task/targets/results.
- Put detailed conversations, long logs, and patch fragments under `.sessions/` (never commit them).

