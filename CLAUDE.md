# CLAUDE.md

## Project: Agent Evaluation Side-by-Side Comparison

### Project Goal

This project builds a side-by-side evaluation system for comparing multiple AI agents on the same task set, with an initial focus on coding workflows.

The purpose of this project is to make agent behavior measurable and comparable, not just anecdotal.

The system should answer questions such as:

- Did the agent complete the task successfully?
- How long did it take?
- How many turns did it require?
- How many tokens and how much cost did it consume?
- How stable was it across repeated runs?
- How different were the traces and tool-use patterns across agents?

This project is not a general-purpose autonomous agent framework.
It is not a prompt playground.
It is not a benchmark paper reproduction project.
It is an evaluation system.

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

Phase 1 of this project focuses on:

- side-by-side comparison of coding agents
- task execution in isolated workspaces
- collection of trace and runtime metadata
- evaluation of outcome, efficiency, and stability
- generation of per-task and aggregate reports

The first supported agents may include:

- Claude Code
- Codex or Codex-like execution path
- other agent backends only if they can be instrumented with enough fidelity

If different agents expose different internal details, the system should normalize what is observable instead of pretending all traces are equivalent.

---

## Non-Goals

Do not turn this into any of the following during P0:

- a generic agent orchestration framework
- a universal benchmark for every AI workload
- a RAG evaluation platform
- a browser automation evaluation platform
- a SaaS product
- a leaderboard website
- a research paper engine
- a full judge model platform
- an autonomous self-improving agent system

Those may come later. Not now.

---

## Architectural Direction

This system should be designed as:

- a shared evaluation core
- workload-specific task adapters
- agent-specific runner adapters
- task-specific evaluators
- a reporting layer

The correct mental model is:

Task -> Runner -> Agent Adapter -> Trace Collector -> Evaluator -> Report

We are not trying to access each agent's true internal reasoning.
We are collecting a normalized external execution trace that is sufficient for comparison.

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
- turn count
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

## P1 Features (Should Have)

P1 adds evaluation depth and practical usability.

### P1.1 Stability metrics
Compute multi-run metrics such as:

- success rate
- mean duration
- mean token usage
- variance / standard deviation
- cost distribution

### P1.2 Richer trace model
Add support for normalized events such as:

- command execution
- diff summary
- retry loops
- dead-end patterns
- validation attempts
- error recovery behavior

### P1.3 Trace-derived metrics
Add metrics such as:

- retries before success
- number of validation cycles
- number of file modifications
- command count
- ratio of productive vs failed tool actions

### P1.4 Dataset management
Support a structured task dataset organization for coding tasks.

Include:

- task metadata
- difficulty tags
- category tags
- repo snapshot or setup script
- validator configuration

### P1.5 Aggregated summaries
Generate aggregate views by:

- agent
- task category
- difficulty tier
- repo type

### P1.6 Better reporting outputs
Support machine-readable and human-readable output:

- JSON
- Markdown
- CSV

### P1.7 Configurable evaluation policy
Support configurable timeouts, retry limits, and cost ceilings per run.

### P1.8 Partial credit model
For tasks where binary success is too coarse, allow structured partial scoring.
This must still be explicit and deterministic where possible.

---

## P2 Features (Nice to Have / Strategic)

P2 is where the system becomes platform-like, but only after P0 and P1 are solid.

### P2.1 Workload expansion
Add additional workload types, such as:

- RAG QA
- browser agent tasks
- API workflow tasks

This should extend the shared core, not distort it.

### P2.2 Judge-assisted evaluation
Use model-based judges only for dimensions that are difficult to validate deterministically, such as:

- code quality
- explanation quality
- groundedness for non-coding tasks

Judge output must be clearly labeled as judge-based, not objective truth.

### P2.3 Cost-performance frontier analysis
Compare agents not just by raw success, but by:

- success per dollar
- success per minute
- stability-adjusted efficiency

### P2.4 Historical tracking
Store historical run results to support:

- regression detection
- version-to-version comparison
- trend analysis over time

### P2.5 Visualization layer
Build charts for:

- success distributions
- token / cost scatter
- per-task breakdown
- efficiency frontiers

### P2.6 Multi-agent orchestration evaluation
Evaluate orchestrated agent systems, not just single agents.

### P2.7 External leaderboard or publishable benchmark
Only after the methodology is stable and credible.

---

## High-Level Design

### 1. Core Concepts

The system should define the following core concepts:

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
- artifacts
- metrics
- validation result

#### Evaluator
Computes scores and metrics from run outputs.

There should be:

- objective evaluators
- optional judge-assisted evaluators later

#### Report
Aggregates results into side-by-side comparisons.

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

- `workloads/`
  - coding task support first
  - future RAG or browser support later

- `evaluators/`
  - coding validators
  - trace metrics
  - aggregate evaluators

- `datasets/`
  - task definitions
  - fixtures
  - setup assets

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

Trace quality matters, but trace comparability is approximate.

That is acceptable.

The system should explicitly distinguish between:

- raw backend trace
- normalized trace
- derived metrics

---

### 4. Evaluation Philosophy

The evaluation stack should prioritize:

1. objective correctness
2. efficiency
3. stability
4. process quality

The system should avoid subjective scoring unless unavoidable.

For coding tasks, the gold standard is:

- deterministic validation
- repeated runs
- transparent metrics

---

### 5. Design Constraints

When implementing this project, follow these constraints:

- Keep the core workload-agnostic, but do not generalize prematurely
- P0 must focus on coding tasks only
- Avoid framework bloat
- Avoid adding a database before needed
- Prefer local files and structured JSON for early stages
- Keep every run reproducible and inspectable
- Make failure modes visible
- Do not hide missing metrics behind fake normalization
- If one agent exposes less telemetry, mark fields as unavailable instead of inventing equivalents

---

## Implementation Guidance for Claude

When working in this repository:

- prioritize P0 completion before adding P1 or P2 ideas
- make the vertical path work end-to-end
- prefer explicit schemas over clever abstractions
- keep adapters small and backend-specific
- keep evaluators deterministic where possible
- do not mix workload-specific logic into the shared core
- do not add RAG abstractions until coding workflow evaluation is stable
- do not optimize for elegance at the cost of observability

When making architecture decisions:

- prefer boring over fancy
- prefer inspectable over magical
- prefer measurable over aspirational

When making frontend design and implementation:

- use DESIGN.md at the project folder and light theme

---

## Suggested P0 Deliverable

The first credible milestone should be:

- 2 coding agents
- start coding agents with Claude Code and Codex
- 5 to 10 coding tasks
- isolated runs
- deterministic validation
- repeated runs
- side-by-side comparison report

This is the minimum version that can produce useful insight and serve as a public demo.

---

## One-Line Product Definition

This project is a side-by-side evaluation system for AI agents, designed to make task completion, cost, speed, and trace behavior measurable across agents solving the same work.
