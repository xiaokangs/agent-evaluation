# Feature requests

Improvements proposed by fleet's product review and approved on the dashboard. Newest last; delete or mark them when done.

## Grade submitted code against pristine tests outside the agent workspace

- Date: 2026-11-14 · Type: Bug · Priority: P0 · Source: fleet product review

**Problem**: An agent can receive PASS without fixing the task by replacing test_solution.py with an always-passing test. This undermines the comparison's central correctness metric.

**Proposal**: Separate editable inputs from grading assets. Verify declared output files in a fresh grading environment containing pristine tests and runner configuration; exclude agent-written test configuration and hooks. Record grading-file hashes and flag prohibited modifications. Acceptance check: the reproduced test-replacement attempt must fail while a genuine solution passes.

**Evidence**: The offline tampering run left solution.py broken, replaced its tests, and received PASS; see .fleet-product/tampered-tests.txt and validator-probes.json. core/workspace.py copies tests into the editable workspace, and evaluators/coding.py runs them there. [Harbor documents separate verification](https://docs.harborframework.com/tasks/separate-verifier).
