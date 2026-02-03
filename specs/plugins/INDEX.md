# Plugin Specs Index

This folder is reserved for **plugin/app (processing unit)** specifications.

## Purpose
- Capture domain semantics, heuristics, and UX expectations that are intentionally out of scope for the Nucleus framework kernel.
- Provide a stable, reviewable place for processing-unit behavior specs that can evolve independently from `specs/framework/`.

## Relationship to the framework
- The framework (`specs/framework/`) defines contracts, safety invariants, and deterministic execution rules.
- Plugins/Apps define what an intent *means* and which plans they should generate.

## Suggested layout (optional)
- `specs/plugins/<processing-unit-id>/INDEX.md`
- `specs/plugins/<processing-unit-id>/intents/*.md`
- `specs/plugins/<processing-unit-id>/plans/*.md`

