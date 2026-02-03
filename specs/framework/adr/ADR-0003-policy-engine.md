# ADR-0003: Policy Engine Model

## Status
Accepted

## Context
Nucleus must enforce safety invariants consistently and explain decisions clearly.

## Decision
Policy evaluation returns a structured decision:
- allow/deny
- reason codes
- human-readable summary

Minimum enforced invariants:
- explicit scope required
- plan-first gating
- destructive operations denied by default
- dry-run constraints honored

## Consequences
- Kernel can provide safe defaults (deny-by-default) while enabling future extensibility.
- Errors remain actionable for plugin developers (clear validation + reasons).

