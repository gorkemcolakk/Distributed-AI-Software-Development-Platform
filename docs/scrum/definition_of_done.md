# Definition of Done (DoD)

For the **Distributed AI Software Development Platform** project, a Product Backlog Item (PBI) or Sprint task is considered **"Done"** and ready to be included in the product Increment only when it satisfies all of the following criteria in accordance with the **2020 Scrum Guide** and the project governance board:

> **Scrum Guide Commitment:** *"The Definition of Done is a formal description of the state of the Increment when it meets the quality measures required for the product. The moment a Product Backlog item meets the Definition of Done, an Increment is born. If a Product Backlog item does not meet the Definition of Done, it cannot be released or even presented at the Sprint Review. Instead, it returns to the Product Backlog for future consideration."*

---

## 1. Code Quality & Version Control (Git & GitHub)
- **Git Commit & Branching:** All source code and assets must be committed to the shared GitHub repository on dedicated feature branches (`feature/*`) and merged into `main` via Pull Requests.
- **Clean Repository:** Compiled Python bytecode (`__pycache__/`, `*.pyc`), virtual environments (`venv/`), local secret files (`.env`), and runtime database instances (`state.db`) are excluded via `.gitignore` and never committed.
- **Peer Review:** Code and documentation must be reviewed and approved by at least one other team member in the *"Code Review & Testing"* stage before merging.

## 2. Architecture & Multi-Agent Integration
- **Component Alignment:** Implemented modules must strictly adhere to the contracts, boundaries, and schemas defined in `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, and `src/contracts.py`.
- **Master & Worker Integration:** Where applicable, new features must successfully interface with the Master Agent orchestrator (`orchestrator.py`) or Worker Agent endpoints (`src/api/`).
- **Runtime Transparency:** Simulated/fallback data and actual LLM/agent execution results must be clearly labeled and distinguished in backend telemetry and UI views. Simulated outputs must never be presented as verified distributed execution.

## 3. AI Security, Privacy & Provider Policy
- **Zero Secrets Leakage:** No API keys, Bearer tokens, or credentials may be hardcoded into source code, printed to terminal logs, or exposed in error messages. All secrets must be loaded from environment variables (`.env`), with only `.env.example` committed.
- **Local-First LLM Execution:** The platform primarily operates on local Ollama models (`qwen2.5:3b`, `qwen2.5-coder:7b`, `deepseek-coder:6.7b`, `llama3.2:3b`, `phi4-mini:3.8b`, `qwen2.5-coder:3b`/`gemma2:2b`). When models are unreachable, the system must safely fall back to clearly marked demo responses without crashing.

## 4. Testing & Quality Assurance (QA)
- **No Critical Defects:** The feature must operate reliably without unhandled exceptions or regressions in existing multi-agent workflows.
- **Automated Test Suite:** Existing automated tests (`python -m unittest discover -s tests`) must pass with zero failures. New core functionality must include unit or integration tests utilizing mocks to ensure execution without mandatory external network or live LLM credentials.
- **Accurate Status Reporting:** Unavailable agents, malformed JSON, and timeouts must be reported accurately (`FAILED`, `BLOCKED`, `UNASSIGNED`) and must never be falsely marked as `COMPLETED`.

## 5. Documentation & Trello Synchronization
- **Documentation Updates:** Any architectural, schema, or configuration change must be documented in `README.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, or relevant Scrum documents.
- **Trello Board Verification:** All acceptance criteria and checklist items on the corresponding Trello card must be physically verified with observable repository artifacts and tests before the card is moved to the **Done** list.
