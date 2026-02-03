# HTTP UI Adapter (Reference Spec)

This document defines a **recommended** HTTP API surface for building UI adapters
that front Nucleus (web apps, Discord/Slack webhooks, SMS gateways, etc.).

The implementation is up to the developer (framework is UI-agnostic), but following
this spec keeps adapters interoperable.

## Key boundary

- UI adapter receives user input and context.
- Adapter calls **Intake** to triage/normalize input into a contract-shaped **Intent**.
- Adapter (or a separate service) executes via kernel: `Intent -> Plan -> Policy -> Tools`.
- The HTTP response is the adapter's **output facet** (rendering/format is adapter-owned).

## Endpoints

### `POST /intake`
Input → Intake → `Intent` (no execution).

Request JSON:

- `input_text`: string (required)
- `scope`: object (required)
  - `fs_roots`: string[] (required)
  - `allow_network`: boolean (optional)
  - `network_hosts_allowlist`: string[] (optional)
- `context`: object (optional)

Response JSON:

- `intent`: Intent JSON
- `triage`: `{ provider, model }`

### `POST /run`
Execute a provided `Intent` via kernel (plan-first, policy enforced).

Request JSON:

- `intent`: Intent JSON (required)
- `run_id`: string (optional)
- `trace_path`: string (optional)
- `dry_run`: boolean (optional)

Response JSON:

- `intent`: the input intent
- `plan_id`
- `results`
- `trace_path`

### `POST /run_text`
One-shot convenience API: Input → Intake → Execute (synchronous).

Request JSON:

- `input_text`: string (required)
- `scope`: object (required)
- `context`: object (optional)
- `run_id`, `trace_path`, `dry_run`: optional (same as `/run`)

Response JSON:

- `intent`: triaged intent
- `triage`: `{ provider, model }`
- `plan_id`
- `results`
- `trace_path`

## Authentication (adapter-owned)

Authentication is intentionally **out of kernel scope** and must be implemented by the adapter:

- Web apps: session cookies / OAuth/OIDC bearer tokens
- Webhooks (Discord/Slack): signature verification (recommended)

The adapter uses auth to build:
- `context` (tenant/user identifiers)
- `scope` (resource allowlist boundaries)
- the allowed `intents_catalog` (if intake is used)

