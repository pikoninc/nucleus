# Nucleus Framework Spec Index

## What is Nucleus?
Nucleus is a **plan-first execution runtime** that turns human intent into safe, deterministic actions:
**Intent → Plan → Act → Trace**.

Nucleus is NOT an app. Apps are plugins.

## Scope
This folder defines the Nucleus framework:
- Kernel orchestration (Intent→Plan→Act→Trace)
- Core contracts + compatibility rules
- Safety model (scope/permissions, confirmation, rollback)
- Plugin system (manifest, loading, registries)
- Tool contracts (deterministic tools only)
- Trace/audit model (event schema, storage, replay)
- UI adapter I/O contracts (input/output as adapters)

## Non-Goals
- Plugin-specific behavior (classification rules, domain heuristics)
- Editing plugin implementations (except plugin system mechanics)

## Source of Truth (order)
1. contracts/core/schemas/*
2. contracts/core/VERSION
3. specs/framework/*.md
4. specs/framework/adr/*

## Allowed to Edit (framework tasks)
- nucleus/**
- contracts/core/**  (ONLY with ADR + versioning + tests)
- tools/**           (tool behavior/contract only)
- ui_adapters/**     (adapter I/O contract only)
- specs/framework/**
- tests/contract/**, tests/nucleus/**, scripts/**

## Forbidden to Edit (framework tasks)
- plugins/**
- specs/plugins/**
- contracts/plugins/**

## Compatibility & Versioning
- contracts/core is the public API.
- Prefer additive changes.
- Any change to contracts/core requires:
  - ADR entry in specs/framework/adr/
  - bump contracts/core/VERSION
  - update contracts/core/examples/
  - contract tests passing

## Safety Invariants (must always hold)
- No delete by default
- Explicit scope + permission validation
- Plan-first gating (confirmation based on policy/risk)
- Rollback/staging support for side-effects
- Deterministic tool execution (no arbitrary shell from AI)
- Trace every step (auditable)

## Definition of Done
- Schemas validate + examples updated
- ADR added when contracts/core changes
- Nucleus kernel tests pass
- Clear list of files changed + rationale

## Map
- 00_overview.md
- 01_architecture.md
- 02_contracts.md
- 03_safety_model.md
- 04_plugin_system.md
- 05_tool_contracts.md
- 06_trace_audit.md
- 07_ui_adapters.md
- adr/*

