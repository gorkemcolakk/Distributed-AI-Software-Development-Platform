# Distributed AI Software Development Platform Architecture

## 1. System Overview
The **Distributed AI Software Development Platform** is a multi-agent software engineering system designed to automatically analyze high-level software requirements, decompose them into a validated Directed Acyclic Graph (DAG) with a shared domain contract, and dynamically dispatch tasks to specialized local (**Ollama**) or distributed (**HTTP / Tailscale VPN**) worker agents using versioned JSON contracts (`v1.0`).

```
+-----------------------------------------------------------------------+
|                        STREAMLIT USER INTERFACE                       |
|  master_agent_projesi/app.py + review_panel.py + run_export.py        |
|  Requirement Input -> Shared Contract & DAG -> Live Monitor & Review  |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                     MASTER AGENT (qwen2.5:7b)                         |
|  +---------------------+  +---------------------+  +---------------+  |
|  | Requirements Engine |  | Capability Evaluator|  | Task Scheduler|  |
|  | (analyzer.py + LLM) |  | (capability_eval.py)|  | (scheduler.py)|  |
|  +---------------------+  +---------------------+  +---------------+  |
|  | MasterOrchestrator + RetryPolicy + Security + Parallel Dispatch    |
+-----------------------------------------------------------------------+
        |                     |                     |               |
        | HTTP/JSON (v1.0)    | HTTP/JSON (v1.0)    | HTTP/JSON     | HTTP/JSON
        v                     v                     v               v
 +--------------+      +--------------+      +-------------+  +-------------+
 | Frontend Agt |      | Backend Agt  |      | Database Agt|  | Testing Agt |
 |(qwen2.5:3b)  |      |(qwen2.5:7b)  |      | (llama3.2)  |  | (deepseek)  |
 +--------------+      +--------------+      +-------------+  +-------------+
        |                     |                     |               |
        +---------------------+---------------------+---------------+
                                   |
                                   | Chained output_artifacts & artifact_sources
                                   v
+-----------------------------------------------------------------------+
|                    INTEGRATION AGENT (phi4-mini:3.8b)                 |
|      AST/SQL Inspection -> Conflict Resolution -> workspaces/run_id   |
+-----------------------------------------------------------------------+
```

## 2. Core Components

### A. Requirements Analyzer (`src/master/analyzer.py`) & Schema Validator (`src/contracts.py`)
- Validates input requirements via `src/security/input_validation.py` (length bounds, empty checks, character sanitization).
- Connects to local Ollama (`qwen2.5:7b`) to dynamically decompose requirements into dependency-aware subtasks and extract a **shared domain contract** (entities/tables, fields, and REST endpoints) injected into all worker envelopes.
- Validates decomposed subtask lists via `validate_master_tasks()` (`MasterSubTaskSchema`), enforces `MAX_LLM_TASKS` and acyclic DAG guarantees, and falls back deterministically to the 6-stage template (`decomposition_mode="template"`) if the LLM is offline or returns malformed JSON:
  - `task-req-1`: Requirements & Architecture Design
  - `task-db-1`: Database Schema & Migration Definition (depends on `task-req-1`)
  - `task-be-1`: Core Backend API Implementation (depends on `task-db-1`)
  - `task-fe-1`: Frontend User Interface & Components (depends on `task-be-1`)
  - `task-qa-1`: Automated Testing & Quality Assurance (depends on `task-fe-1`)
  - `task-int-1`: Integration, Review & Packaging (depends on `task-qa-1`)

### B. Capability Evaluator & Matching Engine (`src/master/capability_eval.py`)
- Evaluates registered agents (`config/agents_config.json`) based on 3 primary capability dimensions:
  1. **Coding Capability ($C$):** Accuracy, syntax validity, and code formatting (0–100).
  2. **Reasoning Capability ($R$):** Logic decomposition and architectural design (0–100).
  3. **Context Capacity ($K$):** Multi-file awareness and context length tolerance (0–100).
- Filters out unavailable (`BUSY`, `OFFLINE`, `ERROR`) agents (`available_only=True`) and prioritizes specialty matches before weighted fitness scoring:
  $$\text{FitScore} = w_C \cdot C + w_R \cdot R + w_K \cdot K + \text{SpecialtyBonus}$$

### C. DAG Scheduler, Parallel Dispatch & Fault Recovery (`src/master/scheduler.py`, `orchestrator.py`, `retry_policy.py`)
- **Topological Scheduling (`scheduler.py`):** Performs cycle detection before execution (`CyclicDependencyError`) and propagates cascading `BLOCKED` states to downstream tasks whenever an upstream dependency fails.
- **Parallel Execution (`orchestrator.py`):** Dispatches independent ready tasks concurrently using `ThreadPoolExecutor` (`MASTER_PARALLEL_DISPATCH`).
- **Bounded Retry & Failover (`retry_policy.py` & `src/security/error_classification.py`):** Classifies failures into transient (`TIMEOUT`, `UNREACHABLE`, rate limit `429`) vs. permanent (`CONTRACT_VIOLATION`, `UNSAFE_PATH`, syntax defects). Transient errors trigger bounded retries (`max_retries`), followed by automatic failover reassignment to the next highest-scoring `IDLE` candidate agent.

### D. Worker Agents, A2A Protocol & Remote Dispatch (`src/agents/`, `src/a2a_protocol.py`, `src/api/worker_server.py`)
- **BaseAgent (`src/agents/base_agent.py`):** Abstract class defining state management, logging, execution lifecycle, and standard `TaskResult` structures.
- **RemoteAgentProxy (`src/agents/remote_agent.py`) & A2A Protocol (`src/a2a_protocol.py`):** Transparent `BaseAgent` proxy that wraps any worker agent configured with a remote HTTP / Tailscale URL (`BACKEND_AGENT_URL`, `DATABASE_AGENT_URL`, `FRONTEND_AGENT_URL`, `TESTING_AGENT_URL`, `INTEGRATION_AGENT_URL`) and dispatches versioned `TaskPayloadContract_v1` envelopes over HTTP with Bearer Token authentication.
- **Specialized Subclasses:**
  - `FrontendAgent` (`qwen2.5-coder:3b`): UI/UX components (`src/agents/frontend_agent.py`).
  - `BackendAgent` (`qwen2.5-coder:7b`): FastAPI/REST API endpoints with AST validation (`src/agents/backend_agent.py`).
  - `DatabaseAgent` (`llama3.2:3b`): SQLite DDL generation with in-memory SQLite validation (`src/agents/database_agent.py`).
  - `TestingAgent` (`deepseek-coder:6.7b`): Pytest unit test generation with AST assertion checks (`src/agents/testing_agent.py` & `src/master/generated_tests.py`).
  - `IntegrationAgent` (`phi4-mini:3.8b`): AST/SQL inspection, file collision detection, and `IntegrationReportContract_v1` generation (`src/agents/integration_agent.py`).

### E. Sandboxed Workspace, Conflict Resolution & Security (`src/master/workspace.py`, `conflicts.py`, `src/security/`)
- **Workspace Isolation (`workspace.py`):** Confines all physical file writes strictly to `workspaces/{run_id}/` and rejects path traversal (`../`) attempts.
- **Conflict Resolution (`conflicts.py`):** Detects duplicate target paths (`DEDUPLICATED` on identical SHA-256 or `RENAMED` to `<stem>.<task_id><ext>`) and SQL `CREATE TABLE` schema mismatches (`REPORTED`), persisting records to SQLite (`file_conflicts`).
- **Output Sanitization (`src/security/output_sanitizer.py`):** Escapes untrusted model output before UI rendering and masks sensitive authorization headers/tokens before persisting logs or attempt history.

## 3. Communication Protocol & Versioned Contracts (`S3-01`)
All Master–Worker interactions are governed by versioned (`contract_version = "1.0"`) Pydantic v2 contracts in [`src/contracts.py`](../src/contracts.py) and documented in [`docs/INTER_AGENT_CONTRACTS.md`](INTER_AGENT_CONTRACTS.md):
- **Task Envelope (`TaskPayloadContract_v1`):** Built via `build_task_envelope()` and carries `run_id`, `task_id`, `envelope_id`, `category`, `dependencies`, `payload` (including shared domain contract), `timestamps` (`created_at`, `dispatched_at`), `timeout_seconds`, and chained `context_artifacts` (`upstream_artifacts`, `generated_files`).
- **Result Envelope (`WorkerTaskResultContract_v1`):** Returns `run_id`, `task_id`, `agent_id`, `status` (normalized via `normalize_worker_status()`), `output_artifacts`, `logs`, `execution_time_seconds`, and `timestamps` (`completed_at`).
- **Error Envelope (`WorkerErrorContract_v1`):** Standardizes distributed failure codes (`UNAUTHORIZED`, `INVALID_PAYLOAD`, `TIMEOUT`, `DUPLICATE_TASK`, `EXECUTION_ERROR`, `UNREACHABLE`, `UNSAFE_PATH`, `CONTRACT_VIOLATION`) with `retryable` flags and `timestamps` (`occurred_at`).
- **Timeout & Duplicate Message Handling (`DuplicateTaskTracker`):**
  - Enforces per-task `timeout_seconds` on HTTP dispatch and triggers automatic failover on timeout.
  - Prevents duplicate execution of identical `(run_id, task_id)` or `envelope_id` requests (`HTTP 409 Conflict` while `IN_PROGRESS`, or idempotent cached result when already `COMPLETED`).

## 4. System Requirements Traceability

### Sprint 1: Foundation and Requirements
- **REQ-1.1:** The system shall provide a web interface for user interactions.
- **REQ-1.2:** The Master Agent prototype shall register available worker agents and models.
- **REQ-1.3:** The Master Agent shall perform basic task decomposition from input requirements.

### Sprint 2: Agent Management and Task Assignment
- **REQ-2.1:** The system shall maintain agent capability profiles and evaluate model capabilities.
- **REQ-2.2:** The system shall classify tasks and dynamically distribute them using an agent selection algorithm.
- **REQ-2.3:** The interface shall provide real-time agent status monitoring.
  
### Sprint 3: Distributed Development
- **REQ-3.1:** Worker agents shall execute assigned programming tasks independently.
- **REQ-3.2:** The platform shall handle network communication between the Master Agent and worker agents using versioned HTTP/JSON contracts (`v1.0`).
- **REQ-3.3:** The platform shall manage task dependencies (DAG) and collect execution results into an isolated run workspace (`workspaces/{run_id}/`).

### Sprint 4: Integration and Quality Assurance
- **REQ-4.1:** The platform shall integrate code generated by worker agents and perform automated AST/SQL syntax verification.
- **REQ-4.2:** The system shall run automated tests and utilize a Code Review agent (`IntegrationAgent`) with UI review reporting.
- **REQ-4.3:** The Master Agent shall classify errors, resolve file/schema conflicts, and automatically reassign failed tasks via bounded retry and failover.

### Sprint 5: Complete System and Evaluation
- **REQ-5.1:** The platform shall support a complete end-to-end development workflow from requirement prompt to verified deliverable package.
- **REQ-5.2:** The system shall display a telemetry and benchmark dashboard with performance measurements and agent/model comparisons.