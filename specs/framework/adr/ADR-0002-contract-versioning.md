# ADR-0002: Core Contract Versioning

## Status
Accepted

## Context
`contracts/core` is the public API for plugin authors and UI adapters.
We must provide predictable compatibility guarantees.

## Decision
- Use **SemVer** in `contracts/core/VERSION`.
- Prefer **additive** changes to schemas:
  - adding optional fields
  - adding new enum values with safe defaults
  - relaxing constraints when safe
- Breaking changes require a MAJOR bump.

## Required process for any change to contracts/core
- Add/update an ADR under `specs/framework/adr/`
- Bump `contracts/core/VERSION`
- Update `contracts/core/examples/`
- Ensure `tests/contract` pass

## Consequences
- Schema evolution is deliberate and auditable.
- Plugin developers can rely on stable interfaces.

