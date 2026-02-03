# 02 Contracts

## Source of truth
1. `contracts/core/schemas/*`
2. `contracts/core/VERSION`

Specs explain contracts; contracts define the runtime boundary.

## Core contracts
- **Intent**: `contracts/core/schemas/intent.schema.json`
- **Plan**: `contracts/core/schemas/plan.schema.json`
- **Tool**: `contracts/core/schemas/tool.schema.json`
- **TraceEvent**: `contracts/core/schemas/trace_event.schema.json`
- **PluginManifest**: `contracts/core/schemas/plugin_manifest.schema.json`

## Compatibility
- `contracts/core` is the public API.
- Prefer additive changes (new optional fields, new enum values with safe defaults).
- Any change to `contracts/core` requires:
  - ADR entry in `specs/framework/adr/`
  - bump `contracts/core/VERSION`
  - update `contracts/core/examples/`
  - `tests/contract` passing

## Examples
See `contracts/core/examples/*` for minimal valid payloads.

