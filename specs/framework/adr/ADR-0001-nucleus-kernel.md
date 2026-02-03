# ADR-0001: Nucleus Kernel Boundary

## Status
Accepted

## Context
We need a clear separation between framework responsibilities and plugin behavior.

## Decision
The Nucleus kernel owns:
- contract validation
- deterministic orchestration (Intent→Plan→Act→Trace)
- policy/permission enforcement
- tool invocation (registered deterministic tools only)
- trace emission and storage

Plugins own:
- domain semantics and heuristics
- intent parameter meaning
- plan content (steps, ordering, rollback strategies)

## Consequences
- Framework edits must not modify plugin implementations.
- Core contracts must remain stable and additive when possible.

