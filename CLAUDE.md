# CLAUDE.md

## Project: Agent Evaluation Side-by-Side Comparison

### Project Goal

This project builds a side-by-side evaluation system for comparing multiple AI agents on the same task set, with an initial focus on coding workflows.

The purpose of this project is to make agent behavior measurable and comparable, not just anecdotal.

The system should answer questions such as:

- Did the agent complete the task successfully?
- How long did it take?
- How many turns or execution steps did it require?
- How many tokens and how much cost did it consume?
- How stable was it across repeated runs?
- What failure modes occurred?
- How did observability differ across agent architectures?

This project is not a general-purpose autonomous agent framework.
It is an evaluation system for measuring agent reliability, efficiency, and trace behavior across implementations.

The first product goal is to produce a credible and repeatable comparison report for multiple agents solving the same coding tasks.

---

## Product Principles

- Correctness over flashy demos
- Comparable runs over agent-specific magic
- Explicit trace capture over vague impressions
- Repeatability over one-off wins
- Minimal but extensible architecture
- Start vertical, not abstract
- No premature generalization into a universal evaluation platform

---

## Initial Scope

Phase 1 focuses on side-by-side comparison of coding agents.

Supported categories may include:

- productized coding agents (for example Claude Code, Codex-like runners)
- custom orchestrated agents (for example LangGraph-based agents)
- future MCP-compatible tool-wrapped agents

The system should compare not only task outcome, but also observability quality and failure behavior across architectures.

---

## Non-Goals

Do not turn this into any of the following during P0/P1:

- a generic agent orchestration framework
- a universal benchmark for every AI workload
- a full RAG evaluation platform
- a browser automation platform
- a SaaS product
- a public leaderboard website

Those may come later. Not now.

---

## Architectural Direction

This system should be designed as:

- a shared evaluation core
- workload-specific task adapters
- agent-specific runner adapters
- task-specific evaluators
- a reporting layer
- a historical results layer later

The correct mental model is:

Task -> Runner -> Agent Adapter -> Trace Collector -> Evaluator -> Report -> Historical Store

We are not trying to access each agent's true internal reasoning.
We are collecting normalized, observable execution traces that are sufficient for comparison.

---

## P0 Features (Must Have)

P0 is the minimum credible system.

### P0.1 Task definition
Support a structured coding task format that includes:

- task id
- task description
- repo or workspace input
- expected validation method
- optional timeout
- optional setup instructions

### P0.2 Agent adapters
Provide a pluggable adapter interface for at least 2 agents.

Each adapter must support:

- task execution
- collection of observable trace events
- collection of runtime metadata
- capture of final artifacts or workspace state

### P0.3 Run isolation
Each run must execute in an isolated workspace.

Rules:

- no cross-run contamination
- no shared mutable task state
- no hidden reuse of previous outputs unless explicitly configured

### P0.4 Trace collection
Capture a normalized trace schema including at least:

- timestamps
- assistant/user-visible messages if available
- tool or command events if available
- file edit events if available
- run start / end markers
- failure / timeout markers

### P0.5 Core metrics
Compute at minimum:

- success / failure
- wall clock duration
- turn count if available
- token usage if available
- estimated cost if available
- tool call count if available

### P0.6 Outcome validation
For coding tasks, the primary validator should be objective.

Examples:

- tests pass
- expected output produced
- required file changed correctly

Do not rely on an LLM judge for P0 success criteria unless there is no deterministic validator.

### P0.7 Side-by-side reporting
Generate a report that compares all agents on:

- task outcome
- duration
- turns
- token usage
- cost
- trace summary

### P0.8 Repeatable runs
Support repeated execution of the same agent on the same task.

Minimum requirement:

- configurable run count per agent per task

This is needed because agent performance is stochastic.

---

## P1 Features (Resume-Strengthening Features)

P1 should transform this from a runnable prototype into a credible evaluation framework.

### P1.1 Scenario-driven task dataset
Support a structured dataset of coding scenarios with metadata such as:

- task category
- difficulty tier
- expected tool usage profile
- required repo context depth
- validator type

The system should support at least 10 to 20 representative coding scenarios, not just toy tasks.

### P1.2 Failure taxonomy
Implement structured failure-mode classification for unsuccessful or degraded runs.

Examples:

- timeout
- invalid edit target
- incomplete implementation
- failed validation ignored
- excessive retry loop
- tool misuse
- hallucinated command or API
- partial completion

Failure analysis must be stored as structured data, not only free-text notes.

### P1.3 Step-derived metrics
Compute metrics derived from trace behavior, such as:

- retry count
- number of validation attempts
- number of file modifications
- command count
- failed tool-action count
- dead-end step count
- edit-to-validation ratio

These should be reported separately from outcome metrics.

### P1.4 Richer trace normalization
Improve trace capture and normalization to distinguish between:

- raw backend trace
- normalized event trace
- derived behavioral metrics

The system must not treat missing telemetry as zero.
Unavailable fields must be marked explicitly as unavailable.

### P1.5 Aggregate reporting
Generate aggregate comparison reports by:

- agent
- task category
- difficulty tier
- run index
- repeated-run summary

Reports should surface patterns, not only per-run details.

### P1.6 Architecture comparison support
Support comparison between at least:

- one productized coding agent
- one custom orchestrated agent implementation

A LangGraph-based coding agent is a valid P1 target for architecture-level comparison.

The project should explicitly compare:

- reliability
- observability
- trace richness
- recovery behavior
- cost-efficiency

### P1.7 Reproducible scoring rubric
Define an explicit scoring rubric for coding tasks that separates:

- objective correctness
- efficiency
- trace quality
- failure severity

The rubric must be reproducible and inspectable.

### P1.8 Batch execution workflow
Support batch execution of scenario suites across multiple agents and multiple runs.

Example:

- 10 tasks
- 3 runs per task
- 3 agent backends

This should produce a consistent evaluation artifact set.

---

## P2 Features (Strategic / Platform-Oriented)

P2 extends the system into a more durable evaluation platform.

### P2.1 Historical run storage
Persist runs, trace summaries, metrics, and validation outcomes in a database-backed store.

The first database target should be simple and pragmatic, such as:

- SQLite for local development
- Postgres for future scaling

The storage layer should support:

- querying by task
- querying by agent
- querying by time range
- querying by outcome or failure type

### P2.2 Regression detection
Implement historical comparison workflows that identify regressions in:

- success rate
- latency
- token usage
- cost
- failure distribution
- trace-derived metrics
- tool selection behavior

The system should support before/after comparisons across agent versions or workflow revisions.

### P2.3 Versioned agent and task metadata
Store versioned metadata for:

- agent backend version
- prompt or policy version
- tool configuration
- task version
- validator version

This is required for trustworthy regression analysis.

### P2.4 Database-backed analytics layer
Add an analytics layer over stored runs for:

- aggregate summaries
- trend analysis
- failure clustering
- agent-vs-agent comparisons over time

### P2.5 Support for custom orchestrated architectures
Expand support for additional orchestrated agents beyond LangGraph, including:

- MCP-compatible tool integrations
- planner/executor split agents
- critic/retry loop architectures

### P2.6 Optional judge-assisted evaluation
Introduce model-based judges only for dimensions that are hard to validate deterministically, such as:

- code quality
- explanation quality
- maintainability heuristics

Judge-based scoring must always be labeled separately from objective scoring.

### P2.7 Visualization and dashboard layer
Once schemas stabilize, provide a lightweight dashboard or report viewer for exploring:

- run history
- aggregate comparisons
- regression trends
- failure-mode breakdowns

Dashboard work must come after the core data model and storage model stabilize.

---

## High-Level Design

### 1. Core Concepts

#### Task
A unit of work to be solved by an agent.

Fields may include:

- id
- type
- description
- setup config
- validator config
- metadata

#### Agent Adapter
A backend-specific execution wrapper.

Responsibilities:

- launch agent for a task
- pass task input
- capture observable outputs
- normalize trace
- return run result

#### Run
One execution of one agent on one task.

A run should contain:

- run metadata
- raw trace
- normalized trace
- derived metrics
- artifacts
- validation result
- failure classification

#### Evaluator
Computes scores and metrics from run outputs.

There should be:

- objective evaluators
- trace-derived evaluators
- optional judge-assisted evaluators later

#### Report
Aggregates results into side-by-side comparisons and repeated-run summaries.

#### Historical Store
Persists run-level and aggregate metadata for regression detection and analytics.

---

### 2. Recommended Layering

Recommended architecture:

- `core/`
  - shared schemas
  - run manager
  - trace model
  - metrics model
  - report generation

- `agents/`
  - one adapter per agent backend
  - one adapter for custom LangGraph agent runner

- `workloads/`
  - coding task support first
  - future RAG or browser support later

- `evaluators/`
  - coding validators
  - failure taxonomy classifier
  - trace metrics
  - aggregate evaluators

- `datasets/`
  - task definitions
  - fixtures
  - setup assets

- `storage/`
  - file-based run storage initially
  - database adapters later

- `reports/`
  - markdown/json/csv output

---

### 3. Trace Philosophy

Do not pretend we have access to an agent's real internal reasoning.

This system evaluates externalized behavior:

- visible steps
- tool usage
- commands
- edits
- timing
- final outcome

The system must distinguish between:

- raw backend trace
- normalized trace
- derived metrics
- unavailable telemetry

If two agents expose different telemetry granularity, compare them only on shared observable dimensions and label missing fields as unavailable, not zero.

---

### 4. Evaluation Philosophy

The evaluation stack should prioritize:

1. objective correctness
2. efficiency
3. stability
4. process quality
5. failure explainability

For coding tasks, the gold standard is:

- deterministic validation
- repeated runs
- transparent metrics
- structured failure analysis

---

### 5. Design Constraints

When implementing this project, follow these constraints:

- Keep the core workload-agnostic, but do not generalize prematurely
- P0 and P1 must focus on coding tasks first
- Avoid framework bloat
- Prefer explicit schemas over clever abstractions
- Make every run reproducible and inspectable
- Do not hide missing metrics behind fake normalization
- Prefer local file storage first, then introduce a database in P2
- Database adoption must improve regression analysis, not just look more enterprise

---

## Suggested P1 Deliverable

A credible P1 milestone should include:

- at least 2 to 3 agent backends
- one of them being a custom LangGraph-based agent
- 10 to 20 coding scenarios
- repeated runs
- deterministic validation
- failure taxonomy
- aggregate side-by-side reports
- trace normalization rules

---

## Suggested P2 Deliverable

A credible P2 milestone should include:

- historical run storage in SQLite or Postgres
- versioned metadata for agents and tasks
- regression detection reports
- trend analysis across repeated benchmarks
- architecture-level comparison across native and orchestrated agents

---

## One-Line Product Definition

This project is a side-by-side evaluation framework for AI agents, designed to measure correctness, efficiency, observability, and regression behavior across agent implementations and architectures.

