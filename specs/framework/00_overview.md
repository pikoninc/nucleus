# 00 Overview

Nucleus is a **plan-first execution runtime**. It turns an `Intent` into a validated `Plan`, then executes it via deterministic `Tools`, while emitting an auditable `Trace`.

## Core loop
- Intent → Plan → Act → Trace

## Principles
- **Contracts-first**: `contracts/core/schemas/*` is the source of truth.
- **Deterministic execution**: Nucleus executes only registered deterministic tools. No arbitrary shell execution.
- **Safety invariants** (must always hold):
  - No delete by default
  - Explicit scope validation
  - Plan-first gating
  - Rollback/staging support
  - Trace every step

## Non-goals
- Plugin-specific heuristics and behavior
- Editing plugin implementations (except plugin system mechanics in framework)

