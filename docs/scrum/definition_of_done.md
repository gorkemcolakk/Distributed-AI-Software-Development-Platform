# Definition of Done (DoD)
## Distributed AI Software Development Platform (CM6453)

* **Version:** 2.1.0
* **Applicability:** All Sprints (Sprint 1 through Sprint 5)
* **Standard:** 2020 Scrum Guide Commitment for Product Increment
* **Audience:** Product Owner (Prof. Dr. Ensar Gül), Scrum Master (İrem Yılmaz), Developers

---

## 1. Principle & Commitment

In strict accordance with the **2020 Scrum Guide**, an Increment is born the moment a Product Backlog Item (PBI) meets the **Definition of Done**. 

> If a Product Backlog item does not meet the Definition of Done, it cannot be released or even presented at the Sprint Review. Instead, it returns to the Product Backlog for future consideration and re-estimation in subsequent sprint planning.

The Definition of Done serves as an uncompromised quality standard that applies identically across all five sprints of this project.

---

## 2. Quality Criteria Across All Sprints

### 2.1 Code Quality, Formatting & Repository Cleanliness
1. **Working Software:** The implementation must execute cleanly in the target runtime environment (Python 3.10+ / Streamlit / FastAPI) without unhandled exceptions or syntax errors.
2. **Branching & Pull Requests:** Direct commits to `main` are strictly prohibited. All development must take place on descriptive feature branches (`feature/<card-id>-<slug>`) and be integrated into `main` via formal Pull Requests (PRs).
3. **Repository Cleanliness:** No compiled bytecode (`__pycache__/`, `*.pyc`), virtual environments (`venv/`), local secret files (`.env`), or runtime database files (`state.db`) may be checked into Git. All temporary files must be shielded by [`.gitignore`](../../.gitignore).
4. **Code Standards & Hygiene:** Code must adhere to PEP 8 standards with descriptive naming, modular functions, and complete type annotations where appropriate.

### 2.2 Peer Review & Quality Assurance
1. **Peer Code Review:** Every PR must be reviewed and formally approved by at least one other developer in the *"Code Review & Testing"* stage before merging into `main`.
2. **Deterministic Automated Unit Testing:** All existing and newly authored unit tests must pass via:
   ```bash
   python -m unittest discover tests
   ```
   Tests must be completely deterministic and mock-based. Tests must **never** depend on an active internet connection, external network ports, or live cloud API keys.
3. **Integration Verification:** Inter-module workflows (such as Master Agent to SQLite persistence, or Orchestrator to Scheduler) must be verified through automated integration tests.
4. **Continuous Integration (CI) Quality Gate:** The GitHub Actions workflow ([`.github/workflows/tests.yml`](../../.github/workflows/tests.yml)) must report a green build on every PR. Any failing test blocks the merge unconditionally.

### 2.3 Architecture, Contracts & Safe Workspace Confinement
1. **Architectural Conformance:** Implemented modules must strictly adhere to the boundaries specified in [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) and the data schemas in [`docs/DATA_MODEL.md`](../DATA_MODEL.md).
2. **Contract Adherence:** Agent communication payloads must conform to the Pydantic schemas in [`src/contracts.py`](../../src/contracts.py) and specifications in [`docs/INTER_AGENT_CONTRACTS.md`](../INTER_AGENT_CONTRACTS.md). Any change requires an explicit version increment (e.g., `v1.0` -> `v1.1`).
3. **Workspace Confinement:** All file generation by worker agents must be physically restricted to `workspaces/{run_id}/`. Path traversal attempts (`../`) must be rejected automatically.
4. **Backward Compatibility:** New increments must preserve the functionality of existing CLI (`python -m src.master.orchestrator`) and web interface (`streamlit run master_agent_projesi/app.py`) entrypoints.

### 2.4 Error Handling & Status Integrity ("Never Silently COMPLETED")
1. **Resilient Exception Handling:** Network timeouts, missing API keys, corrupt model outputs, and malformed inputs must be trapped gracefully without crashing the UI or master orchestrator process.
2. **Truthful State Reporting:** A task that fails, times out, or cannot find an eligible agent must be explicitly recorded as `FAILED`, `BLOCKED`, or `UNASSIGNED`. A task must **never** be silently marked as `COMPLETED`.
3. **Transparency of Simulation:** Fallback or mock data must be explicitly labeled as demo/fallback in both telemetry logs and the Streamlit UI. Simulated outputs must never be presented as verified distributed execution.

### 2.5 Security, Secrets & Privacy
1. **Zero Hardcoded Secrets:** No API keys, Bearer tokens, or passwords may be stored in code or committed to Git. All secrets must be loaded dynamically via environment variables (`.env`), documented via [`.env.example`](../../.env.example).
2. **Log Sanitization:** Sensitive authorization headers and credentials must be masked before writing to log streams or SQLite attempt records.

### 2.6 Documentation & Scrum Synchronization
1. **Documentation Updates:** Any architectural change, new endpoint, or schema update must be documented in `docs/` and referenced in [`README.md`](../../README.md).
2. **Traceability:** Trello cards must contain verified checklist items, matching Story Points, and references to commit hashes or PR numbers.

---

## 3. Sprint Increment Verification Checklist

Before any Sprint Increment is certified for Sprint Review:
- [ ] Working software demonstration prepared and tested locally via [`start.bat`](../../start.bat).
- [ ] Automated unit test suite passes with zero failures and zero errors (`python -m unittest discover tests`).
- [ ] GitHub Actions CI pipeline passes on `main`.
- [ ] SQLite schema migrations tested without data corruption.
- [ ] Associated Sprint Backlog, Review, and Retrospective reports updated under [`docs/scrum/sprints/`](sprints/).
