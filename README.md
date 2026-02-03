# Nucleus

**Nucleus** is a **plan-first execution runtime** for human–AI collaboration.

It turns human intent into **safe, deterministic actions** through a strict pipeline:

> **Intent → Plan → Act → Trace**

Nucleus is not an app.  
It is a **runtime framework** that other people can safely build on.

---

## Why Nucleus exists

Modern AI tools are good at *deciding* what to do,  
but dangerous at *directly doing* things.

Nucleus exists to answer a simple question:

> **How can AI assist execution without breaking safety, trust, or auditability?**

Nucleus solves this by enforcing:
- explicit intent
- executable plans
- deterministic tools
- guardrails and rollback
- full traceability

---

## Core Principles

### 1. Plan-first execution
Nothing runs without a plan.

Every action must be expressed as a **Plan** that can be:
- inspected
- confirmed
- dry-run
- rejected

AI never executes blindly.

---

### 2. Deterministic tools only
AI does **not** run arbitrary shell commands.

All side effects go through **registered tools** with:
- declared inputs/outputs
- known side effects
- optional dry-run support

This makes execution predictable and testable.

---

### 3. Explicit scope and permissions
Every Plan declares:
- what resources it touches
- where it is allowed to act
- what level of risk it carries

Nothing happens outside the declared scope.

---

### 4. Safety by default
Nucleus enforces safety as a *framework invariant*:

- no delete by default
- staging before mutation
- rollback paths when possible
- confirmation gating by policy
- full execution trace

Safety is not a plugin feature.  
It is the core contract.

---

### 5. Trace everything
Every run produces an auditable event stream.

You can:
- inspect what happened
- understand why it happened
- replay or debug executions
- prove what was (and wasn’t) done

---

## Architecture Overview

Nucleus is structured around four layers:

[ UI Adapters ]
↓
[ Intent / Plan ]
↓
[ Nucleus Kernel ]
↓
[ Deterministic Tools ]


### Kernel
The Nucleus kernel orchestrates:
- intent routing
- plan generation
- policy evaluation
- execution control
- trace emission

### Plugins
Plugins define *what* to do, not *how* to execute.

A plugin:
- declares supported intents
- generates Plans
- selects tools
- follows core contracts

### Tools
Tools are the only way to affect the real world:
- filesystem
- applications
- external services

They are deterministic, testable, and auditable.

### UI Adapters
UI is an adapter — not the core.

Input and output can be:
- CLI
- Alfred
- notifications
- dashboards
- chat interfaces

The runtime stays the same.

---

## What Nucleus is NOT

- ❌ Not an AI agent that directly controls your system
- ❌ Not a chatbot with shell access
- ❌ Not an app-specific automation script
- ❌ Not a UI framework

Nucleus is a **runtime for controlled execution**.

---

## Repository Structure (high-level)

nucleus/
├─ nucleus/ # Runtime kernel
├─ contracts/ # Public execution contracts (schemas)
├─ specs/ # Spec-driven design (framework + plugins)
├─ plugins/ # Plugin implementations
├─ tools/ # Deterministic execution tools
├─ ui_adapters/ # Input/output adapters
├─ tests/ # Contract + runtime + plugin tests
└─ examples/ # Sample intents, plans, traces


### Spec-driven development
All development starts from **specs/**:
- framework specs define invariants
- plugin specs define behavior
- contracts define the public API

Code follows specs — never the other way around.

---

## Example: Desktop tidy (builtin plugin)

Nucleus ships with a reference plugin:

**builtin.desktop**

It demonstrates:
- intent-based execution (`desktop.tidy`)
- plan-first behavior
- staging and rollback
- safe filesystem operations
- notification-based UI

This plugin exists to show *how plugins should be built*,  
not as the final product.

---

## Who is this for?

Nucleus is for people who want to:

- build AI-assisted automation **without losing control**
- design human-in-the-loop systems
- create safe execution layers for LLMs
- build extensible runtimes, not one-off scripts
- treat safety and auditability as first-class features

Typical users:
- platform / staff engineers
- automation system designers
- AI tool builders
- teams working on human–AI workflows

---

## Status

Nucleus is currently **early-stage (v0.1)**.

APIs may evolve, but the core principles are stable:
- plan-first
- deterministic execution
- safety invariants
- traceability

Breaking changes to public contracts are explicitly versioned.

---

## Contributing

Contributions are welcome, but **structure matters**.

Please read:
- `specs/framework/INDEX.md` (framework rules)
- `specs/plugins/*/INDEX.md` (plugin rules)

In short:
- framework changes require ADRs
- plugins must obey core contracts
- safety rules are non-negotiable

---

## License

MIT License  
(see `LICENSE`)

---

## Philosophy (one line)

> **Nucleus externalizes execution control,  
> so humans and AI can collaborate without accidents.**

