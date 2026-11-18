# CI Quality Gate (S4-06)

**Owner:** Berat İnan (Testing & QA Agent — `deepseek-coder:6.7b`)
**Workflow:** [`.github/workflows/tests.yml`](../.github/workflows/tests.yml)

## What runs

| Trigger | Jobs |
| :--- | :--- |
| Every Pull Request (any target branch) | `unittest (Python 3.11)`, `unittest (Python 3.13)`, `CI Gate` |
| Push to `main` | same |
| Manual (`workflow_dispatch`) | same |

Each `unittest` job:
1. installs `requirements.txt`,
2. byte-compiles `src`, `master_agent_projesi`, `scripts`, `tests` (`compileall`) so a syntax error fails the build even in an untested module,
3. runs the whole suite: `python -m unittest discover -s tests -v`.

`CI Gate` needs both matrix jobs and fails unless all of them succeeded. It is the
single check to mark as required, so the rule keeps working if the Python matrix changes.

## No live model, key or network

The suite must pass on a clean runner:

- `OLLAMA_HOST=http://127.0.0.1:9` (closed port) and `OLLAMA_TIMEOUT=2`: a test that
  accidentally calls a real model fails fast instead of hanging.
- `GEMINI_API_KEY=""`, `RUN_OLLAMA_SMOKE=0`: cloud checks and live Ollama smoke tests are skipped.
- Model calls are mocked (`llm_client=` injection, `unittest.mock.patch`), worker agents are
  test doubles or run with `use_ollama=False`, SQLite and workspaces use temporary directories.
- The workflow uses no `secrets.*` and runs with `permissions: contents: read`.

`tests/test_s4_ci_quality_gate.py` checks these properties, so removing the PR trigger,
adding `continue-on-error: true` or `|| true`, or dropping the gate job fails the suite itself.

## Making a failing test block the merge

GitHub only blocks the merge button when the check is required on the branch. A repository
admin does this once:

1. **Settings → Branches → Add branch protection rule** (or **Rules → Rulesets**) for `main`.
2. Enable **Require a pull request before merging**.
3. Enable **Require status checks to pass before merging** and **Require branches to be up to date**.
4. Search for and add **`CI Gate`** (it appears after the workflow has run once on a PR).
5. Optionally enable **Do not allow bypassing the above settings**.

## Running locally

```bash
python -m unittest discover -s tests -v
```

Same environment as CI (PowerShell):

```powershell
$env:OLLAMA_HOST="http://127.0.0.1:9"; $env:GEMINI_API_KEY=""; python -m unittest discover -s tests -v
```

Manual connectivity check (not part of the suite): `python master_agent_projesi/test_api.py`
prints which model backends are reachable and never prints the key.

## Sprint 4 test modules

| Module | Covers |
| :--- | :--- |
| `tests/test_s4_failover_and_conflicts.py` | Reassignment to the next best `IDLE` agent, unavailable agents skipped, unsafe output path counts as a failed attempt, honest `FAILED`, transitive `BLOCKED`, SQLite attempt history, file path conflicts and syntax review in the Integration Agent |
| `tests/test_s4_generated_code.py` | Runs the generated code: FastAPI backend through `TestClient`, SQL schema in in-memory SQLite (FK / UNIQUE / CHECK), HTML tag balance, executes a Testing Agent suite, validates every file a full pipeline writes to `workspaces/{run_id}/` |
| `tests/test_s4_ci_quality_gate.py` | Workflow gate properties and `master_agent_projesi/test_api.py` key hygiene |
