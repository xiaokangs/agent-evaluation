# Feature requests

Improvements proposed by fleet's product review and approved on the dashboard. Newest last; delete or mark them when done.

Evidence files named below (`.fleet-product/...`) were captured by the fleet product review and are **not committed to this repo**; each entry states the reproduction steps inline so it can be checked without them.

## Grade submitted code against pristine tests outside the agent workspace

- Date: 2026-11-14 · Type: Bug · Priority: P0 · Source: fleet product review

**Problem**: An agent can receive PASS without fixing the task by replacing test_solution.py with an always-passing test. This undermines the comparison's central correctness metric.

**Proposal**: Separate editable inputs from grading assets. Verify declared output files in a fresh grading environment containing pristine tests and runner configuration; exclude agent-written test configuration and hooks. Record grading-file hashes and flag prohibited modifications. Acceptance check: the reproduced test-replacement attempt must fail while a genuine solution passes.

**Evidence**: The offline tampering run left solution.py broken, replaced its tests, and received PASS (reproduce: in a workspace for any `tests_pass` task, leave `solution.py` unfixed and overwrite `test_solution.py` with `def test_ok(): assert True`, then run the validator); see .fleet-product/tampered-tests.txt and validator-probes.json. core/workspace.py copies tests into the editable workspace, and evaluators/coding.py runs them there. [Harbor documents separate verification](https://docs.harborframework.com/tasks/separate-verifier).

## Make validators enforce command success and actual file changes

- Date: 2026-11-14 · Type: Bug · Priority: P1 · Source: fleet product review

**Problem**: output_match accepts expected stdout even when the command exits with an error. file_changed accepts an untouched existing file, so custom tasks can report success without successful execution or any edit.

**Proposal**: Require exit code zero alongside matching output, and retain exit code and stderr in validation details. Capture file hashes before agent execution and compare afterward for file_changed; distinguish creation, modification, and unchanged files. If presence-only validation is useful, expose it as a separately named validator.

**Evidence**: Direct probes reproduced PASS for `printf expected; exit 9` and for the original unchanged solution.py. Results are in .fleet-product/validator-probes.json; implementations are CodingEvaluator._output_match and _file_changed in evaluators/coding.py.


## Preserve batch state and resume after individual execution failures

- Date: 2026-11-14 · Type: Bug · Priority: P1 · Source: fleet product review

**Problem**: Selecting LangGraph aborts the batch after earlier results have been saved, leaving no manifest. Missing CLIs and validator timeouts also escape execution, preventing remaining evaluations from running.

**Proposal**: Preflight selected backends and reject unimplemented adapters before starting. Write the planned run matrix to a manifest immediately, update it atomically after every attempt, and persist structured errors with execution phase and diagnostics. Catch adapter, setup, and validation failures per run; bound setup duration. Add resume support that skips completed attempts and explicitly selects failed attempts for retry.

**Evidence**: .fleet-product/interrupted-batch.txt and batches/offline-interrupted/ (a custom output location: `python cli.py batch --agents <working-agent>,langgraph --output-dir batches --batch-id offline-interrupted`; the default would be results/batch_<timestamp>/) show one saved result without manifest.json. missing-cli.txt (an agent whose CLI is not on PATH) shows an uncaught RuntimeError; validator-timeout.txt records TimeoutExpired. Relevant paths: cli.py, core/run_manager.py, core/workspace.py. [Inspect preserves completed samples for retries](https://inspect.aisi.org.uk/handling-errors.html).


## Expose experiment configuration and save enough provenance to reproduce it

- Date: 2026-11-14 · Type: Feature · Priority: P1 · Source: fleet product review

**Problem**: CLI users cannot select models even though adapters accept them. Saved runs identify the backend but omit the resolved model, CLI version, task snapshot, and fixture fingerprint, making later comparisons difficult to reproduce.

**Proposal**: Add an experiment configuration file with named agent variants, model selections, adapter options, task selection, and repetitions. Persist the resolved configuration, available model identity, CLI/package versions, task definition, and fixture/grader hashes with every batch. Mark unknown model identity explicitly and include variant labels and provenance in reports.

**Evidence**: cli.py constructs default adapters without exposing their model arguments. core/schemas.py and the batch manifest contain no experiment configuration or dataset fingerprint. [Harbor supports reusable job configurations with model selection](https://docs.harborframework.com/jobs/configs).


## Link report failures to retained patches and complete diagnostics

- Date: 2026-11-14 · Type: UX · Priority: P1 · Source: fleet product review

**Problem**: The report reduces failures to messages such as 'tests failed (exit 2)'. Default cleanup removes the edited workspace, artifacts remain empty, and users must locate individual JSON files to understand what happened.

**Proposal**: Before cleanup, save a bounded patch, raw backend output, and complete validator stdout/stderr under each run ID. Add report links to these artifacts and show execution status separately from validation outcome. Provide a local `inspect <run-id>` command that displays the failing test, patch, and relevant trace events.

**Evidence**: .fleet-product/batch-report.md (output of `python cli.py report --input-dir <batch-dir>`) shows generic failure reasons. Tampering-run artifacts are empty and its workspace was deleted. core/report.py truncates failure reasons; core/run_manager.py saves no patch before workspace cleanup. [Harbor collects per-trial artifacts](https://docs.harborframework.com/jobs/artifact-collection).


## Add a representative multi-file evaluation suite with uncertainty reporting

- Date: 2026-11-14 · Type: Feature · Priority: P1 · Source: fleet product review

**Problem**: All nine fixtures contain only solution.py and test_solution.py; seven tasks are labeled easy and two medium. This exercises the pipeline but offers limited evidence for choosing agents for repository-scale work, while percentage-only reports obscure small sample sizes.

**Proposal**: Keep the current tasks as a smoke suite and add a separately named selection suite covering cross-file debugging, API-compatible refactoring, dependency/configuration changes, and recovery from failing integration tests. Validate every fixture with a failing baseline and passing reference patch. Report category-level results, pass counts, and uncertainty across tasks and repeated runs.

**Evidence**: datasets/tasks and datasets/fixtures establish the limited task scope. core/report.py presents pass percentages and means without uncertainty. CLAUDE.md already targets representative scenarios; this makes that goal testable. [Inspect provides standard-error and confidence-interval metrics](https://inspect.aisi.org.uk/metrics.html).
