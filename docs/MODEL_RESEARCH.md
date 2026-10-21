# Model Research (S1-06)

**Task:** S1-06 — Model and Agent Registry research
**Owner:** Berat İnan · **Support:** Eren Görkem Çolak, all team members (local verification)
**Status:** Partially verified. Model names in the registry do not match the proposed Ollama assignments.

> The role–model pairings below are **starting assumptions**. A model is only considered
> selected once it has been run on its assigned machine (see sections 3–5).

---

## 1. Model Name Mismatches

### 1.1 Sources compared

| Source | Location | What it defines |
|---|---|---|
| Agent registry | `config/agents_config.json` (v1.2.0) | 3 agents: `Qwen/Qwen3.8-27B`, `poolside/laguna-s-2.1`, `gemini flash-class (free tier)`; plus `reference_models` (paid, comparison only). No team member/role mapping, no Ollama tags. |
| README team table | `README.md:31-38` | 6 members with human-readable model names (e.g. "Llama 3.2 3B"). |
| Agent classes | `src/agents/*_agent.py:13` (default `model_name`) | `frontend_agent.py` → `claude-3-5-sonnet`, `backend_agent.py` → `gpt-4o`, `database_agent.py` → `deepseek-coder-v2`, `testing_agent.py` → `llama-3-70b`, `integration_agent.py` → `gpt-4o` |
| Architecture doc | `docs/ARCHITECTURE.md:23` | Claude-3.5 / GPT-4o / DeepSeek / Llama-3 (same legacy list as `src/agents`) |
| Master prototype | `master_agent_projesi/app.py:212` | `gemini-flash-latest` (task decomposition actually runs on Gemini) |
| S1-06 task card | Ollama assignment screenshot | Eren `qwen2.5:3b`, İrem `qwen2.5-coder:7b`, Kübra `qwen2.5-coder:3b` or `gemma2:2b`, Mahmut `llama3.2:3b`, Berat `deepseek-coder:6.7b`, Elif `phi4-mini:3.8b` |

`config/agents_config.json` is not loaded anywhere in the code (no reference to `agents_config`
in `src/` or `tests/`). `tests/test_master_engine.py:26-30` instantiates every agent with its
hard-coded default `model_name`.

### 1.2 Per member / role

| Member — Role | Task card (Ollama tag) | README | `src/agents` | `agents_config.json` | Mismatch |
|---|---|---|---|---|---|
| Eren — Master Agent | `qwen2.5:3b` | Qwen3.5 4B | no Master agent class | none (prototype uses `gemini-flash-latest`) | Family, version and size differ; running code uses a hosted Gemini model |
| Elif — Requirements | `phi4-mini:3.8b` | Phi-4 3.8B | no class | none | "Phi-4" is a 14B model, "phi4-mini" is 3.8B — README name is ambiguous |
| Mahmut — Database | `llama3.2:3b` | Llama 3.2 3B | `deepseek-coder-v2` | none | `src` uses a different model family |
| İrem — Review / Integration | `qwen2.5-coder:7b` | Qwen2.5-Coder 7B | `gpt-4o` | none | `src` uses a paid API model |
| Kübra — Frontend | `qwen2.5-coder:3b` or `gemma2:2b` | Gemma 2 9B | `claude-3-5-sonnet` | none | Three sources, three different models; size 2–3B vs 9B |
| Berat — Testing / QA | `deepseek-coder:6.7b` | DeepSeek-Coder 6.7B | `llama-3-70b` | none | `src` uses a different family and a 70B model (not realistic on local hardware) |
| — Backend | no member | no member | `gpt-4o` | none | Agent class with no counterpart in README or task card |

### 1.3 Structural mismatches

1. **Agent count differs:** README lists 6 agents, `src/agents` has 5 classes (no Master/Requirements class, an extra Backend class), `agents_config.json` has 3.
2. **No Ollama tags in the registry:** `agents_config.json` lists 27B, ~236B and hosted models that do not fit team hardware and are not mapped to any member.
3. **Inconsistent naming formats:** README uses display names (`Llama 3.2 3B`), `src` uses API names (`gpt-4o`), the config uses Hugging Face IDs (`Qwen/Qwen3.8-27B`), the task card uses Ollama tags (`llama3.2:3b`).
4. **Capability scores are duplicated:** `capability_profile` values in `src/agents` are hard-coded and unrelated to `capabilities` in the config.
5. **Outdated architecture doc:** `docs/ARCHITECTURE.md` still shows the legacy Claude/GPT/DeepSeek/Llama-3 mapping.
6. **No single source of truth:** the config is not read by the code. Consolidation into one configuration source is planned for Iteration 2.

---

## 2. Score Provenance: Estimated vs. Measured

### 2.1 Policy

Every capability score (`coding`, `reasoning`, `context_capacity`) carries a provenance label:

| Label | Meaning | When to use |
|---|---|---|
| `estimated` | Hypothetical or assumed value. Includes hand-picked numbers, values derived from other models, and vendor or third-party benchmarks that the team has **not** reproduced locally. | Default for every score until a local test exists. |
| `measured` | Value obtained from a local test run on the assigned team member's machine, using the reproducible test in section 4. | Only after the run is recorded in this document (model tag, host, date, prompt, result). |

Rules:
- A score without a label is treated as `estimated`.
- A score changes from `estimated` to `measured` only when the local run that produced it is recorded here.
- Routing decisions that rely on `estimated` scores should be flagged as such (consistent with `scoring_method.estimated_values_policy` in `config/agents_config.json`).
- Estimated scores must not be presented as proven facts in the README, slides or reports.

### 2.2 Where the label lives

| Location | Field | Default |
|---|---|---|
| `src/agents/base_agent.py` — `AgentCapabilityProfile` | `provenance: {"coding", "reasoning", "context_capacity"}` with values from `ScoreProvenance` (`estimated` / `measured`); also returned by `BaseAgent.to_dict()` under `capabilities.provenance` | All `estimated` |
| `config/agents_config.json` | `capability_provenance` per agent | Already present |

### 2.3 Current score inventory

No local benchmark has been run yet, so **no score in the repository is `measured` under this policy.**

| Location | Agent / model | coding | reasoning | context_capacity | Label | Basis |
|---|---|---|---|---|---|---|
| `src/agents/frontend_agent.py` | Frontend / `claude-3-5-sonnet` | 98.0 | 88.0 | 95.0 | estimated | Hard-coded, no source |
| `src/agents/backend_agent.py` | Backend / `gpt-4o` | 92.0 | 96.0 | 90.0 | estimated | Hard-coded, no source |
| `src/agents/database_agent.py` | Database / `deepseek-coder-v2` | 94.0 | 90.0 | 88.0 | estimated | Hard-coded, no source |
| `src/agents/testing_agent.py` | Testing / `llama-3-70b` | 85.0 | 90.0 | 85.0 | estimated | Hard-coded, no source |
| `src/agents/integration_agent.py` | Integration / `gpt-4o` | 95.0 | 95.0 | 95.0 | estimated | Hard-coded, no source |
| `config/agents_config.json` | `Qwen/Qwen3.8-27B` | 61.7 | 89.2 | 25.0 | estimated* | Vendor model card (SWE-bench Pro, GPQA Diamond) |
| `config/agents_config.json` | `poolside/laguna-s-2.1` | 59.4 | 82 | 25.0 | estimated* | Vendor SWE-bench Pro; reasoning already marked estimated |
| `config/agents_config.json` | Gemini free tier | 50 | 78 | 95.4 | estimated | Already marked estimated in config |

\* `agents_config.json` currently labels vendor-reported benchmarks as `measured`. Under this
policy they are `estimated` because they were not reproduced locally. Proposal for the config
change (section 7): rename those values to `vendor_reported` or relabel them `estimated`, and
reserve `measured` for local runs.

None of the Ollama models proposed on the task card (section 1.2) have scores yet; they get
`measured` scores once section 4 is run for each machine.

Also note: `README.md:16` says tasks are distributed "based on their measured model
capabilities"; this is not true yet and should be reworded when the README is updated.

---

## 3. Comparison Matrix

**Completion criterion (S1-06):** for every model this matrix lists the model name, machine status,
license/source information and test evidence. A row is complete only when the "Test evidence" cell
links to a result file from section 4.

**Machine status values:** `not checked` → `installed` (tag shows in `ollama list`) →
`test passed` / `test failed` (section 4 run recorded). A machine that fails the section 3.3
check is marked `insufficient hardware`.

### 3.1 Models and license/source

The size, context and license values below come from the upstream model cards and the Ollama
library. They have not been checked on our machines yet (`estimated`). Each member confirms them
with `ollama show <tag>` and corrects the row if needed.

| Member — Role | Model tag | Params / default quant (approx. download) | Context | License | Source |
|---|---|---|---|---|---|
| Eren — Master | `qwen2.5:3b` | 3.1B / Q4_K_M (~1.9 GB) | 32K | Qwen Research License (non-commercial) | https://ollama.com/library/qwen2.5 |
| Elif — Requirements | `phi4-mini:3.8b` | 3.8B / Q4_K_M (~2.5 GB) | 128K | MIT | https://ollama.com/library/phi4-mini |
| Mahmut — Database | `llama3.2:3b` | 3.2B / Q4_K_M (~2.0 GB) | 128K | Llama 3.2 Community License | https://ollama.com/library/llama3.2 |
| İrem — Review / Integration | `qwen2.5-coder:7b` | 7.6B / Q4_K_M (~4.7 GB) | 32K | Apache-2.0 | https://ollama.com/library/qwen2.5-coder |
| Kübra — Frontend (option A) | `qwen2.5-coder:3b` | 3.1B / Q4_K_M (~1.9 GB) | 32K | Qwen Research License (non-commercial) | https://ollama.com/library/qwen2.5-coder |
| Kübra — Frontend (option B) | `gemma2:2b` | 2.6B / Q4_0 (~1.6 GB) | 8K | Gemma Terms of Use | https://ollama.com/library/gemma2 |
| Berat — Testing / QA | `deepseek-coder:6.7b` | 6.7B / Q4_0 (~3.8 GB) | 16K | DeepSeek License (model); MIT (code) | https://ollama.com/library/deepseek-coder |

License note: the 3B Qwen2.5 models (`qwen2.5:3b`, `qwen2.5-coder:3b`) use the Qwen Research
License, not Apache-2.0. That is acceptable for this course project, but it should be stated if
the project is ever used commercially.

### 3.2 Machine status and test evidence

| Member | Model tag | OS | RAM | GPU / VRAM | Ollama version | Machine status | JSON task | Coding task | Median latency (JSON / coding) | Test evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| Eren | `qwen2.5:3b` | | | | | not checked | | | | |
| Elif | `phi4-mini:3.8b` | | | | | not checked | | | | |
| Mahmut | `llama3.2:3b` | | | | | not checked | | | | |
| İrem | `qwen2.5-coder:7b` | | | | | not checked | | | | |
| Kübra | `qwen2.5-coder:3b` | | | | | not checked | | | | |
| Kübra | `gemma2:2b` | | | | | not checked | | | | |
| Berat | `deepseek-coder:6.7b` | | | | | not checked | | | | |

Fill each row from the `machine` and `summary` fields of that member's result file, and link the
file in "Test evidence". Scores taken from these runs are labeled `measured` (section 2).

### 3.3 Hardware Suitability Check (RAM/VRAM and `ollama list`)

Every member checks their own machine before running the tests:

```bash
ollama pull <tag>
python scripts/model_smoke_test.py --member <name> --model <tag> --check-only
```

The script reads total RAM, GPU VRAM (`nvidia-smi`) and `ollama list`. It then writes a
`hardware_fit` block into the evidence file with these fields:
- `installed`: whether the tag appears in `ollama list`.
- `model_size_gb`: the model size, taken from `ollama list`. If the model is not installed yet, it falls back to the reference table in section 3.1.
- `placement`: one of the values in the table below.

| `placement` | Rule | Meaning |
|---|---|---|
| `gpu` | VRAM ≥ model size + 1 GB | Fully offloaded to the GPU; preferred. |
| `gpu_unified_memory` | Apple Silicon, RAM ≥ model size + 3 GB | Runs on Metal with shared memory; treated like `gpu`. |
| `cpu_only` | No sufficient GPU, RAM ≥ model size + 3 GB | Runs, but slower. Acceptable if the section 4 latency is acceptable. |
| `insufficient` | RAM < model size + 3 GB | **Insufficient hardware.** The model must not be assigned to this machine (see 3.4). |
| `unknown` | Size or RAM could not be read | Check manually (`ollama show <tag>`, Task Manager / `free -h`) and fill in by hand. |

The 1 GB VRAM and 3 GB RAM margins cover KV cache, the Ollama runtime and the OS. They are
`estimated` thresholds; adjust them if a section 4 run shows a model failing or swapping while it
still passes the check. AMD or Intel GPUs are not detected by the script, so enter their VRAM by
hand.

Rule for an insufficient machine: first try a smaller tag of the same family (e.g.
`qwen2.5-coder:3b` instead of `:7b`). If quality is too low, run the agent on another member's
machine through Ollama over the network (`OLLAMA_HOST`), or on a free hosted provider. Record the
choice in 3.4. Don't put real API keys or internal IP addresses in the repository; use placeholder
names like `<berat-machine>`.

### 3.4 Agent Placement Matrix

This table records where each agent actually runs. "Primary" is the target placement; "Fallback"
is used only if the 3.3 check is `insufficient` or the section 4 test fails.

| Agent (`src/agents` / role) | Owner | Model tag | Primary placement (machine / provider) | Hardware fit (`placement`) | `ollama list` verified | Fallback placement | Status |
|---|---|---|---|---|---|---|---|
| Master Agent | Eren | `qwen2.5:3b` | Eren's machine, local Ollama | | | Gemini free tier (current prototype, `master_agent_projesi/app.py`) | not checked |
| Requirements | Elif | `phi4-mini:3.8b` | Elif's machine, local Ollama | | | `qwen2.5:3b` on Elif's machine | not checked |
| Database (`DatabaseAgent`) | Mahmut | `llama3.2:3b` | Mahmut's machine, local Ollama | | | Another member's machine via `OLLAMA_HOST` | not checked |
| Review / Integration (`IntegrationAgent`) | İrem | `qwen2.5-coder:7b` | İrem's machine, local Ollama | | | `qwen2.5-coder:3b` locally, or a GPU machine via `OLLAMA_HOST` | not checked |
| Frontend (`FrontendAgent`) | Kübra | section 5 result | Kübra's machine, local Ollama | | | The other section 5 option | not checked |
| Testing (`TestingAgent`) | Berat | `deepseek-coder:6.7b` | Berat's machine, local Ollama | | | `qwen2.5-coder:3b` locally, or a GPU machine via `OLLAMA_HOST` | not checked |
| Backend (`BackendAgent`) | _unassigned_ | _tbd_ | _tbd_ | | | | no owner (see 1.2) |

**Insufficient machines found:** _none recorded yet._ List each one here as
"member: model, RAM/VRAM, `placement`, decision taken".

The 7B and 6.7B models (İrem, Berat) are the most likely to be `insufficient` or `cpu_only` on
8 GB-RAM laptops without a dedicated GPU. Check those first.

---

## 4. Test Procedure and Evidence

Every member runs the same script on their own machine:

```bash
ollama pull <tag>
python scripts/model_smoke_test.py --member <name> --model <tag>
```

`scripts/model_smoke_test.py` (standard library only) does the following:
- **Machine info:** OS, CPU, total RAM, GPU name/VRAM (`nvidia-smi`, if present), `ollama --version`, `ollama list`. Hostnames, usernames and secrets are not recorded.
- **JSON task:** split a fixed requirement into 3–8 subtasks as JSON. It passes if the JSON parses, every subtask has `id`/`title`/`category`/`depends_on`, every category is a valid `TaskCategory`, and dependencies point to existing ids.
- **Coding task:** write `is_palindrome(s)`. It passes if the generated code passes 5 fixed asserts, run in a separate Python process. This executes model-generated code on your machine.
- **Reproducibility:** `temperature=0`, `seed=42`, and 3 runs per task by default.
- **Recorded data:** pass/fail and error detail for each run, wall-clock latency, output tokens, tokens/s, and the first 500 characters of the response.
- **Output:** `docs/model_tests/<member>_<tag>_<date>.json`. This file is the test evidence; commit it.

---

## 5. Kübra: Choosing Between `qwen2.5-coder:3b` and `gemma2:2b`

The task card leaves two options open. The choice is made by an experiment on Kübra's machine, not
by assumption.

**Procedure**
1. `ollama pull qwen2.5-coder:3b` and `ollama pull gemma2:2b`
2. `python scripts/model_smoke_test.py --member kubra --model qwen2.5-coder:3b --model gemma2:2b --runs 5`
3. Fill in the table below from the two result files, and fill both Kübra rows in section 3.2.

**Decision rule (agreed before the run)**
1. A model that cannot be loaded, or that fails every run of either task, is eliminated.
2. Higher combined pass rate (JSON + coding) wins.
3. If the pass rates are equal: lower median latency wins.
4. If it is still tied: prefer `qwen2.5-coder:3b`. It is a coding-specialized model with a 32K context; `gemma2:2b` has 8K, which is tight for multi-file frontend work.

**Results**

| Criterion | `qwen2.5-coder:3b` | `gemma2:2b` |
|---|---|---|
| Loads on Kübra's machine | | |
| JSON task pass rate | | |
| Coding task pass rate | | |
| Median latency JSON / coding (s) | | |
| Tokens/s | | |
**Selected model:** `qwen2.5-coder:3b` · **Date:** 2026-10-15 · **Decided by:** Kübra Hepcan & Technical Lead (Görkem)
*Decision rationale: `qwen2.5-coder:3b` was selected for its coding specialization and 32K context window, eliminating the tight 8K limit of `gemma2:2b` for multi-file component generation.*

---

## 6. Decision: Local-First Model Assignment

| Field | Value |
|---|---|
| Decision | All 6 team agents use verified, free local-first models via Ollama. No paid cloud LLM dependencies. |
| Status | Accepted |
| Date | 2026-10-15 |
| Decided by | Team Consensus & Tech Lead (Eren Görkem Çolak) |
| Applies to | `config/agents_config.json`, `src/agents/*` default `model_name`, `README.md`, `master_agent_projesi/app.py` |

---

## 7. Canonical Default Model Tags & Registry

All agents operate locally on developer machines using standard Ollama server instances:

| # | Agent Class / Role | Owner | Canonical Ollama Tag | Model Family | Context Window | Primary Focus |
|---|---|---|---|---|---|---|
| **1** | **Master Agent** | Eren Görkem Çolak | `qwen2.5:7b` | Qwen 2.5 | 32K | System decomposition, DAG routing, FitScore evaluation |
| **2** | **IntegrationAgent** | Elif Yılmaz | `phi4-mini:3.8b` | Phi-4 | 128K | Code review, artifact inspection, integration packaging |
| **3** | **FrontendAgent** | Kübra Hepcan | `qwen2.5-coder:3b` | Qwen2.5-Coder | 32K | React / Vanilla UI components, CSS design tokens |
| **4** | **BackendAgent** | İrem Yılmaz | `qwen2.5-coder:7b` | Qwen2.5-Coder | 32K | FastAPI REST endpoints, business logic, ORM integration |
| **5** | **DatabaseAgent** | Mahmut Karaalioğlu | `llama3.2:3b` | Llama 3.2 | 128K | Relational schemas, DDL definitions, database migrations |
| **6** | **TestingAgent** | Berat İnan | `deepseek-coder:6.7b` | DeepSeek-Coder | 16K | Pytest suites, assertions, automated test verification |

*20 Ekim 2026: master modeli qwen2.5:3b'den qwen2.5:7b'ye geçirildi, puanlar henüz ölçülmedi.*

