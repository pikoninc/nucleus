# 09 Studio

Studio is the **LLM-facing** layer used to propose changes to **specs, configuration, and manifests**.
It produces reviewable patches; it never executes tools.

## Role
- Collaborate with humans to draft changes to:
  - specs (`specs/**`)
  - manifests (e.g., processing unit manifests)
  - configuration files (app/plugin config, policies)
- Output changes as **diffs/patches** that are easy to review.

## Constraints (hard)
- **No execution**: Studio must not invoke runtime tools.
- **No irreversible decisions**: outputs must remain human-reviewable and revertible.
- **No hidden state**: conversations are context; the patch/diff is the explicit artifact.

## Relationship to planning/compilation
- Studio outputs may affect what the deterministic planner/compiler can produce, but only after:
  - human review/approval
  - schema validation (when contracts are involved)
  - policy enforcement at execution time

Studio is upstream of deterministic execution, not part of it.

## Recommended workflow (spec-driven)
Spec → Plan → Task → Implementation → Status

- **Spec**: update `specs/**` to define intent and constraints.
- **Plan/Task/Status**: keep reviewable work artifacts (see `ai/` workspace).
- **Implementation**: apply patches to code/config/contracts.

## Out of scope (framework)
- Choosing models/providers
- Long-running agent loops
- Any direct tool invocation or infrastructure changes

