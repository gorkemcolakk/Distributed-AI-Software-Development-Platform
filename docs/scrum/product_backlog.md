# Master Product Backlog
## Distributed AI Software Development Platform (CM6453)

* **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Development Team:**
  - Eren Görkem Çolak (Master Agent — `qwen2.5:3b`)
  - Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`)
  - Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`)
  - Berat İnan (Testing Agent — `deepseek-coder:6.7b`)
  - İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
  - Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`)
* **Academic Course:** CM6453 Software Engineering Process and DevOps
* **Methodology:** Scrum Framework (5 Sprints × 2 Weeks = 10 Weeks)
* **Standard:** 2020 Scrum Guide (Ken Schwaber & Jeff Sutherland)
* **Current Status:** Living Document (Sprint 1 & Sprint 2 Completed, Sprint 3 Completed with 2 Tasks Rolled Over, Sprint 4 Active)

---

## 1. Commitment: Product Goal

> **Product Goal:**  
> *"Deliver an end-to-end web-based distributed software engineering platform where a central Master Agent receives long-form software specifications, decomposes them into a validated Directed Acyclic Graph (DAG) of architectural subtasks, evaluates heterogeneous worker agent capabilities (Coding, Reasoning, Context Window), autonomously assigns tasks to specialized local Ollama models across distributed nodes, validates and integrates produced code artifacts through automated syntax and conflict review, and provides verifiable telemetry and benchmarking through a web dashboard."*

---

## 2. Epics & Thematic Breakdown

* **Epic 1 (Foundation & Architecture):** Repository governance, architectural specifications, persistence design, and web UI baseline.
* **Epic 2 (Agent Management & Intelligence):** Capability profiles, weighted candidate selection algorithm, schema validation, and run isolation.
* **Epic 3 (Distributed Execution & Worker Integration):** Local Ollama model prompting, REST worker communication, artifact production, and DAG dependency enforcement.
* **Epic 4 (Quality Assurance, Recovery & Integration):** Code review automation, AST syntax inspection, conflict resolution, bounded retries, task reassignment, and CI quality gates.
* **Epic 5 (Telemetry, Benchmarking & Release):** Telemetry dashboard, empirical model benchmarks, end-to-end validation, and release documentation.

---

## 3. Ordered Product Backlog Items (PBIs)

### Phase 1: Foundation, Requirements & Baseline Prototype (Sprint 1: Sept 24 – Oct 07, 2026)
| PBI ID | Card ID | Epic | Title & Description | Primary Assignee | Priority | SP | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-01** | **S1-01** | Epic 1 | **Repository & Team Workflow Governance:** Establish GitHub repository, branch protection rules, environment setup scripts, and collaboration guidelines. | Eren Görkem Çolak | High | 2 | None | **Done** |
| **PBI-02** | **S1-02** | Epic 1 | **Streamlit Web UI Prototype:** Build initial web interface for requirement input, agent capability cards, and decomposed task visualization. | Kübra Hepcan | High | 5 | S1-01 | **Done** |
| **PBI-03** | **S1-03** | Epic 1 | **System Architecture Specification:** Document Master/Worker boundaries, communication protocols, and module responsibilities in [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md). | Mahmut Karaalioğlu | High | 3 | S1-05 | **Done** |
| **PBI-04** | **S1-04** | Epic 1 | **Initial Data Model & SQLite Design:** Distinguish persistent storage from in-memory state and design database schema in [`docs/DATA_MODEL.md`](../DATA_MODEL.md) and [`src/master/db_manager.py`](../../src/master/db_manager.py). | İrem Yılmaz | High | 3 | S1-05, S1-03 | **Done** |
| **PBI-05** | **S1-05** | Epic 1 | **System Requirements Inventory & Acceptance Criteria:** Decompose course project specifications into testable functional and non-functional requirements in [`docs/SRS.md`](../SRS.md). | Kübra Hepcan | Highest | 3 | None | **Done** |
| **PBI-06** | **S1-06** | Epic 2 | **Local Ollama Model Verification:** Research and verify local Ollama model options across team hardware and document findings in [`docs/MODEL_RESEARCH.md`](../MODEL_RESEARCH.md). | Berat İnan | High | 3 | Team Hardware | **Done** |
| **PBI-07** | **S1-07** | Epic 1 | **Master-Agent & Task Decomposition Prototype:** Implement core orchestrator engine (`orchestrator.py`), requirement analyzer (`analyzer.py`), capability evaluator (`capability_eval.py`), and task scheduler (`scheduler.py`). | Eren Görkem Çolak | Highest | 5 | S1-01, S1-03 | **Done** |

*Sprint 1 Velocity Delivered:* **24 Story Points** (7 of 7 Cards Completed). Detailed in [Sprint 1 Backlog](sprints/sprint_1_backlog.md) and [Sprint 1 Report](sprints/sprint_1_report.md).

---

### Phase 2: Agent Management, Registry Unification & Task Assignment (Sprint 2: Oct 08 – Oct 21, 2026)
| PBI ID | Card ID | Epic | Title & Description | Primary Assignee | Priority | SP | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-08** | **S2-01** | Epic 2 | **API Key Standardization & Safe Fallback:** Centralize API/Ollama configuration, remove duplicate loaders, and implement safe offline fallback mode without hardcoded credentials. | İrem Yılmaz | Highest | 3 | S1-06 | **Done** |
| **PBI-09** | **S2-02** | Epic 2 | **Canonical Agent Registry & UI Status Integration:** Connect Streamlit UI to shared [`config/agents_config.json`](../../config/agents_config.json) and display live agent statuses (`IDLE`, `BUSY`, `OFFLINE`, `ERROR`). | Kübra Hepcan | Highest | 5 | S1-06, S2-01 | **Done** |
| **PBI-10** | **S2-03** | Epic 2 | **Weighted Selection Algorithm & Scheduler Lifecycle (`run_id`):** Implement multi-dimensional fitness scoring, filter unavailable agents, isolate per-run scheduler state, and prevent false `COMPLETED` reporting. | Eren Görkem Çolak | Highest | 5 | S2-02, S1-07 | **Done** |
| **PBI-11** | **S2-04** | Epic 2 | **Task Classification Schema Validation:** Validate decomposed subtask JSON schemas using Pydantic contracts and define baseline inter-agent communication interfaces in [`docs/INTER_AGENT_CONTRACTS.md`](../INTER_AGENT_CONTRACTS.md). | Elif Yılmaz | High | 3 | S1-05, S2-01 | **Done** |
| **PBI-12** | **S2-05** | Epic 1 | **SQLite Persistence Integration:** Implement SQLite WAL-mode tables (`runs`, `agents`, `tasks`, `attempts`) with `run_id` isolation, error constraints, and `.gitignore` protection. | Mahmut Karaalioğlu | High | 3 | S1-04, S2-03 | **Done** |
| **PBI-13** | **S2-06** | Epic 4 | **Automated Unit Test Suite for Selection & Scheduler:** Develop deterministic mock-based unit tests for weighted selection, status filtering, schema validation, and scheduler lifecycle in [`tests/test_master_engine.py`](../../tests/test_master_engine.py). | Berat İnan | High | 3 | S2-03, S2-04, S2-05 | **Done** |

*Sprint 2 Velocity Delivered:* **22 Story Points** (6 of 6 Cards Completed). Detailed in [Sprint 2 Backlog](sprints/sprint_2_backlog.md) and [Sprint 2 Report](sprints/sprint_2_report.md).

---

### Phase 3: Distributed Execution & Dependency Management (Sprint 3: Oct 22 – Nov 04, 2026)
| PBI ID | Card ID | Epic | Title & Description | Primary Assignee | Priority | SP | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-14** | **S3-01** | Epic 3 | **Versioned Master–Worker Contracts & Task Dispatch:** Finalize versioned JSON schemas (`TaskPayloadContract_v1`, `WorkerTaskResultContract_v1`) in [`src/contracts.py`](../../src/contracts.py) and update orchestrator dispatch. | Eren Görkem Çolak | Highest | 5 | S2-03, S2-04 | **Done** |
| **PBI-15** | **S3-02** | Epic 3 | **Authenticated Worker HTTP API & Backend Ollama Code Generation:** Implement Bearer-token protected REST worker endpoint (`src/api/worker_server.py`) and connect BackendAgent to local Ollama (`qwen2.5-coder:7b`). | İrem Yılmaz | Highest | 5 | S3-01, S2-01 | **Done** |
| **PBI-16** | **S3-03** | Epic 3 | **FrontendAgent Local Ollama Generation & Distributed UI Monitor:** Connect FrontendAgent to local Ollama (`qwen2.5-coder:3b`) and display distributed worker and file statuses in Streamlit UI. | Kübra Hepcan | High | 3 | S3-01, S2-02 | **Carried Over to Sprint 4** (In Progress) |
| **PBI-17** | **S3-04** | Epic 3 | **DAG Dependency Graph Validation & Safe Workspace Writer:** Validate task DAG for cycles (Tarjan SCC), enforce cascading `BLOCKED` states on failure, generate SQL via DatabaseAgent, and enforce safe file writing to `workspaces/{run_id}/`. | Mahmut Karaalioğlu | Highest | 5 | S3-01, S2-05 | **Done** |
| **PBI-18** | **S3-05** | Epic 3 | **Artifact Manifest Aggregation & Output Collection:** Collect worker code outputs, compute file sizes and SHA-256 integrity hashes, and structure standardized artifact manifests via IntegrationAgent. | Elif Yılmaz | High | 3 | S3-01, S3-04 | **Carried Over to Sprint 4** (Sprint Backlog) |
| **PBI-19** | **S3-06** | Epic 4 | **TestingAgent Ollama Generation & DAG/HTTP Test Suite:** Connect TestingAgent to local Ollama (`deepseek-coder:6.7b`) and write automated unit tests for HTTP auth, DAG cycle detection, and path traversal prevention. | Berat İnan | High | 3 | S3-01, S3-02, S3-04 | **Done** |

*Sprint 3 Velocity Delivered:* **18 Story Points** (4 of 6 Cards Completed). 2 cards (S3-03 and S3-05, totaling 6 SP) were incomplete and rolled over into Sprint 4 in accordance with Scrum rules. Detailed in [Sprint 3 Backlog](sprints/sprint_3_backlog.md) and [Sprint 3 Report](sprints/sprint_3_report.md).

---

### Phase 4: Integration, Quality Assurance & Fault Recovery (Sprint 4: Nov 05 – Nov 18, 2026 — Active)
| PBI ID | Card ID | Epic | Title & Description | Primary Assignee | Priority | SP | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-16** | **S3-03** | Epic 3 | *(Rolled over from S3)* **FrontendAgent Local Ollama & Distributed UI Monitor:** Connect FrontendAgent to local Ollama (`qwen2.5-coder:3b`) and display distributed worker and file statuses in Streamlit UI. | Kübra Hepcan | High | 3 | S3-01, S2-02 | **In Progress** |
| **PBI-18** | **S3-05** | Epic 3 | *(Rolled over from S3)* **Artifact Manifest Aggregation & Output Collection:** Collect worker code outputs, compute file sizes and SHA-256 integrity hashes, and structure standardized artifact manifests via IntegrationAgent. | Elif Yılmaz | High | 3 | S3-01, S3-04 | **Sprint Backlog** |
| **PBI-20** | **S4-01** | Epic 4 | **Bounded Retry & Automated Task Reassignment:** Implement state machine in `orchestrator.py` with bounded retry limits (`max_retries`) for transient errors and automatic failover to the second-highest idle candidate agent. | Eren Görkem Çolak | Highest | 5 | S3-01, S3-04, S4-02 | **Sprint Backlog** |
| **PBI-21** | **S4-02** | Epic 4 | **Error Classification & Input/Output Security Hardening:** Classify worker errors into transient (timeout/quota) vs. permanent (syntax/schema), sanitize requirements input length, escape untrusted model output, and purge credentials from logs. | İrem Yılmaz | High | 3 | S3-02, S2-01 | **Sprint Backlog** |
| **PBI-22** | **S4-03** | Epic 1 | **UI Display of Code Review Findings & Reassignment History:** Display file-by-file code review results (`APPROVED`, `REVIEW_REQUIRED`, `REJECTED`), path conflict alerts, and task reassignment histories in Streamlit dashboard. | Kübra Hepcan | High | 3 | S4-01, S4-05 | **Sprint Backlog** |
| **PBI-23** | **S4-04** | Epic 4 | **File Path/Schema Conflict Resolution & SQLite Attempt History:** Detect write conflicts in shared workspaces, record attempt counts and error details in SQLite `attempts` table, and persist generated file metadata in `output_files`. | Mahmut Karaalioğlu | High | 3 | S3-04, S4-01 | **Sprint Backlog** |
| **PBI-24** | **S4-05** | Epic 4 | **Integration Agent Code Review & Packaging:** Replace static `APPROVED` response with automated Python AST syntax verification, LLM code review via `phi4-mini:3.8b`, and assembled project artifact packaging. | Elif Yılmaz | Highest | 5 | S3-05, S4-04 | **Sprint Backlog** |
| **PBI-25** | **S4-06** | Epic 4 | **Automated Test Expansion & GitHub Actions CI Gate:** Author mock-based unit tests for retry/reassignment and conflict detection, expand [`.github/workflows/tests.yml`](../../.github/workflows/tests.yml) to block failing PR merges, and sanitize test suites. | Berat İnan | Highest | 5 | S4-01, S4-02, S4-04, S4-05 | **Sprint Backlog** |

*Sprint 4 Committed Capacity:* **30 Story Points** (6 Core Cards: 24 SP + 2 Rolled Over Cards: 6 SP). Detailed in [Sprint 4 Backlog](sprints/sprint_4_backlog.md) and [Sprint 4 Report](sprints/sprint_4_report.md).

---

### Phase 5: Telemetry, Benchmarking, Complete System & Release (Sprint 5: Nov 19 – Dec 02, 2026 — Planned)
| PBI ID | Card ID | Epic | Title & Description | Primary Assignee | Priority | SP | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-26** | **S5-01** | Epic 5 | **End-to-End Distributed Workflow & Telemetry Logging:** Orchestrate full pipeline from requirement input to integrated application package, recording per-task start/finish timestamps and latency metrics in `orchestrator.py`. | Eren Görkem Çolak | Highest | 3 | S4-01, S4-05 | **Planned** |
| **PBI-27** | **S5-02** | Epic 5 | **Documentation & System Harmonization:** Synchronize [`README.md`](../../README.md), [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md), [`docs/DATA_MODEL.md`](../DATA_MODEL.md), [`docs/SRS.md`](../SRS.md), and Definition of Done with final verified code and local Ollama setup. | İrem Yılmaz | High | 3 | S5-01, S5-04 | **Planned** |
| **PBI-28** | **S5-03** | Epic 5 | **Live Telemetry & Model Benchmark Visualizer Dashboard:** Render real execution runs (`run_id`), task durations, retry counts, and agent comparison charts in Streamlit UI; clearly distinguish live vs. demo data. | Kübra Hepcan | High | 3 | S5-01, S5-04 | **Planned** |
| **PBI-29** | **S5-04** | Epic 5 | **SQLite Telemetry & Benchmark Data Export:** Implement queries and CSV/JSON export functionality in `db_manager.py` for agent success rates, latencies, and attempt counts. | Mahmut Karaalioğlu | High | 3 | S4-04, S5-01 | **Planned** |
| **PBI-30** | **S5-05** | Epic 5 | **Final Demonstration Scenario & PO Acceptance Verification:** Rehearse multi-paragraph software requirement demo (`sample_requirement.md`), verify assembled web app, test negative failure path, and confirm PO acceptance. | Elif Yılmaz | Highest | 3 | S5-01, S5-03 | **Planned** |
| **PBI-31** | **S5-06** | Epic 5 | **Empirical Ollama Benchmark & E2E Test Suite Validation:** Benchmark local team models using standardized prompts (`master_model_benchmark.py`), record latency/accuracy in benchmark report, and execute full E2E test suite. | Berat İnan | Highest | 5 | S5-01, S5-04 | **Planned** |

*Sprint 5 Planned Capacity:* **20 Story Points** (6 Cards). Detailed in [Sprint 5 Backlog](sprints/sprint_5_backlog.md) and [Sprint 5 Report](sprints/sprint_5_report.md).

---

## 4. Scrum Traceability & Quality Commitments

1. **Alignment with Product Goal:** Every PBI directly supports the incremental realization of the distributed multi-agent platform, from foundational setup to empirical benchmarking.
2. **Definition of Done (DoD):** All PBIs must satisfy the unified [Definition of Done](definition_of_done.md) before being marked as `Done` in Sprint Reviews.
3. **Carry-over Management:** Unfinished work (e.g., S3-03 and S3-05 from Sprint 3) is never marked done; it returns to the backlog and is prioritized in the next Sprint Backlog.
4. **Honest Reporting:** No simulated feature or mocked test is reported as verified distributed execution. Unimplemented capabilities are explicitly labeled as planned.
