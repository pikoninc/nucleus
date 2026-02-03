# 00 Overview

Nucleus is a **spec-driven, plan-first execution runtime**. It turns an `Intent` into a validated `Plan`, then executes it via deterministic `Tools`, while emitting an auditable `Trace`.

## Core loop
- Intent → Plan → Act → Trace

## Principles
- **Separation of thinking and execution**:
  - Humans and LLMs may think, classify, and propose.
  - Only the runtime executes deterministic steps. LLMs never execute tools.
- **Specification as the source of truth**:
  - Specs define intent and constraints; conversations are context, never state.
- **Contracts-first**: `contracts/core/schemas/*` is the runtime boundary and source of truth.
- **Deterministic execution**: Nucleus executes only registered deterministic tools. No arbitrary shell execution.
- **Safety invariants** (must always hold):
  - No delete by default
  - Explicit scope validation
  - Plan-first gating
  - Rollback/staging support
  - Trace every step

## High-level layers (conceptual)
- **Input Intake (LLM)**: normalizes ambiguous user input into a contract-shaped `Intent` (no execution).
- **Processing units (App / Plugin)**: domain-aware components that plan work from an `Intent`.
- **Studio (LLM)**: proposes config/manifest/spec changes as reviewable patches (no tools).
- **Planner / Compiler (deterministic)**: converts manifests/config into executable `Plan`s.
- **Executor (deterministic)**: runs `Plan` steps via registered tools and records trace.

## Non-goals
- Plugin-specific heuristics and behavior
- Editing plugin implementations (except plugin system mechanics in framework)

