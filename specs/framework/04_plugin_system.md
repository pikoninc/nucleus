# 04 Plugin System

Nucleus is the **framework runtime**. Domain behavior lives in **processing units**.

## Processing unit model (App / Plugin)
Nucleus uses a symmetric mental model:

- **App**: application-level processing unit (often the entry point / integrator).
- **Plugin**: domain-focused processing unit designed for reuse across Apps.

Both share the same structural model and can be described via the same manifest/registry mechanism.
The difference is **responsibility and composition**, not runtime mechanics.

## What framework owns
- **Plugin manifest contract** (`contracts/core/schemas/plugin_manifest.schema.json`)
  - Naming note: the contract is called `PluginManifest` for historical reasons, but it can describe any processing unit (App or Plugin).
- Loading and validation of manifests
- Registries (plugins, tools, UI adapters)
- Routing from `Intent.intent_id` to a processing-unit-provided handler/planner (mechanism only)

## What plugins own (out of scope for framework edits)
- Domain rules and heuristics
- Intent parameter semantics
- Plan generation content (golden plans)

## Registry model (minimal)
- Plugin (processing unit) registry stores validated manifests and resolves `intent_id`.
- Tool registry stores deterministic tool implementations and their metadata.
- UI registry stores adapter I/O capabilities (contracts; UI behavior lives outside kernel).

