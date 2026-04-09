# agent-eval

Side-by-side evaluation system for AI coding agents. Runs the same coding tasks across multiple agents (Claude Code, Codex, LangGraph) and produces a structured comparison report.

---

## Prerequisites

- Python 3.11+
- [Claude Code CLI](https://claude.ai/code) installed and authenticated (`claude` on PATH)
- [Codex CLI](https://github.com/openai/codex) installed and authenticated (`codex` on PATH)

---

## Setup

```bash
# Clone and enter the project
cd agent-eval

# Create and activate a project-local virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Smoke Test

Verify the pipeline works end-to-end with a single task:

```bash
# Run one task against both agents (1 run each)
python cli.py run \
  --task datasets/tasks/example_fix_bug.json \
  --agents claude-code,codex \
  --runs 1

# Generate a report from the results
python cli.py report --input-dir results/ --output report.md

cat report.md
```

Expected output:
- Both agents should `PASS` the `fix-off-by-one` task
- `claude-code` typically finishes in ~7s with 3 turns
- `codex` typically finishes in ~15–20s with 1 turn
- Token counts and cost will be populated for Claude Code; cost will be `N/A` for Codex (not exposed by CLI)

---

## Full Batch Run

Run all 9 tasks across both agents:

```bash
python cli.py batch \
  --agents claude-code,codex \
  --runs 1

# Results land in results/batch_YYYYMMDD_HHMMSS/
# The command prints the exact path and a report command at the end
```

To run 3 times per task (recommended for stability measurement):

```bash
python cli.py batch --agents claude-code,codex --runs 3
```

---

## Generate a Report

```bash
# Markdown (default)
python cli.py report \
  --input-dir results/batch_YYYYMMDD_HHMMSS \
  --output report.md

# JSON (machine-readable)
python cli.py report \
  --input-dir results/batch_YYYYMMDD_HHMMSS \
  --output report.json
```

---

## Project Structure

```
agent-eval/
├── cli.py                        # Entry point: run / batch / report commands
├── core/
│   ├── schemas.py                # Shared data models (Task, Run, Trace, Metrics, Report)
│   ├── workspace.py              # Isolated workspace creation (temp dir per run)
│   ├── run_manager.py            # Orchestrates runs: workspace → agent → evaluator → persist
│   └── report.py                 # Aggregates runs into side-by-side report
├── agents/
│   ├── base.py                   # AgentAdapter interface
│   ├── claude_code.py            # Claude Code CLI adapter (stream-json trace)
│   ├── codex.py                  # Codex CLI adapter (JSONL trace)
│   └── langgraph_agent.py        # LangGraph adapter stub (P1)
├── evaluators/
│   ├── base.py                   # Evaluator interface
│   └── coding.py                 # Deterministic coding validators
├── datasets/
│   ├── tasks/                    # Task JSON definitions
│   └── fixtures/                 # Per-task workspace snapshots (buggy code + tests)
└── results/                      # Run outputs (gitignored)
    └── batch_YYYYMMDD_HHMMSS/
        ├── manifest.json
        └── <task>__<agent>__<run-id>.json
```

---

## Adding a New Task

1. **Create the fixture** under `datasets/fixtures/<task-id>/`:
   - `solution.py` — starting state (broken, incomplete, or stub)
   - `test_solution.py` — pytest tests that must pass after the agent fixes it

2. **Create the task JSON** at `datasets/tasks/<task-id>.json`:
   ```json
   {
     "id": "your-task-id",
     "description": "What you tell the agent — be specific and unambiguous",
     "workspace": "datasets/fixtures/your-task-id",
     "validator": {
       "type": "tests_pass",
       "config": { "command": "python -m pytest test_solution.py -v", "timeout_seconds": 30 }
     },
     "timeout_seconds": 120,
     "metadata": { "difficulty": "easy", "category": "bug-fix", "language": "python" }
   }
   ```

3. **Verify the fixture fails before the agent touches it:**
   ```bash
   .venv/bin/python -m pytest datasets/fixtures/your-task-id/test_solution.py -q
   # Must FAIL — if it passes, the task is trivially solved already
   ```

**Validator types:** `tests_pass` · `output_match` · `file_changed` · `script`

---

## Available Agents

| Agent ID | Backend | Tokens | Cost |
|----------|---------|--------|------|
| `claude-code` | `claude --output-format stream-json` | ✅ | ✅ |
| `codex` | `codex exec --full-auto --json` | ✅ | N/A |
| `langgraph` | Custom LangGraph agent (P1 stub) | TBD | TBD |
