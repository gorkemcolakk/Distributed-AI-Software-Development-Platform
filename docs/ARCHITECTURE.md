# Distributed AI Software Development Platform Architecture

## 1. System Overview
The **Distributed AI Software Development Platform** is a multi-agent software engineering system designed to automatically analyze high-level software requirements, decompose them into structured dependency-aware subtasks, and dynamically assign those tasks to specialized LLM-based worker agents.

```
+-----------------------------------------------------------------------+
|                            USER INTERFACE                             |
|       Enter Requirement -> View Decomposition DAG -> Live Monitor     |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                             MASTER AGENT                              |
|  +---------------------+  +---------------------+  +---------------+  |
|  | Requirements Engine |  | Capability Evaluator|  | Task Scheduler|  |
|  +---------------------+  +---------------------+  +---------------+  |
+-----------------------------------------------------------------------+
        |                     |                     |               |
        v                     v                     v               v
 +--------------+      +--------------+      +-------------+  +-------------+
 | Frontend Agt |      | Backend Agt  |      | Database Agt|  | Testing Agt |
 | (Claude-3.5) |      | (GPT-4o)     |      | (DeepSeek)  |  | (Llama-3)   |
 +--------------+      +--------------+      +-------------+  +-------------+
        |                     |                     |               |
        +---------------------+---------------------+---------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                         INTEGRATION AGENT                             |
|          Code Review -> Conflict Resolution -> Complete Web App       |
+-----------------------------------------------------------------------+
```

## 2. Core Components

### A. Requirements Analyzer (`src/master/analyzer.py`)
- Receives software requirements document from user.
- Decomposes project into Directed Acyclic Graph (DAG) of subtasks:
  - `task-req-1`: Requirements & Architecture Design
  - `task-db-1`: Database Schema & Migration Definition (depends on `task-req-1`)
  - `task-be-1`: Core Backend API Implementation (depends on `task-db-1`)
  - `task-fe-1`: Frontend User Interface & Components (depends on `task-be-1`)
  - `task-qa-1`: Automated Testing & Quality Assurance (depends on `task-fe-1`)
  - `task-int-1`: Integration, Review & Packaging (depends on `task-qa-1`)

### B. Capability Evaluator & Matching Engine (`src/master/capability_eval.py`)
- Evaluates registered agents based on 3 primary capability dimensions:
  1. **Coding Capability ($C$):** Accuracy, syntax validity, and code formatting (0-100).
  2. **Reasoning Capability ($R$):** Logic decomposition and architectural design (0-100).
  3. **Context Capacity ($K$):** Multi-file awareness and context length tolerance (0-100).

- **Fitness Score Calculation:**
  $$\text{FitScore} = w_C \cdot C + w_R \cdot R + w_K \cdot K + \text{SpecialtyBonus}$$

### C. Worker Agents (`src/agents/`)
- **BaseAgent (`src/agents/base_agent.py`):** Abstract class defining state management, logging, execution lifecycle, and standard JSON task contracts.
- **Specialized Subclasses:**
  - `FrontendAgent`: Optimized for React/CSS UI components.
  - `BackendAgent`: Optimized for FastAPI/REST API endpoints.
  - `DatabaseAgent`: Optimized for SQL DDL and Alembic migrations.
  - `TestingAgent`: Optimized for Pytest and unit test generation.
  - `IntegrationAgent`: Optimized for code review, conflict resolution, and deployment assembly.

## 3. Communication Protocol
- Ajanlar REST API / JSON-RPC veya WebSocket üzerinden Master Agent ile iletişim kurar.
- Görevler ve sonuç nesneleri standardize edilmiş JSON formatındadır.
