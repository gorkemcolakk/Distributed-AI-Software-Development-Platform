# Software Requirements Specification (SRS)
## Distributed AI Software Development Platform
**Course:** CM6453 Software Engineering Process and DevOps  
**Methodology:** Scrum (5 Iterations / 10 Weeks)  

---

## 1. Introduction

### 1.1 Purpose
The purpose of this document is to define the software requirements for the Distributed AI Software Development Platform. The platform automates end-to-end software development by receiving high-level user requirements, decomposing them into engineering sub-tasks with a shared domain contract, matching these tasks against distributed LLM worker agents based on their capability profiles, and coordinating their execution across a local or distributed network.

### 1.2 Product Scope
The system is a web-based platform that coordinates multiple AI agents to generate software projects. A user submits a project request (such as an Online Library Management System or Inventory Tracker) through a Streamlit web dashboard. The Master Agent (`qwen2.5:7b`) divides this request into dependency-ordered sub-tasks, including requirements/architecture analysis, database schema design, backend API development, frontend UI development, automated testing, and integration/code review. Worker agents running specialized local Ollama models are registered in `config/agents_config.json`, and each task is assigned according to the agent's weighted capability score (*Coding*, *Reasoning*, *Context Capacity*). The platform validates generated files via AST/SQL inspection, resolves file/schema conflicts, runs automated tests, recovers from worker failures via bounded retries and failover, and packages the output into `workspaces/{run_id}/`.

---

## 2. Overall Description

### 2.1 Product Perspective
Rather than relying on a single monolithic cloud LLM, this platform distributes programming workloads across specialized local Ollama LLM agents operating in-process or on separate machines over HTTP REST / Tailscale VPN. The Master Agent (`src/master/orchestrator.py`) serves as the central coordination engine, while Worker Agents focus on specific software engineering roles:
- **Master Agent (`qwen2.5:7b`):** Requirement decomposition, shared domain contract extraction, capability routing, and parallel DAG orchestration.
- **Database Agent (`llama3.2:3b`):** SQLite DDL schema design and migration generation.
- **Backend Agent (`qwen2.5-coder:7b`):** FastAPI/REST backend endpoints and business logic.
- **Frontend Agent (`qwen2.5-coder:3b`):** Web UI components and state layout.
- **Testing Agent (`deepseek-coder:6.7b`):** Pytest automated unit and integration test generation.
- **Integration Agent (`phi4-mini:3.8b`):** AST/SQL syntax review, conflict resolution, SHA-256 manifest aggregation, and project packaging.

### 2.2 Product Features
* **Requirement Input & Validation:** A multi-line text area where the user enters software requirements, validated by `src/security/input_validation.py`.
* **LLM & Template Task Decomposition:** The Master Agent (`src/master/analyzer.py`) decomposes user input into a validated DAG of sub-tasks and extracts a shared domain contract (entities, fields, REST routes), with safe fallback to a deterministic template if Ollama is unavailable.
* **Viewing Sub-Tasks & Shared Contract:** Interactive dashboard views displaying decomposed tasks, dependencies, execution statuses, and the shared contract.
* **Canonical Agent Registry:** A live table and configuration (`config/agents_config.json`) showing registered worker agents, their assigned Ollama models, live availability (`IDLE`, `BUSY`, `OFFLINE`, `ERROR`), and capability scores (`Coding`, `Reasoning`, `Context Capacity`).
* **Capability-Based Task Assignment & Failover:** Matching each task with the highest-scoring eligible agent (`FitScore`) and automatically reassigning on transient failure or timeout.
* **Code Review, Conflict Resolution & Telemetry Dashboard:** Automated AST/SQL review verdicts (`APPROVED`, `REVIEW_REQUIRED`, `REJECTED`), file path/schema conflict alerts, and empirical model/run telemetry comparisons.

### 2.3 User Classes and System Roles
* **User (Software Lead / Evaluator):** Enters project requirements, triggers orchestration, inspects live agent execution, reviews AST/conflict reports, and exports generated project artifacts.
* **Master Agent (`src/master/`):** The central orchestration engine that decomposes prompts into a DAG, evaluates agent capabilities, dispatches tasks locally or over HTTP, and manages persistence in SQLite (`state.db`).
* **Worker Agent (`src/agents/` & `src/api/worker_server.py`):** Standalone FastAPI worker processes or in-process agents running specialized Ollama models that receive `TaskPayloadContract_v1` envelopes and return `WorkerTaskResultContract_v1` artifacts.

### 2.4 Operating Environment
* **Web Frontend:** Modern web browser accessing the Streamlit dashboard (`master_agent_projesi/app.py`, `review_panel.py`, `run_export.py`).
* **Master Agent & Worker Runtime:** Python 3.10+ (verified on Python 3.13) running FastAPI (`uvicorn`), Streamlit, Pydantic v2, and SQLite (WAL mode).
* **Local LLM Engine:** Ollama (`http://localhost:11434`) running open-weights models (`qwen2.5:7b`, `qwen2.5-coder:7b`, `qwen2.5-coder:3b`, `llama3.2:3b`, `deepseek-coder:6.7b`, `phi4-mini:3.8b`).
* **Worker Agent Nodes:** Local processes or distributed developer machines connected over local LAN or Tailscale VPN (`100.x.y.z`).
* **Project & CI Tools:** Trello for Scrum sprint planning and task tracking; GitHub and GitHub Actions (`.github/workflows/tests.yml`) for version control and automated CI quality gates.

### 2.5 Design Constraints
* **Independent Agents & Sandbox Confinement:** Worker agents run independently so a failure on one node does not crash the Master UI, and all generated files are strictly confined to `workspaces/{run_id}/`.
* **Standard Scoring:** Capability scores for Coding, Reasoning, and Context Capacity are normalized between 0 and 100 in `config/agents_config.json`.
* **Scrum Schedule:** The project is divided into 5 two-week sprints (10 weeks total: Oct 01, 2026 – Dec 10, 2026).

---

## 3. System Features & Functional Requirements

### 3.1 Requirement Input & Task Decomposition
* **REQ-1 (Requirement Input Form):** The system provides a multi-line text area on the Streamlit dashboard where users can write or paste detailed software requirements, validated against length and character constraints. *(Verified — Sprint 1 & Sprint 4)*
* **REQ-2 (Task Decomposition Logic):** The Master Agent (`src/master/analyzer.py`) analyzes the submitted text via local Ollama (`qwen2.5:7b`) or deterministic template fallback and breaks it down into dependency-aware engineering sub-tasks alongside a shared domain contract. *(Verified — Sprint 1 & Sprint 4)*
* **REQ-3 (Sub-Task & Contract Display):** The dashboard displays decomposed tasks, dependencies, assigned agents, and the shared domain contract in interactive expandable panels. *(Verified — Sprint 1 & Sprint 4)*
* **REQ-4 (Decomposition & Execution Feedback):** The system shows real-time execution status badges (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `BLOCKED`, `RETRYING`, `REASSIGNED`) and completion summaries. *(Verified — Sprint 1 & Sprint 4)*

### 3.2 Agent Registry and Capabilities
* **REQ-5 (Agent Capability Display):** The dashboard displays registered agents from `config/agents_config.json` showing each agent's ID, model tag, specialty domain, live status, and capability scores (`Coding`, `Reasoning`, `Context Capacity`). *(Verified — Sprint 1 & Sprint 2)*
* **REQ-6 (Score Representation):** Capability metrics for Coding, Reasoning, and Context Capacity are represented on a 0–100 scale with provenance tracking (`estimated` vs. `measured`). *(Verified — Sprint 1 & Sprint 2)*

### 3.3 Task Assignment, Distributed Execution, Quality Assurance & Evaluation
* **REQ-7 (Capability-Based Assignment):** The Master Agent (`src/master/capability_eval.py`) matches and assigns decomposed tasks to eligible `IDLE` agents based on weighted `FitScore` and specialty alignment. *(Verified — Sprint 2)*
* **REQ-8 (Distributed Network Communication):** The Master Agent transmits versioned JSON task envelopes (`TaskPayloadContract_v1`) to worker agent nodes over Bearer-token authenticated HTTP REST (`src/api/worker_server.py`, `src/agents/remote_agent.py`). *(Verified — Sprint 3)*
* **REQ-9 (Timeout, Error Recovery & Code Review):** The system classifies transient vs. permanent errors (`src/security/error_classification.py`), executes bounded retries and automatic failover (`src/master/retry_policy.py`), resolves file/schema conflicts (`src/master/conflicts.py`), and validates generated code via AST/SQL inspection (`src/agents/integration_agent.py`). *(Verified — Sprint 4)*
* **REQ-10 (End-to-End Workflow & Evaluation Dashboard):** The platform executes an end-to-end development workflow from requirement prompt to packaged project archive and displays a telemetry/benchmark dashboard comparing run latencies, attempt counts, and local Ollama model performance. *(Target — Sprint 5)*

---

## 4. External Interface Requirements

### 4.1 User Interface
The web interface (`master_agent_projesi/app.py` and `review_panel.py`) is built as an interactive Streamlit dashboard:
* **Requirement & Execution Panel:** Displays the requirement input area, execution controls, shared domain contract viewer, DAG task list, and run export controls (`run_export.py`).
* **Agent Status, Review & Telemetry Panels:** Displays registered worker agents (`config/agents_config.json`), live statuses, AST/SQL code review verdicts, path/schema conflict alerts, reassignment histories, and run/model performance metrics.

### 4.2 Software and Component Interfaces
* **Streamlit Web UI (`master_agent_projesi/`):** Frontend application for user interactions, review inspection, and telemetry visualization.
* **Master Agent Service (`src/master/`):** Python orchestration engine managing LLM decomposition, capability scoring, DAG scheduling, parallel dispatch, conflict resolution, and SQLite persistence (`state.db`).
* **Worker Agent Nodes (`src/api/worker_server.py` & `src/agents/`):** FastAPI REST servers exposing `GET /health` and Bearer-protected `POST /task` endpoints backed by local Ollama models or labeled fallback generators.
* **Local Ollama API (`http://localhost:11434`):** Local inference endpoint serving `qwen2.5:7b`, `qwen2.5-coder:7b`, `qwen2.5-coder:3b`, `llama3.2:3b`, `deepseek-coder:6.7b`, and `phi4-mini:3.8b`.

### 4.3 Communication Interfaces
Network communication between the Master Agent and distributed worker agents uses HTTP/1.1 REST with JSON payloads governed by versioned Pydantic v2 contracts (`contract_version = "1.0"` in `src/contracts.py` and `src/a2a_protocol.py`), Bearer Token authentication (`Authorization: Bearer <token>`), per-task timeouts, and idempotent duplicate-task tracking (`DuplicateTaskTracker`).

---

## 5. Non-Functional Requirements (NFR)

* **NFR-1 (Response Latency & Non-Blocking Feedback):** Upon triggering analysis, the web interface displays immediate progress indicators while independent tasks execute concurrently (`ThreadPoolExecutor`), preventing unresponsive UI states.
* **NFR-2 (Node Fault Isolation & Truthful State):** If a distributed worker disconnects, times out, or encounters an error, the Master Agent traps the error gracefully, attempts bounded retry/failover, and never marks a failed or blocked task as `COMPLETED` (enforced via Python guards, SQLite `CHECK` constraints, and database triggers).
* **NFR-3 (System Extensibility & Security):** New worker agents and Ollama models can be added via `config/agents_config.json` and `.env` without modifying core orchestration logic. All file writes are sandboxed to `workspaces/{run_id}/` against path traversal, and credentials are masked in logs and SQLite records.