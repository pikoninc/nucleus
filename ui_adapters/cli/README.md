# CLI UI Adapter (Contract)

## Input format
CLI input produces an **Intent JSON** that validates against:
- `contracts/core/schemas/intent.schema.json`

Minimum required fields:
- `intent_id` (string)
- `params` (object)
- `scope` (object; must include `fs_roots`)

## Notes
- Adapters must not bypass safety invariants.
- Execution requires a validated `Plan` (plan-first gating).

## Output behavior
For terminal-based adapters, **stdout/stderr act as the default output facet**:
- stdout: typically machine-readable JSON (Intent / Plan / execution result)
- stderr: human-friendly messages and notifications

## OpenAI intake (environment)
When using intake commands that call OpenAI (e.g. `nuc intake` with `--provider openai.responses`, or `nuc desktop ai`),
set `OPENAI_API_KEY`.

- **Recommended**: copy `env.example` to `.env` and fill in your key.
- The CLI will load `.env` (and also `env`) from the current working directory on startup.

