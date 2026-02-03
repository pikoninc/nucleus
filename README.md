# Nucleus

Nucleus is a spec-driven, AI-augmented runtime framework designed to safely integrate large language models (LLMs) into real software systems by strictly separating thinking from execution.

It enables developers to use AI for understanding, structuring, and proposing actions—
while guaranteeing that all execution remains deterministic, auditable, and under human control.

## What Problem Nucleus Solves

Modern AI systems are excellent at reasoning, but unsafe when allowed to execute directly:

- Non-deterministic behavior
- Hidden state in conversation logs
- Irreversible side effects
- Poor auditability
- Fragile collaboration between humans and AI agents

Nucleus addresses this by enforcing a simple but strict rule:

AI may think and propose.  
Only the runtime may execute.

## What Nucleus Is

Nucleus is:

- A runtime architecture, not an autonomous agent
- A spec-first framework, not prompt-driven automation
- A foundation for human–AI collaboration with guarantees
- A system where execution is deterministic and inspectable

It is designed for engineers who want to use AI seriously—
without sacrificing safety, reproducibility, or clarity.

## What Nucleus Is Not

Nucleus is not:

- A fully autonomous AI agent
- A system where LLMs execute OS or infrastructure commands
- A workflow engine where chat logs define state
- A black-box automation tool

If you want AI to “just run things,” this framework is intentionally not that.

## Core Principles

### 1. Separation of Thinking and Execution

Nucleus strictly separates responsibilities:

**Thinking**

- Intent understanding
- Classification
- Structuring
- Proposals

Performed by humans and LLMs

**Execution**

- Actual operations
- Side effects
- State changes

Performed only by a deterministic runtime

LLMs never execute.  
The runtime never reasons.

### 2. Specification as the Source of Truth

Specifications (Specs) are the center of the system:

- Specs define what should happen and what is allowed
- Specs are shared language between humans and AI
- Specs are authoritative over code and conversations

Conversation logs are context, never system state.

### 3. Deterministic Execution

- No LLMs are used during execution
- Same input + same config → same result
- All side effects go through explicit tools
- Execution is traceable and designed for rollback

This makes Nucleus suitable for production-grade systems.

## High-Level Architecture

```text
User / UI
   ↓
Input Intake (LLM)
   ↓   IntentEnvelope
Processing Unit
   ↓
Studio (LLM)
   ↓   Manifest / Config Patch
Planner / Compiler
   ↓   Execution Plan
Executor (Deterministic)
   ↓
Tools + Trace
```

Nucleus provides this structure as a set of clearly separated layers.

## Core Components and Responsibilities

### Input Intake

Role

- Accept natural language input
- Tolerate ambiguity and incomplete intent
- Normalize input into a structured IntentEnvelope

Constraints

- No execution
- No side effects
- No configuration commitment

Input Intake is the system’s entry point and intent clarifier.

### Processing Units

A processing unit is a domain-aware component that behaves according to a spec.

Nucleus supports two forms of processing units with the same underlying structure.

#### Application (App)

An App represents an application-level processing unit.

Responsibilities

- Acts as the initial entry point for user intent
- Receives IntentEnvelope from Input Intake
- Decides how the intent should be handled
- May execute its own domain logic directly
- May delegate or compose other processing units

An App can operate entirely on its own  
or act as an integrator of other units.

#### Plugin

A Plugin is a domain-focused processing unit.

Responsibilities

- Encapsulates rules and behavior of a specific domain
- Uses declarative manifests and schemas where possible
- Is designed to be reused across multiple Apps

Plugins are optional.  
They are included only when an App chooses to use them.

#### Relationship Between Apps and Plugins

- Apps and Plugins share the same structural model
- Plugins do not require Apps to exist conceptually
- Apps may use zero, one, or many Plugins
- The difference lies in responsibility, not structure

This symmetry allows Nucleus to scale from minimal setups to complex systems without changing its mental model.

### Studio

Role

- Collaborate with AI to generate or update configuration
- Produce only diffs or patches, never execution
- Keep all changes human-reviewable

Constraints

- No execution
- No tool access
- No irreversible decisions

### Planner / Compiler

Role

- Convert manifests into executable plans
- Apply policies and safety constraints
- Generate previews and dry runs

### Executor

Role

- Execute plans exactly as defined
- Invoke tools in a controlled manner
- Record execution traces

Constraints

- No AI usage
- No interpretation or decision-making

### Tools

- The only source of side effects
- Explicitly declare capabilities and risks
- Callable only from the Executor

## Spec-Driven Development and AI Operations

Development and operations in Nucleus follow a consistent lifecycle:

Spec → Plan → Task → Implementation → Status

- Spec defines intent and constraints
- Plan proposes how to fulfill the spec
- Task represents the current state of work
- Conversation logs are contextual only

An AI operations workspace supports this process while keeping system state explicit and auditable.

## Safety Model

- AI never executes actions
- Execution paths are deterministic
- All side effects go through tools
- Preview and rollback are first-class concepts

## Intended Use Cases (Abstract)

Nucleus is suitable for building:

- AI-assisted applications with strict safety guarantees
- Systems that translate ambiguous human intent into structured action
- Spec-driven internal tools and products
- Human–AI collaborative workflows
- Adaptive assistants with controlled execution

## Summary

Nucleus is a framework where:

- Humans decide
- AI proposes
- Specifications define truth
- The runtime executes deterministically

Apps and Plugins are expressions of this philosophy—not the philosophy itself.

Nucleus exists to make AI-assisted systems reliable, understandable, and safe.

