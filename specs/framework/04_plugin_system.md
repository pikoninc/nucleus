# 04 Plugin System

Plugins are **apps**. Nucleus is the **framework runtime**.

## What framework owns
- **Plugin manifest contract** (`contracts/core/schemas/plugin_manifest.schema.json`)
- Loading and validation of manifests
- Registries (plugins, tools, UI adapters)
- Routing from `Intent.intent_id` to a plugin-provided handler/planner (mechanism only)

## What plugins own (out of scope for framework edits)
- Domain rules and heuristics
- Intent parameter semantics
- Plan generation content (golden plans)

## Registry model (minimal)
- Plugin registry stores validated manifests and resolves `intent_id`.
- Tool registry stores deterministic tool implementations and their metadata.
- UI registry stores adapter I/O capabilities (contracts; UI behavior lives outside kernel).

