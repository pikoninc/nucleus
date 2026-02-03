# UI adapters (I/O boundary)

UI adapters are an **infrastructure layer** that makes UIs interchangeable.

Conceptually, a UI adapter is a **single request/response boundary**:
- it receives external input
- it calls intake to triage into an `Intent`
- it runs the kernel (or delegates execution)
- it renders output back to the channel/user

This repository documents adapters under `ui_adapters/<adapter_id>/` (e.g. `http`, `cli`, `alfred`).
Each adapter is a single I/O boundary (input + output facets).

Some adapters may be effectively one-way (e.g. emit `Intent` JSON), and rely on a default renderer.
For example, an Alfred workflow may only emit an `Intent` JSON, and the default output is terminal stdout/stderr.

