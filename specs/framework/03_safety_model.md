# 03 Safety Model

Nucleus enforces safety at **contract**, **policy**, and **execution** layers.

## Invariants (must always hold)
- **No delete by default**: destructive operations are denied unless explicitly allowed by policy.
- **Explicit scope**: every `Intent` and `Plan` must declare scope, and execution must validate against it.
- **Plan-first gating**: Nucleus executes only a validated `Plan`, never raw intent.
- **Rollback/staging support**: plans can express staging/commit/rollback phases; policy can require staging first.
- **Deterministic execution**: only registered deterministic tools; no arbitrary shell.
- **Trace every step**: every decision and step is emitted as `TraceEvent` (including denials).

## Scope model (minimal)
Scope is a structured allowlist of resources the plan may touch (e.g., filesystem roots).
Policy must reject plans that attempt actions outside declared scope.

## Confirmation model
Framework supports a policy-driven gate that can require confirmation for risky plans.
Confirmation is modeled as a policy decision + trace; UI adapters can implement UX.

## Rollback/staging
- `phase=staging`: prepare / preview / no irreversible effects.
- `phase=commit`: apply effects.
- `phase=rollback`: revert effects (best-effort; must be explicit in plan).

## No-delete default
Tools and plan steps can be marked destructive; policy rejects by default.

