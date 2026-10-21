# Product Backlog

*This document serves as the single authoritative source of work undertaken by the Scrum Team for the **Distributed AI Software Development Platform**, ordered by priority and mapped to Sprint iterations.*

## Commitment: Product Goal
Deliver a web-based distributed multi-agent software development platform where a **Master Agent** analyzes long-form software requirements documents, decomposes them into dependency-aware subtasks, evaluates heterogeneous LLM agent capabilities (*Coding*, *Reasoning*, *Context*), assigns tasks to local (**Ollama**) or approved cloud worker agents, validates and integrates generated code artifacts, and reports transparent runtime telemetry.

---

## Ordered Product Backlog Items (PBIs)

### Phase 1: Foundation, Requirements & Prototype Baseline (Sprint 1)
| PBI ID | Trello Card | Title & Description | Acceptance Criteria Summary | Priority | Size (SP) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-01** | **S1-01** | **Repository & Workflow Governance:** Establish GitHub repository, branch rules, and setup guide. | Team access verified; `main` branch workflow documented; setup commands tested. | High | 2 | Done |
| **PBI-02** | **S1-05** | **System Requirements & Acceptance Criteria:** Decompose course specs into testable requirements (`docs/SRS.md`). | Every requirement has observable acceptance criteria; current vs. planned features clearly marked. | Highest | 3 | Done |
| **PBI-03** | **S1-03** | **System Architecture Specification:** Document Master/Worker boundaries and data flows (`docs/ARCHITECTURE.md`). | Component diagram matches repo tree; unimplemented `src/api` marked as planned. | High | 3 | Done |
| **PBI-04** | **S1-04** | **Initial Data Model & SQLite Design:** Define persistent vs. runtime state and ERD (`docs/DATA_MODEL.md`, `db_manager.py`). | Entities (`Agent`, `Task`, `Attempt`, `OutputFile`) defined; SQLite prototype created. | High | 3 | Done |
| **PBI-05** | **S1-06** | **Local Ollama Model Verification:** Research and test local Ollama models across team hardware (`docs/MODEL_RESEARCH.md`). | Hardware RAM/VRAM and `ollama list` verified; model-role matrix documented. | High | 3 | Done |
| **PBI-06** | **S1-02** | **Streamlit Web UI Prototype:** Build initial web interface for requirement input and agent/task visualization (`app.py`). | Launches via `start.bat`; accepts long requirements; displays decomposed tasks and agents. | High | 5 | Done |
| **PBI-07** | **S1-07** | **Master-Agent & Task Decomposition Prototype:** Implement `orchestrator.py`, `analyzer.py`, `capability_eval.py`, and `scheduler.py`. | Decomposes input into 6 subtask categories; unit tests in `test_master_engine.py` pass. | Highest | 5 | Done |

---

### Phase 2: Agent Management, Registry Unification & Task Assignment (Sprint 2)
| PBI ID | Trello Card | Title & Description | Acceptance Criteria Summary | Priority | Size (SP) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-08** | **S2-01** | **API Key Standardization & Safe Fallback:** Remove duplicate `load_api_key()` and enforce safe demo mode without leaking keys. | Single config path; no hardcoded keys; graceful handling of missing keys or 429 errors. | Highest | 3 | In Progress |
| **PBI-09** | **S2-02** | **Unified Canonical Agent Registry:** Connect Streamlit UI and Core Engine to the same `config/agents_config.json` schema. | UI hardcoded `agents_data` removed; UI and engine list identical agent IDs and Ollama tags. | Highest | 5 | In Progress |
| **PBI-10** | **S2-03** | **Weighted Fitness Scoring & Availability Filtering:** Use `TaskCategory` weights and exclude `BUSY`/`OFFLINE`/`ERROR` agents. | Deterministic fit score; unavailable agents excluded; tie-breaker and specialty bonus tested. | High | 3 | In Progress |
| **PBI-11** | **S2-04** | **Task Decomposition Schema Validation:** Validate LLM JSON output against task schema and label fallback data. | Empty input, malformed JSON, unknown categories, and long documents handled predictably. | High | 3 | Sprint Backlog |
| **PBI-12** | **S2-05** | **Run-Scoped Scheduler Lifecycle (`run_id`):** Isolate scheduler state per run and accurately report `FAILED`/`BLOCKED`/`UNASSIGNED`. | Consecutive runs do not collide; failed or unassigned tasks are never marked `COMPLETED`. | Highest | 3 | Sprint Backlog |
| **PBI-13** | **S2-06** | **Live Engine-Bound UI Status Monitoring:** Bind UI progress and status tables to verified backend execution results. | Manual simulation buttons do not fake completion; `FAILED`/`BLOCKED` states visible in UI. | High | 3 | Sprint Backlog |
| **PBI-14** | **S2-07** | **SQLite Persistence Alignment:** Synchronize `db_manager.py` and `DATA_MODEL.md` with `run_id` and unified registry fields. | Database schema supports `run_id` and error states; runtime `state.db` excluded via `.gitignore`. | High | 2 | Sprint Backlog |

---

### Phase 3: Distributed Execution & Dependency Management (Sprint 3)
| PBI ID | Trello Card | Title & Description | Acceptance Criteria Summary | Priority | Size (SP) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-15** | **S3-01** | **Versioned Master–Worker Contracts:** Define HTTP/JSON schemas for task envelopes, result manifests, and errors. | Versioned schemas (`docs/contracts/v1/`) with `run_id`, `task_id`, timestamps, and retry semantics. | Highest | 5 | Product Backlog |
| **PBI-16** | **S3-02** | **Authenticated Worker HTTP API:** Implement worker endpoint/client with Bearer token auth, timeouts, and health checks. | Separate worker process/host accepts valid token requests and rejects unauthorized/malformed calls. | Highest | 5 | Product Backlog |
| **PBI-17** | **S3-03** | **Real Worker Execution & Safe Artifact Collection:** Invoke local Ollama models and write validated files to isolated workspaces. | At least one worker executes real Ollama inference; path traversal prevented; artifact manifest returned. | Highest | 5 | Product Backlog |
| **PBI-18** | **S3-04** | **DAG Dependency Graph Validation:** Detect cyclic/missing dependencies and schedule only tasks with successful prerequisites. | Cycles and missing IDs rejected; failed upstream task leaves downstream tasks `BLOCKED`. | High | 3 | Product Backlog |

---

### Phase 4: Integration, Recovery & Quality Assurance (Sprint 4)
| PBI ID | Trello Card | Title & Description | Acceptance Criteria Summary | Priority | Size (SP) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-19** | **S4-01** | **Bounded Retry & Task Reassignment:** Retry transient errors within limits and reassign to eligible backup agents. | Attempt history recorded; permanent errors not blindly retried; exhausted retries stay `FAILED`. | Highest | 3 | Product Backlog |
| **PBI-20** | **S4-02** | **Evidence-Based Integration Agent:** Inspect generated files for existence, syntax validity, and path conflicts. | Hardcoded `APPROVED` removed; actionable findings per file path; approves only when checks pass. | High | 5 | Product Backlog |
| **PBI-21** | **S4-03** | **Automated Test Suite & CI Quality Gate:** Expand mock-based unit/integration tests and configure GitHub Actions PR checks. | Tests run without live API keys; failing test blocks PR merge; `test_api.py` sanitized. | Highest | 5 | Product Backlog |
| **PBI-22** | **S4-04** | **Input/Output Security & Provider Privacy:** Enforce provider policy, input size validation, and output escaping. | DoD and runtime provider behavior match; untrusted model output sanitized before display/write. | Highest | 3 | Product Backlog |

---

### Phase 5: Telemetry Dashboard, Benchmarking & Release (Sprint 5)
| PBI ID | Trello Card | Title & Description | Acceptance Criteria Summary | Priority | Size (SP) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-23** | **S5-01** | **Real Execution & Agent Telemetry Dashboard:** Render `run_id`, durations, attempts, and agent metrics from real execution records. | Missing metrics shown as `unavailable` (not fake zeros); demo vs. live telemetry clearly labeled. | High | 3 | Product Backlog |
| **PBI-24** | **S5-02** | **Empirical Model Benchmarking:** Compare verified local Ollama models on standardized tasks (`docs/MODEL_BENCHMARK.md`). | Same prompt/task set run across models; latency, pass rate, and hardware conditions recorded in CSV. | High | 5 | Product Backlog |
| **PBI-25** | **S5-03** | **End-to-End Distributed Scenario Verification:** Execute full workflow with a multi-part requirement plus a negative failure case. | Full pipeline verified from requirement to integration; timeout/failure scenario demonstrated. | Highest | 3 | Product Backlog |
| **PBI-26** | **S5-04** | **Release Documentation Alignment:** Synchronize `README.md`, `ARCHITECTURE.md`, `DoD`, and setup guides with final verified code. | Fresh setup verified by a teammate; all simulated vs. distributed capabilities honestly documented. | High | 3 | Product Backlog |