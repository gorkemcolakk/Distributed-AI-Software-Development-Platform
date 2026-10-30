# Product Backlog

*This document serves as the single authoritative, ordered source of work undertaken by the Scrum Team for the **Distributed AI Software Development Platform**, fully synchronized with the project Trello board and the **2020 Scrum Guide**.*

## Commitment: Product Goal
Deliver a web-based distributed multi-agent software development platform where a **Master Agent** analyzes long-form software requirements documents, decomposes them into dependency-aware subtasks, evaluates heterogeneous LLM agent capabilities (*Coding*, *Reasoning*, *Context*), assigns tasks to local (**Ollama**) or approved worker agents, validates and integrates generated code artifacts, and reports transparent runtime telemetry.

---

## Ordered Product Backlog Items (PBIs)

### Phase 1: Foundation, Requirements & Prototype Baseline (Sprint 1: Oct 01 – Oct 15, 2026)
| PBI ID | Trello Card | Title & Scope Summary | Responsible | Priority | Size (SP) | Est. Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-01** | **S1-01** | **Repository & Team Workflow Governance:** Establish GitHub repo, branch protection rules, and setup guide. | Eren Görkem Çolak | High | 2 | 4h | Done |
| **PBI-02** | **S1-02** | **Streamlit Web UI Prototype:** Build initial web interface for requirement input and agent/task visualization. | Kübra Hepcan | High | 5 | 8h | Done |
| **PBI-03** | **S1-03** | **System Architecture Specification:** Document Master/Worker boundaries, contracts, and data flows. | Mahmut Karaalioğlu | High | 3 | 8h | Done |
| **PBI-04** | **S1-04** | **Initial Data Model & SQLite Design:** Define persistent vs. runtime state, ERD, and SQLite prototype. | İrem Yılmaz | High | 3 | 6h | Done |
| **PBI-05** | **S1-05** | **System Requirements Inventory & Acceptance Criteria:** Decompose course specs into testable requirements. | Kübra Hepcan | Highest | 3 | 6h | Done |
| **PBI-06** | **S1-06** | **Team Local Ollama Model Research:** Benchmark hardware RAM/VRAM and verify candidate Ollama models. | Berat İnan | High | 3 | 8h | Done |
| **PBI-07** | **S1-07** | **Master-Agent & Task Decomposition Prototype:** Implement `orchestrator.py`, `analyzer.py`, and baseline test suite. | Eren Görkem Çolak | Highest | 5 | 12h | Done |

*Phase 1 Total: 7 Items | 24 Story Points | 52 Hours | All Done*

---

### Phase 2: Agent Registry, Fit Score & Lifecycle Isolation (Sprint 2: Oct 15 – Oct 29, 2026)
| PBI ID | Trello Card | Title & Scope Summary | Responsible | Priority | Size (SP) | Est. Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-08** | **S2-01** | **Backend API & Fallback Standardization:** Remove duplicate loader and establish safe offline/quota fallback. | İrem Yılmaz | Highest | 3 | 4h | Done |
| **PBI-09** | **S2-02** | **Unified Agent Registry UI Connection:** Connect Streamlit UI directly to `config/agents_config.json`. | Kübra Hepcan | Highest | 5 | 10h | Done |
| **PBI-10** | **S2-03** | **Weighted Fitness Scoring & Availability Filtering:** Implement `calculate_fit_score` and filter unavailable agents. | Eren Görkem Çolak | High | 3 | 6h | Done |
| **PBI-11** | **S2-04** | **Task Schema Validation & Inter-Agent Contracts:** Validate LLM task decomposition JSON and define contract schemas. | Elif Yılmaz | High | 3 | 6h | Done |
| **PBI-12** | **S2-05** | **Run-Scoped Scheduler Lifecycle (`run_id`):** Isolate scheduler state per run and report `FAILED`/`BLOCKED`/`UNASSIGNED` accurately. | Eren Görkem Çolak | Highest | 3 | 8h | Done |
| **PBI-13** | **S2-06** | **Live Engine-Bound UI Status Monitoring:** Bind UI progress and status tables to real backend execution results. | Kübra Hepcan | High | 3 | 6h | Done |
| **PBI-14** | **S2-07** | **SQLite Layer Integration & Run States:** Integrate `db_manager.py` with unified profiles and run states; prevent false completions. | Mahmut Karaalioğlu | High | 2 | 4h | Done |

*Phase 2 Total: 7 Items | 22 Story Points | 44 Hours | All Done*

---

### Phase 3: Distributed Execution & DAG Scheduling (Sprint 3: Oct 29 – Nov 12, 2026)
| PBI ID | Trello Card | Title & Scope Summary | Responsible | Priority | Size (SP) | Est. Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-15** | **S3-01** | **Master–Worker Communication Contracts & Orchestration:** Define versioned HTTP/JSON task envelopes in `contracts.py`. | Eren Görkem Çolak | Highest | 5 | 10h | Sprint Backlog |
| **PBI-16** | **S3-02** | **Authenticated Worker HTTP API & Code Generation:** Implement Bearer token worker server and local Ollama backend coding. | İrem Yılmaz | Highest | 5 | 10h | Done |
| **PBI-17** | **S3-03** | **FrontendAgent Ollama UI Generation & UI Monitoring:** Generate UI code with local model and display worker statuses on dashboard. | Kübra Hepcan | High | 3 | 8h | Sprint Backlog |
| **PBI-18** | **S3-04** | **DAG Dependency Validation, SQL Generation & Workspace Writer:** Enforce DAG cycle checks, SQL generation, and safe file writer. | Mahmut Karaalioğlu | Highest | 5 | 10h | Sprint Backlog |
| **PBI-19** | **S3-05** | **Artifact Manifest Aggregation & Directory Assembly:** Aggregate worker outputs, compute SHA-256 hashes, and catalog artifacts. | Elif Yılmaz | High | 3 | 8h | Sprint Backlog |
| **PBI-20** | **S3-06** | **TestingAgent Ollama Test Generation & Distributed Tests:** Generate tests with local model and write HTTP API/DAG unit tests. | Berat İnan | High | 3 | 8h | Done |

*Phase 3 Total: 6 Items | 24 Story Points | 54 Hours | Active Sprint (2 Done, 4 in Sprint Backlog)*

---

### Phase 4: Error Recovery, Code Review & CI Quality Gate (Sprint 4: Nov 12 – Nov 26, 2026)
| PBI ID | Trello Card | Title & Scope Summary | Responsible | Priority | Size (SP) | Est. Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-21** | **S4-01** | **Bounded Retry & Alternative Agent Reassignment:** Reassign failed tasks to highest-fit idle backup worker in orchestrator. | Eren Görkem Çolak | Highest | 5 | 8h | Product Backlog |
| **PBI-22** | **S4-02** | **Error Classification & Input/Output Security Hardening:** Classify transient vs. permanent errors and sanitize model inputs/outputs. | İrem Yılmaz | High | 3 | 8h | Product Backlog |
| **PBI-23** | **S4-03** | **UI Code Review Findings & Reassignment History Display:** Render code review statuses, conflict alerts, and attempt logs in UI. | Kübra Hepcan | High | 3 | 8h | Product Backlog |
| **PBI-24** | **S4-04** | **Path/Schema Conflict Resolution & SQLite Attempt Logging:** Detect write collisions and record attempt history in SQLite tables. | Mahmut Karaalioğlu | High | 3 | 8h | Product Backlog |
| **PBI-25** | **S4-05** | **Automated Syntax/Code Review via Local Integration Agent:** Inspect real generated files, evaluate syntax, and approve valid packages. | Elif Yılmaz | Highest | 5 | 10h | Product Backlog |
| **PBI-26** | **S4-06** | **Test Suite Expansion & GitHub Actions CI Gate:** Expand test suite and enforce pull request blocking on CI pipeline failures. | Berat İnan | Highest | 5 | 10h | Product Backlog |

*Phase 4 Total: 6 Items | 24 Story Points | 52 Hours | Planned*

---

### Phase 5: Telemetry Dashboard, Benchmarking & E2E Release (Sprint 5: Nov 26 – Dec 10, 2026)
| PBI ID | Trello Card | Title & Scope Summary | Responsible | Priority | Size (SP) | Est. Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PBI-27** | **S5-01** | **E2E Distributed Orchestration & Latency Telemetry:** Connect full pipeline from requirement to final artifact with execution timing. | Eren Görkem Çolak | High | 3 | 8h | Product Backlog |
| **PBI-28** | **S5-02** | **Documentation & Definition of Done Verification:** Synchronize README, Architecture, DoD, and Scrum sprint records with codebase. | İrem Yılmaz | High | 3 | 6h | Product Backlog |
| **PBI-29** | **S5-03** | **Real Telemetry & Model Comparison Dashboard:** Display real run durations, attempts, and agent comparison charts in Streamlit. | Kübra Hepcan | High | 3 | 8h | Product Backlog |
| **PBI-30** | **S5-04** | **SQLite Execution History & Benchmark Metric Export:** Export runtime execution metrics and agent benchmark data to CSV/JSON. | Mahmut Karaalioğlu | High | 3 | 6h | Product Backlog |
| **PBI-31** | **S5-05** | **E2E Live Demonstration Scenario & Product Owner Acceptance:** Prepare live demo script with complex requirement and verify PO acceptance. | Elif Yılmaz | High | 3 | 6h | Product Backlog |
| **PBI-32** | **S5-06** | **Empirical Ollama Model Benchmarking & E2E Verification:** Benchmark local models on standardized tasks and document findings. | Berat İnan | Highest | 5 | 8h | Product Backlog |

*Phase 5 Total: 6 Items | 20 Story Points | 40 Hours | Planned*

---

## Product Backlog Summary & Velocity Overview
* **Total Product Backlog Items:** 32 PBIs
* **Total Story Points:** 114 SP (242 Estimated Hours)
* **Sprint 1 Delivered:** 24 SP (100% completed)
* **Sprint 2 Delivered:** 22 SP (100% completed)
* **Sprint 3 (In Progress):** 24 SP (8 SP Done, 16 SP in active development)
* **Sprint 4 (Planned):** 24 SP
* **Sprint 5 (Planned):** 20 SP
