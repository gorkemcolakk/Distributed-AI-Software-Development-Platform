# Software Requirements Specification (SRS)
## Distributed AI Software Development Platform
**Course:** CM6453 Software Engineering Process and DevOps[cite: 1]  
**Methodology:** Scrum (5 Iterations / 10 Weeks)[cite: 1]

---

## 1. Introduction

### 1.1 Purpose
The purpose of this document is to define the software requirements for the Distributed AI Software Development Platform. The platform automates end-to-end software development by receiving high-level user requirements, decomposing them into engineering sub-tasks, matching these tasks against distributed LLM worker agents based on their capability profiles, and coordinating their execution across a distributed network.[cite: 1]

### 1.2 Product Scope
The system is a web-based platform that coordinates multiple AI agents to generate software projects. A user submits a project request (such as an Online Library Management System) through a web dashboard. The Master Agent divides this request into smaller tasks, including requirements analysis, frontend development, backend development, database design, and testing. Worker agents running different LLM models are registered in the system, and each task is assigned according to the agent's strengths, such as coding, reasoning, or context handling. In later stages, the platform merges the generated code, runs automated tests, and handles errors automatically.[cite: 1]

---

## 2. Overall Description

### 2.1 Product Perspective
Rather than relying on a single monolithic LLM, this platform distributes programming workloads across specialized LLM agents operating on separate machines or environments. The Master Agent serves as the central coordination engine, while Worker Agents focus on specific software engineering roles (e.g., Model-Y for system architecture, GPT-X for backend logic, and Model-Z for user interface development).[cite: 1]

*(Multi-Agent Distributed LLM Software Development Platform Architecture)*[cite: 1]

### 2.2 Product Features
* **Requirement Input:** A text area where the user enters the software description and requirements.[cite: 1]
* **Task Decomposition:** The Master Agent reads the user's input and splits it into smaller sub-tasks (Requirements Analysis, Frontend, Backend, Database, and QA/Testing).[cite: 1]
* **Viewing Sub-Tasks:** A simple list on the dashboard that lets the user see and open each decomposed task.[cite: 1]
* **Agent List:** A table showing registered worker agents along with their scores (Coding, Reasoning, and Context).[cite: 1]
* **Task Assignment (Sprint 2):** Matching each task with the best agent based on their scores instead of choosing randomly.[cite: 1]

### 2.3 User Classes and System Roles
* **User (Software Lead):** Types the project requirements, clicks the decompose button, and views the generated tasks and agent statuses.[cite: 1]
* **Master Agent:** The central logic engine that decomposes the user prompt into tasks and selects which agent should do which job.[cite: 1]
* **Worker Agent:** A standalone program running a specific LLM model (such as Agent A, Agent B, or Agent C) that receives instructions from the Master Agent and returns code or documents.[cite: 1]

### 2.4 Operating Environment
* **Web Frontend:** Any modern web browser to access the user interface.[cite: 1]
* **Master Agent Backend:** A server runtime environment to handle task decomposition and API routing (exact framework to be finalized during implementation).[cite: 1]
* **Worker Agent Nodes:** Distributed personal computers or machines connected over a local network or the internet.[cite: 1]
* **Project Tools:** Trello for Scrum sprint planning and task tracking; GitHub for version control, code storage, and documentation.[cite: 1]

### 2.5 Design Constraints
* **Independent Agents:** Worker agents must run separately so that an issue on one computer does not crash the main web application.[cite: 1]
* **Standard Scoring:** Capability scores for Coding, Reasoning, and Context must be integers between 0 and 100.[cite: 1]
* **Scrum Schedule:** The project is strictly divided into 5 two-week sprints (10 weeks in total).[cite: 1]

---

## 3. System Features & Functional Requirements

### 3.1 Requirement Input & Task Decomposition
The user submits a software requirement text, and the Master Agent breaks it into engineering sub-tasks.[cite: 1]

* **REQ-1 (Requirement Input Form):** The system provides a multi-line text area on the dashboard where users can write or paste detailed software requirements. *(Target: Sprint 1)*[cite: 1]
* **REQ-2 (Task Decomposition Logic):** The Master Agent analyzes the submitted text and breaks it down into five core engineering sub-tasks: Requirements Analysis, Frontend Development, Backend Development, Database Design, and Quality Assurance & Testing. *(Target: Sprint 1)*[cite: 1]
* **REQ-3 (Sub-Task Display):** The dashboard displays these decomposed tasks as an interactive, expandable list so the user can inspect each item. *(Target: Sprint 1)*[cite: 1]
* **REQ-4 (Decomposition Feedback):** The system shows a visual confirmation message ("Task Decomposition Completed Successfully!") immediately after the decomposition process finishes. *(Target: Sprint 1)*[cite: 1]

### 3.2 Agent Registry and Capabilities
This feature manages the list of connected worker agents and presents their evaluated skill ratings.[cite: 1]

* **REQ-5 (Agent Capability Display):** The dashboard displays a registered agents view showing each agent's ID, model name, specialty domain, and capability scores (Coding, Reasoning, and Context). *(Target: Sprint 1)*[cite: 1]
* **REQ-6 (Score Representation):** Capability metrics for Coding, Reasoning, and Context are represented as whole numbers normalized between 0 and 100. *(Target: Sprint 1)*[cite: 1]

### 3.3 Task Assignment, Remote Execution & Evaluation (Future Sprints)
These requirements describe upcoming development phases planned across future iterations.[cite: 1]

* **REQ-7 (Capability-Based Assignment):** The Master Agent matches and assigns decomposed tasks to agents based on their specific capability strengths instead of picking agents randomly. *(Target: Sprint 2)*[cite: 1]
* **REQ-8 (Distributed Network Communication):** The Master Agent transmits task prompts and instructions to worker agent machines over HTTP REST. *(Target: Sprint 3)*[cite: 1]
* **REQ-9 (Timeout and Error Recovery):** The system detects unresponsive agent nodes and reassigns failed tasks to other available agents. *(Target: Sprint 4)*[cite: 1]
* **REQ-10 (Evaluation Dashboard):** The platform generates a summary dashboard showing agent execution results and model comparisons. *(Target: Sprint 5)*[cite: 1]

---

## 4. External Interface Requirements

### 4.1 User Interface
The web interface is built as a single-page Streamlit dashboard organized into two main visual areas:[cite: 1]
* **Left Panel:** Displays the requirement text input box, the "Analyze and Decompose Requirements" button, the success status message, and the expandable list of decomposed sub-tasks.[cite: 1]
* **Right Panel:** Displays the registered agents list, showing the active worker agents, their specialties, and their capability scores.[cite: 1]

### 4.2 Software and Component Interfaces
* **Streamlit Web UI:** Serves as the frontend application for user interactions and visual task tracking.[cite: 1]
* **Master Agent Service:** Implemented in Python to manage prompt parsing, LLM calls, and task distribution logic.[cite: 1]
* **Worker Agent Nodes:** Independent processes running on distributed machines that communicate with the Master Agent using HTTP REST or WebSockets.[cite: 1]
* **LLM Model APIs:** Remote inference connections to models like GPT-X, Model-Y, and Model-Z to generate code and documentation.[cite: 1]

### 4.3 Communication Interfaces
Network communication between the Master Agent and distributed worker agents will use standard network protocols (such as HTTP, WebSockets, or RPC) to exchange task assignments and generate outputs. The exact data format and communication mechanism will be finalized during implementation.[cite: 1]

---

## 5. Non-Functional Requirements (NFR)

* **NFR-1 (Response Latency):** Upon clicking the analyze button, the web interface shall immediately display a processing or loading indicator to indicate ongoing LLM decomposition, preventing unresponsive UI states.[cite: 1]
* **NFR-2 (Node Fault Isolation):** If a distributed worker agent disconnects or encounters an error, the Master Agent server and the Streamlit interface continue running without interruption.[cite: 1]
* **NFR-3 (System Extensibility):** New worker agents and LLM models can be added by creating a new entry in the registry without needing to modify the core decomposition logic.[cite: 1]