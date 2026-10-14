# Definition of Done (DoD)

For the **Distributed AI Software Development Platform** project, a Product Backlog Item (PBI) or Sprint task is considered **"Done"** and ready to be presented at the Sprint Review only when it satisfies all of the following criteria:

## 1. Code Quality & Version Control (Git & GitHub)
- **Branching Strategy:** All development work must be performed on dedicated feature branches (`feature/*`) and integrated into `main` via Pull Requests (PRs) rather than uncontrolled direct pushes.
- **Clean Repository:** Compiled Python bytecode (`__pycache__/`, `*.pyc`), virtual environments (`venv/`), local environment files (`.env`), and runtime database files (`*.db`) must be excluded via `.gitignore` and never committed to the repository.
- **Peer Review:** Every code change or documentation update must be reviewed and approved by at least one other team member in the *"Code Review & Testing"* column before merging.

## 2. Architecture & Multi-Agent Integration
- **Component Alignment:** Implemented modules must adhere to the component boundaries, contracts, and data schemas defined in `docs/ARCHITECTURE.md` and `docs/DATA_MODEL.md`.
- **Runtime Transparency:** Simulated (mock/fallback/demo) data and actual LLM/agent execution results must be clearly distinguished in both the backend and UI. Hardcoded or simulated outputs must never be reported as verified distributed execution.

## 3. AI Provider Policy, Security & Privacy
- **Secret Management:** No real API keys, tokens, or credentials may be hardcoded in source files, printed to logs, or exposed in error messages. All secrets must be loaded from environment variables (`.env`), with only `.env.example` committed to the repository.
- **Local-First & Cloud LLM Usage:** The platform is designed to primarily support local LLM execution via **Ollama**. External cloud LLM providers (e.g., Google Gemini API) may only be invoked in components approved by the Product Owner when an API key is explicitly configured by the user. When no API key or local model server is available, the application must safely transition to a clearly labeled demo/fallback mode without transmitting data externally.

## 4. Testing & Quality Assurance (QA)
- **Automated Tests:** Existing unit tests (`python -m unittest discover -s tests`) must pass without errors. New core logic must include deterministic unit tests (using mocks/stubs so that tests run without requiring live API keys).
- **Error Handling & Accurate Status Reporting:** Empty inputs, malformed JSON outputs, unavailable/busy agents, or network/quota timeouts must be handled gracefully without crashing the application. Failed, blocked, or unassigned tasks must be reported accurately (`FAILED`, `BLOCKED`, `UNASSIGNED`) and never silently marked as `COMPLETED`.

## 5. Documentation & Trello Synchronization
- **Documentation Updates:** Any change affecting setup, architecture, or data schemas must be reflected in `README.md`, `docs/ARCHITECTURE.md`, or `docs/DATA_MODEL.md`.
- **Trello Verification:** All checklist items on the corresponding Trello card must be verified with observable code or test evidence before moving the card to the **Done** list.