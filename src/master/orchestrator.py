"""
Master Agent Orchestrator.
Main entrypoint connecting decomposition, capability evaluation, task scheduling,
contract envelope packaging (S3-01), and local/distributed agent execution.
"""

import logging
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from src.master.analyzer import RequirementsAnalyzer
from src.master.capability_eval import CapabilityEvaluator
from src.master.scheduler import TaskScheduler, DagValidationError  # noqa: F401 (re-exported for callers)
from src.master.workspace import (
    RunWorkspace,
    UnsafePathError,
    DEFAULT_WORKSPACE_ROOT,
    normalize_relative_path,
)
from src.master.conflicts import SchemaConflictDetector
from src.master.retry_policy import RetryPolicy, TRANSIENT, classify_failure, failure_code
from src.agents.base_agent import BaseAgent, TaskCategory, TaskResult, AgentStatus
from src.contracts import (
    CONTRACT_VERSION,
    DEFAULT_TASK_TIMEOUT_SECONDS,
    DuplicateTaskTracker,
    OrchestratorTaskRecordContract_v1,
    OrchestratorTaskStatus,
    WorkerErrorCode,
    build_task_envelope,
    normalize_worker_status,
    validate_master_tasks,
)
from src.master import db_manager
from src.security.error_classification import classify_task_result, ErrorKind
from src.security.input_validation import validate_requirement_text
from src.security.output_sanitizer import redact_secrets, safe_log_message

logger = logging.getLogger(__name__)

# How much generated code the Testing task sees (enough for signatures, short enough for small models)
TEST_CONTEXT_MAX_FILES = 2
TEST_CONTEXT_MAX_CHARS = 1500


def code_excerpts_for_testing(generated_files: Dict[str, str]) -> Dict[str, str]:
    """First part of each generated Python module (test files excluded), so TestingAgent
    writes tests against the real code instead of generic ones."""
    excerpts: Dict[str, str] = {}
    for path in sorted(generated_files):
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        content = generated_files[path]
        if not name.endswith(".py") or name.startswith("test_") or not isinstance(content, str):
            continue
        excerpt = content[:TEST_CONTEXT_MAX_CHARS]
        if len(content) > TEST_CONTEXT_MAX_CHARS:
            excerpt += "\n# ... (truncated)"
        excerpts[path] = excerpt
        if len(excerpts) >= TEST_CONTEXT_MAX_FILES:
            break
    return excerpts


class MasterOrchestrator:
    """Master Agent Orchestrator managing distributed multi-agent software development lifecycle."""

    def __init__(self, evaluator: Optional[CapabilityEvaluator] = None,
                 db_path: Optional[str] = None, persist: bool = True,
                 workspace_root: Optional[str] = None, write_artifacts: Optional[bool] = None,
                 task_timeout: float = DEFAULT_TASK_TIMEOUT_SECONDS,
                 retry_policy: Optional[RetryPolicy] = None, sleep=None,
                 analyzer: Optional[RequirementsAnalyzer] = None, parallel: Optional[bool] = None,
                 max_parallel: Optional[int] = None):
        self.persist = persist
        self.db_path = db_manager.init_db(db_path, verbose=False) if persist else None
        # S4-07: the UI passes RequirementsAnalyzer(use_llm=True); the default is the fixed template
        self.analyzer = analyzer or RequirementsAnalyzer()
        self.evaluator = evaluator or CapabilityEvaluator()
        self.scheduler = TaskScheduler()
        self.duplicate_tracker = DuplicateTaskTracker()
        self.task_timeout = float(task_timeout)
        # S4-01: TRANSIENT failures (remote TIMEOUT / UNREACHABLE) are retried on the same agent
        self.retry_policy = retry_policy or RetryPolicy.from_env()
        self._sleep = sleep or time.sleep
        # S4-07: independent ready tasks go to their agents at the same time (MASTER_PARALLEL_DISPATCH=false: one by one)
        env_parallel = os.environ.get("MASTER_PARALLEL_DISPATCH", "true").strip().lower() not in ("0", "false", "no", "off")
        self.parallel = env_parallel if parallel is None else bool(parallel)
        try:
            env_max = int(os.environ.get("MASTER_MAX_PARALLEL", "4"))
        except ValueError:
            env_max = 4
        self.max_parallel = max(1, int(max_parallel if max_parallel is not None else env_max))
        self._agent_locks: Dict[int, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._workspace_lock = threading.Lock()
        self.execution_history: List[TaskResult] = []
        self.dispatched_envelopes: List[Dict[str, Any]] = []
        # S3-04: agent output files are written only under <workspace_root>/<run_id>/.
        # Default: on for persisted runs, off for in-memory runs unless a root is given.
        self.write_artifacts = (persist or workspace_root is not None) if write_artifacts is None else write_artifacts
        self.workspace_root = self._resolve_workspace_root(workspace_root)

    def _resolve_workspace_root(self, workspace_root: Optional[str]) -> str:
        if workspace_root:
            return os.path.abspath(workspace_root)
        if os.environ.get("WORKSPACE_ROOT"):
            return os.path.abspath(os.environ["WORKSPACE_ROOT"])
        if self.db_path:
            # Keep workspaces next to the state DB (repo root in production, temp dir in tests)
            return os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "workspaces")
        return DEFAULT_WORKSPACE_ROOT

    def _db(self, fn, *args, **kwargs):
        """Runs a persistence call; SQLite I/O errors are logged, never crash the run.
        ValueError (e.g. wrongly COMPLETED record) is intentionally propagated."""
        if not self.persist:
            return None
        try:
            return fn(*args, db_path=self.db_path, **kwargs)
        except sqlite3.Error as exc:
            logger.warning("SQLite persistence failed in %s: %s", fn.__name__, exc)
            return None

    def _agent_ids(self) -> Dict[str, str]:
        return {a.name: a.agent_id for a in self.evaluator.registered_agents}

    def _reset_error_agents(self):
        """Resets agents in ERROR status back to IDLE before a new run begins."""
        for agent in self.evaluator.registered_agents:
            raw_status = getattr(agent.status, "value", str(agent.status))
            if raw_status == "ERROR":
                agent.status = AgentStatus.IDLE


    # ------------------------------------------------------------------ S4-07 parallel dispatch
    def _agent_lock(self, agent) -> threading.Lock:
        """One lock per agent: two parallel tasks never run on the same agent at the same time."""
        with self._locks_guard:
            return self._agent_locks.setdefault(id(agent), threading.Lock())

    def _execute_wave(self, prepared, workspace) -> List[Dict[str, Any]]:
        """Runs the attempts of every prepared task; results come back in the same order."""
        if not prepared:
            return []
        jobs = [(task["task_id"], dispatch_task, ranked) for task, _cat, ranked, dispatch_task in prepared]
        if not self.parallel or len(jobs) < 2:
            return [self._run_attempts(*job, workspace=workspace) for job in jobs]
        logger.info("Dispatching %d independent tasks in parallel: %s", len(jobs), [j[0] for j in jobs])
        with ThreadPoolExecutor(max_workers=min(len(jobs), self.max_parallel)) as pool:
            futures = [pool.submit(self._run_attempts, *job, workspace=workspace) for job in jobs]
            return [f.result() for f in futures]

    def _run_attempts(self, task_id: str, dispatch_task: Dict[str, Any], ranked_candidates, workspace) -> Dict[str, Any]:
        """Failover over the ranked candidates, with bounded retry on TRANSIENT failures (S4-01)."""
        attempted_agents: List[str] = []
        attempt_log: List[Dict[str, Any]] = []
        last_result, last_agent, last_error = None, None, None
        written_files: List[Dict[str, Any]] = []
        succeeded = False

        for candidate in ranked_candidates:
            agent = candidate["agent"]
            with self._agent_lock(agent):
                # A parallel task may have left this agent ERROR / OFFLINE while we waited for it
                if getattr(agent.status, "value", str(agent.status)) in ("ERROR", "OFFLINE"):
                    continue
                retry_no = 0
                while True:
                    attempted_agents.append(agent.name)
                    last_agent = agent

                    result = agent.execute_task(dispatch_task)
                    norm_status = normalize_worker_status(getattr(result, "status", "FAILED"))
                    if hasattr(result, "status") and norm_status == "SUCCESS":
                        result.status = "SUCCESS"
                    self.execution_history.append(result)
                    last_result = result
                    is_successful = norm_status == "SUCCESS"
                    error_message = getattr(result, "error_message", None)

                    raw_files = ((getattr(result, "output_artifacts", None) or {}).get("files")) or []
                    if is_successful and workspace is not None:
                        try:
                            with self._workspace_lock:  # conflict detection keeps a per-run index
                                written_files = workspace.write_files(raw_files, owner=task_id)
                        except UnsafePathError as exc:
                            # The agent answered, but its output cannot be delivered safely
                            is_successful = False
                            error_message = f"Güvensiz çıktı yolu reddedildi: {exc}"
                            written_files = []
                        except OSError as exc:
                            is_successful = False
                            error_message = f"Çıktı dosyaları çalışma alanına yazılamadı: {exc}"
                            written_files = []
                    elif is_successful and raw_files:
                        # Validate relative paths even in in-memory mode (persist=False)
                        try:
                            in_mem_files = []
                            for entry in raw_files:
                                rel_raw = entry.get("filename") or entry.get("path")
                                clean_rel = normalize_relative_path(rel_raw).as_posix()
                                in_mem_files.append({
                                    "relative_path": clean_rel,
                                    "content": str(entry.get("content", "")),
                                })
                            written_files = in_mem_files
                        except UnsafePathError as exc:
                            is_successful = False
                            error_message = f"Güvensiz çıktı yolu reddedildi: {exc}"
                            written_files = []

                    if error_message:
                        error_message = redact_secrets(error_message)
                    last_error = error_message
                    error_code = None if is_successful else failure_code(result, error_message)
                    if is_successful:
                        error_kind = None
                    else:
                        raw_kind = getattr(result, "error_kind", None)
                        if raw_kind in (ErrorKind.TRANSIENT.value, ErrorKind.PERMANENT.value):
                            error_kind = raw_kind
                        else:
                            error_kind = classify_task_result(result, error_message).kind.value
                    attempt_log.append({
                        "agent_id": agent.agent_id,
                        "agent_name": agent.name,
                        "model_used": getattr(agent, "model_name", None),
                        "is_successful": is_successful,
                        "error_message": error_message,
                        "execution_time_seconds": getattr(result, "execution_time_seconds", 0.0),
                        "error_kind": error_kind,
                        "error_code": error_code,
                        "retry_no": retry_no,
                    })

                    if is_successful or error_kind != TRANSIENT or retry_no >= self.retry_policy.max_retries:
                        break
                    # TRANSIENT: same agent once more after a short pause (bounded by max_retries)
                    retry_no += 1
                    logger.info("Retrying %s on %s after %s (retry %d/%d)", task_id, agent.name,
                                error_code, retry_no, self.retry_policy.max_retries)
                    agent.status = AgentStatus.IDLE
                    self._sleep(self.retry_policy.delay_for(retry_no))

                if is_successful:
                    succeeded = True
                    break
                # A worker that only timed out stays usable for later tasks of this run;
                # unreachable or permanently failing agents keep their ERROR status until the next run.
                if error_code == WorkerErrorCode.TIMEOUT.value:
                    agent.status = AgentStatus.IDLE

        return {"attempted_agents": attempted_agents, "attempt_log": attempt_log, "succeeded": succeeded,
                "last_result": last_result, "last_agent": last_agent, "last_error": last_error,
                "written_files": written_files}

    def process_requirement(self, requirement_text: str, project_title: str) -> Dict[str, Any]:
        """
        Full orchestration pipeline:
        1. Reset ERROR agents to IDLE and initialize isolated run_id
        2. Decompose requirement into task DAG
        3. Validate the DAG before execution: structural errors raise DagValidationError;
           cyclic / undefined-dependency tasks and everything downstream are BLOCKED up front
        4. Validate task schemas and build versioned TaskPayloadContract_v1 envelopes
           with run_id, task_id, timeout_seconds, and chained upstream context_artifacts (S3-01)
        5. Evaluate agent capabilities and match tasks with failover support (local or RemoteAgentProxy)
        6. Schedule and execute tasks in topological order; write agent files only
           into workspaces/{run_id}/ (unsafe paths fail the attempt)
        7. Apply deadlock protection for unsatisfied dependencies
        8. Determine dynamic system_status and return comprehensive execution report
        """
        requirement_text = validate_requirement_text(requirement_text)
        self._reset_error_agents()
        run_id = self.scheduler.reset()
        self.duplicate_tracker.clear()
        self.dispatched_envelopes = []

        decomposition = self.analyzer.decompose(requirement_text, project_title)
        tasks = decomposition["tasks"]
        # Rejects the whole run (before anything is persisted or executed) if the graph is malformed
        dag_report = self.scheduler.validate_graph(tasks)
        # Validate task contract schemas (S2-04 / S3-01)
        is_schema_valid, schema_err, _ = validate_master_tasks(tasks)
        if not is_schema_valid:
            logger.warning("Task decomposition schema warning in run %s: %s", run_id, schema_err)

        task_map = {t["task_id"]: t for t in tasks}
        assignments = []
        assignment_by_id = {}
        agent_ids = self._agent_ids()
        workspace = RunWorkspace(run_id, root=self.workspace_root) if self.write_artifacts else None
        project_context = {"project_title": project_title, "requirement": requirement_text}
        # S4-07: every agent gets the same entity / field / endpoint names from the Master model
        if decomposition.get("shared_contract"):
            project_context["shared_contract"] = decomposition["shared_contract"]

        # Track upstream task outputs & generated file contents across the DAG (S3-01 / S3-05 / S4-04)
        completed_task_artifacts: Dict[str, Dict[str, Any]] = {}
        generated_files_by_path: Dict[str, str] = {}
        artifact_sources_by_path: Dict[str, List[str]] = {}
        schema_detector = SchemaConflictDetector()
        run_conflicts: List[Dict[str, Any]] = []

        self._db(db_manager.upsert_agents, self.evaluator.registered_agents)
        self._db(db_manager.create_run, run_id, project_title,
                 requirement_id=decomposition["requirement_id"], total_tasks=len(tasks),
                 workspace_path=str(workspace.path) if workspace else None)

        # Pre-execution DAG rejection: these tasks are never handed to an agent
        for task in tasks:
            task_id = task["task_id"]
            if task_id in dag_report["rejected"]:
                reasons = dag_report["rejected"][task_id]
            elif task_id in dag_report["blocked_downstream"]:
                reasons = [f"bağımlı olduğu görev '{dep}', durum BLOCKED"
                           for dep in dag_report["blocked_downstream"][task_id]]
            else:
                continue
            self.scheduler.mark_blocked(task_id)
            record = self._blocked_record(task, "Çalıştırma öncesi DAG doğrulaması: " + "; ".join(reasons), run_id=run_id)
            assignments.append(record)
            assignment_by_id[task_id] = record
            self._db(db_manager.save_task_result, run_id, task, record, agent_ids=agent_ids)

        while not self.scheduler.is_all_finished(tasks):
            executable_tasks = self.scheduler.get_executable_tasks(tasks)
            if not executable_tasks:
                # No more executable tasks ready, break to deadlock resolution
                break

            # S4-07: 1) prepare every ready task in order (ranking, context, envelope),
            # 2) run the agents - in parallel when several tasks are ready and none depends on another,
            # 3) record the results in order on this thread (scheduler, shared dicts and SQLite stay single-threaded).
            prepared = []
            for task in executable_tasks:
                task_id = task["task_id"]
                category = TaskCategory(task["category"])
                specialty = task.get("required_specialty")

                # Duplicate dispatch check within the same run (S3-01 Item 3)
                dup_state, _ = self.duplicate_tracker.begin(run_id, task_id)
                if dup_state != "NEW":
                    logger.warning("Skipping duplicate dispatch for (%s, %s): state=%s", run_id, task_id, dup_state)
                    continue

                # Evaluate and rank candidates with availability filtering
                ranked_candidates = self.evaluator.evaluate_and_rank(
                    category, required_specialty=specialty, available_only=True
                )

                if not ranked_candidates:
                    self.duplicate_tracker.release(run_id, task_id)
                    self.scheduler.mark_unassigned(task_id)
                    record = self._validate_record(run_id, {
                        "contract_version": CONTRACT_VERSION,
                        "run_id": run_id,
                        "task_id": task_id,
                        "title": task["title"],
                        "assigned_agent": None,
                        "model_used": None,
                        "fit_score": 0.0,
                        "execution_time_seconds": 0.0,
                        "status": "UNASSIGNED",
                        "agent_result_status": None,
                        "reason": f"No available agent found for category '{category.value}'",
                        "attempted_agents": [],
                        "output_files": []
                    })
                    assignments.append(record)
                    assignment_by_id[task_id] = record
                    self._db(db_manager.save_task_result, run_id, task, record, agent_ids=agent_ids)
                    continue

                # Build concise upstream context from completed dependency tasks (excluding bulky raw code strings)
                deps = task.get("dependencies", [])
                upstream_ctx = {}
                for dep_id in deps:
                    if dep_id in completed_task_artifacts:
                        raw_art = completed_task_artifacts[dep_id] or {}
                        compact_art = {
                            k: v for k, v in raw_art.items()
                            if k not in ("files", "generated_code", "generated_sql", "generated_html")
                        }
                        if "files" in raw_art and isinstance(raw_art["files"], list):
                            compact_art["files_generated"] = [
                                f.get("filename") or f.get("path")
                                for f in raw_art["files"]
                                if isinstance(f, dict)
                            ]
                        upstream_ctx[dep_id] = compact_art

                merged_context = {
                    **project_context,
                    **(task.get("context_artifacts") or {}),
                }
                if category != TaskCategory.DATABASE:
                    if upstream_ctx:
                        merged_context["upstream_artifacts"] = upstream_ctx
                    if generated_files_by_path:
                        merged_context["generated_files"] = sorted(generated_files_by_path.keys())
                # Testing needs to see the code it tests: send a short excerpt of the generated
                # Python modules (not the full files, so small models stay within their timeout)
                if category == TaskCategory.TESTING:
                    excerpts = code_excerpts_for_testing(generated_files_by_path)
                    if excerpts:
                        merged_context["code_under_test"] = excerpts

                # Build versioned S3-01 task envelope (includes run_id, task_id, timeout_seconds)
                envelope = build_task_envelope(
                    task,
                    run_id=run_id,
                    context_artifacts=merged_context,
                    timeout_seconds=float(task.get("timeout_seconds", self.task_timeout)),
                )
                dispatch_task = envelope.model_dump()
                # Preserve any extra custom keys from task dict
                for k, v in task.items():
                    if k not in dispatch_task:
                        dispatch_task[k] = v

                # For Integration tasks, pass collected files & sources so IntegrationAgent inspects real outputs
                if category == TaskCategory.INTEGRATION and generated_files_by_path:
                    dispatch_task.setdefault("output_artifacts", dict(generated_files_by_path))
                    dispatch_task.setdefault(
                        "artifact_sources",
                        {p: list(srcs) for p, srcs in artifact_sources_by_path.items()},
                    )
                    if run_conflicts:
                        dispatch_task.setdefault("conflicts_log", list(run_conflicts))

                self.dispatched_envelopes.append(dict(dispatch_task))
                prepared.append((task, category, ranked_candidates, dispatch_task))

            outcomes = self._execute_wave(prepared, workspace)
            for (task, category, _ranked, dispatch_task), outcome in zip(prepared, outcomes):
                task_id = task["task_id"]
                attempted_agents = outcome["attempted_agents"]
                attempt_log = outcome["attempt_log"]
                task_succeeded = outcome["succeeded"]
                last_result = outcome["last_result"]
                last_agent = outcome["last_agent"]
                last_error = outcome["last_error"]
                written_files = outcome["written_files"]

                task_conflicts: List[Dict[str, Any]] = []
                if task_succeeded:
                    self.scheduler.mark_completed(task_id)
                    artifacts_dict = getattr(last_result, "output_artifacts", None) or {}
                    completed_task_artifacts[task_id] = artifacts_dict

                    # Record generated files (using resolved paths if workspace renamed/deduplicated them)
                    raw_files = artifacts_dict.get("files") or []
                    content_by_req = {}
                    for entry in raw_files:
                        if isinstance(entry, dict) and isinstance(entry.get("content"), str):
                            rel_raw = entry.get("filename") or entry.get("path")
                            try:
                                content_by_req[normalize_relative_path(rel_raw).as_posix()] = entry["content"]
                            except UnsafePathError:
                                pass

                    if written_files:
                        for wf in written_files:
                            resolved_rel = wf["relative_path"]
                            req_rel = wf.get("requested_path") or resolved_rel
                            content = wf.get("content") if "content" in wf else content_by_req.get(req_rel, "")
                            conflict = wf.get("conflict")
                            if conflict:
                                task_conflicts.append(conflict)
                            if not (conflict and conflict.get("resolution") == "DEDUPLICATED"):
                                generated_files_by_path[resolved_rel] = content
                                # append, not overwrite: in-memory mode (no workspace) does not rename,
                                # so two producers of one path must stay visible to the IntegrationAgent
                                producers = artifact_sources_by_path.setdefault(resolved_rel, [])
                                if last_agent.name not in producers:
                                    producers.append(last_agent.name)
                            if resolved_rel.endswith(".sql") and content:
                                task_conflicts.extend(schema_detector.check(task_id, resolved_rel, content))
                    else:
                        for clean_rel, content in content_by_req.items():
                            generated_files_by_path[clean_rel] = content
                            artifact_sources_by_path.setdefault(clean_rel, []).append(last_agent.name)
                            if clean_rel.endswith(".sql") and content:
                                task_conflicts.extend(schema_detector.check(task_id, clean_rel, content))

                    run_conflicts.extend(task_conflicts)

                    # Update SQLite review_status on output_files after IntegrationAgent inspects them
                    if category == TaskCategory.INTEGRATION and isinstance(artifacts_dict, dict):
                        review_map: Dict[str, str] = {}
                        for p in artifacts_dict.get("inspected_files") or []:
                            review_map[p] = "APPROVED"
                        for finding in artifacts_dict.get("findings") or []:
                            if not isinstance(finding, dict):
                                continue
                            fp = finding.get("file_path")
                            sev = finding.get("severity")
                            if fp in review_map:
                                if sev == "CRITICAL":
                                    review_map[fp] = "REJECTED"
                                elif sev == "WARNING" and review_map[fp] != "REJECTED":
                                    review_map[fp] = "REVIEW_REQUIRED"
                        if review_map:
                            self._db(db_manager.update_output_file_reviews, run_id, review_map)

                    record = self._validate_record(run_id, {
                        "contract_version": CONTRACT_VERSION,
                        "run_id": run_id,
                        "task_id": task_id,
                        "title": task["title"],
                        "assigned_agent": last_agent.name,
                        "model_used": last_agent.model_name,
                        "fit_score": last_agent.capabilities.calculate_fit_score(category),
                        "execution_time_seconds": last_result.execution_time_seconds,
                        "status": "COMPLETED",
                        "agent_result_status": "SUCCESS",
                        "reason": f"Successfully executed by '{last_agent.name}'",
                        "attempted_agents": attempted_agents,
                        "output_files": [f["relative_path"] for f in written_files] if workspace is not None else []
                    })
                    self.duplicate_tracker.complete(run_id, task_id, record)
                    assignments.append(record)
                    assignment_by_id[task_id] = record
                else:
                    self.duplicate_tracker.release(run_id, task_id)
                    self.scheduler.mark_failed(task_id)
                    err_msg = last_error or "Execution failed"
                    record = self._validate_record(run_id, {
                        "contract_version": CONTRACT_VERSION,
                        "run_id": run_id,
                        "task_id": task_id,
                        "title": task["title"],
                        "assigned_agent": last_agent.name if last_agent else None,
                        "model_used": last_agent.model_name if last_agent else None,
                        "fit_score": last_agent.capabilities.calculate_fit_score(category) if last_agent else 0.0,
                        "execution_time_seconds": last_result.execution_time_seconds if last_result else 0.0,
                        "status": "FAILED",
                        "agent_result_status": "FAILED",
                        "reason": f"All eligible candidate agents failed: {err_msg}",
                        "attempted_agents": attempted_agents,
                        "output_files": []
                    })
                    assignments.append(record)
                    assignment_by_id[task_id] = record

                self._db(db_manager.save_task_result, run_id, task, record,
                         attempts=attempt_log, agent_ids=agent_ids,
                         file_records=written_files if workspace is not None else None,
                         conflicts=task_conflicts)

        # Deadlock protection for remaining unfinished tasks
        processed = self.scheduler.get_processed_tasks()
        remaining_tasks = [t for t in tasks if t["task_id"] not in processed]
        cycle_of = {tid: cycle for cycle in self.scheduler.find_cycles(tasks) for tid in cycle}

        for task in remaining_tasks:
            task_id = task["task_id"]
            deps = task.get("dependencies", [])
            block_reasons = []
            if task_id in cycle_of:
                block_reasons.append(f"döngüsel bağımlılık tespit edildi: {' <-> '.join(cycle_of[task_id])}")

            for dep in deps:
                if dep not in task_map:
                    block_reasons.append(f"bağımlı olduğu görev '{dep}' tanımlı değil")
                elif dep in self.scheduler.failed_tasks:
                    block_reasons.append(f"bağımlı olduğu görev '{dep}', durum FAILED")
                elif dep in self.scheduler.unassigned_tasks:
                    block_reasons.append(f"bağımlı olduğu görev '{dep}', durum UNASSIGNED")
                elif dep in self.scheduler.blocked_tasks:
                    block_reasons.append(f"bağımlı olduğu görev '{dep}', durum BLOCKED")
                elif dep not in self.scheduler.completed_tasks:
                    dep_status = assignment_by_id.get(dep, {}).get("status", "UNSATISFIED")
                    block_reasons.append(f"bağımlı olduğu görev '{dep}', durum {dep_status}")

            if not block_reasons:
                block_reasons.append("Çözülemeyen veya döngüsel bağımlılık")

            reason_str = "; ".join(block_reasons)
            self.scheduler.mark_blocked(task_id)
            record = self._blocked_record(task, reason_str, run_id=run_id)
            assignments.append(record)
            assignment_by_id[task_id] = record
            self._db(db_manager.save_task_result, run_id, task, record, agent_ids=agent_ids)

        # Calculate system status
        completed_count = len(self.scheduler.completed_tasks)
        failed_count = len(self.scheduler.failed_tasks)
        unassigned_count = len(self.scheduler.unassigned_tasks)
        blocked_count = len(self.scheduler.blocked_tasks)
        total_tasks = len(tasks)

        if completed_count == total_tasks:
            system_status = "COMPLETED"
        elif completed_count == 0:
            system_status = "FAILED"
        else:
            system_status = "PARTIALLY_COMPLETED"

        status_counts = {
            "COMPLETED": completed_count,
            "FAILED": failed_count,
            "UNASSIGNED": unassigned_count,
            "BLOCKED": blocked_count
        }
        self._db(db_manager.upsert_agents, self.evaluator.registered_agents)
        self._db(db_manager.finish_run, run_id, system_status, status_counts)

        return {
            "contract_version": CONTRACT_VERSION,
            "run_id": run_id,
            "project_title": project_title,
            "requirement_id": decomposition["requirement_id"],
            "total_tasks_processed": len(assignments),
            "task_assignments": assignments,
            "system_status": system_status,
            "status_counts": {
                "COMPLETED": completed_count,
                "FAILED": failed_count,
                "UNASSIGNED": unassigned_count,
                "BLOCKED": blocked_count
            },
            "workspace_path": str(workspace.path) if workspace else None,
            "conflicts": run_conflicts,
            # S4-07: what the engine actually ran (the UI shows this instead of a second decomposition)
            "decomposition": {
                "mode": decomposition.get("decomposition_mode", "template"),
                "label": decomposition.get("decomposition_label", ""),
                "fallback_reason": decomposition.get("fallback_reason"),
                "shared_contract": decomposition.get("shared_contract"),
                "tasks": tasks,
            },
            "dag_validation": {
                "is_valid": dag_report["is_valid"],
                "cycles": dag_report["cycles"],
                "missing_dependencies": dag_report["missing_dependencies"],
                "rejected_tasks": sorted(dag_report["rejected"]),
                "blocked_downstream": sorted(dag_report["blocked_downstream"]),
            }
        }

    @staticmethod
    def _validate_record(run_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Validates orchestrator task record against OrchestratorTaskRecordContract_v1."""
        OrchestratorTaskRecordContract_v1(
            contract_version=record.get("contract_version", CONTRACT_VERSION),
            run_id=run_id,
            task_id=record["task_id"],
            status=OrchestratorTaskStatus(record["status"]),
            assigned_agent=record.get("assigned_agent"),
            agent_result_status=record.get("agent_result_status"),
            attempted_agents=record.get("attempted_agents", []),
            output_files=record.get("output_files", []),
            error_message=None if record["status"] == "COMPLETED" else record.get("reason"),
        )
        return record

    @classmethod
    def _blocked_record(cls, task: Dict[str, Any], reason: str, run_id: str = "run-blocked") -> Dict[str, Any]:
        return cls._validate_record(run_id, {
            "contract_version": CONTRACT_VERSION,
            "run_id": run_id,
            "task_id": task["task_id"],
            "title": task["title"],
            "assigned_agent": None,
            "model_used": None,
            "fit_score": 0.0,
            "execution_time_seconds": 0.0,
            "status": "BLOCKED",
            "agent_result_status": None,
            "reason": reason,
            "attempted_agents": [],
            "output_files": []
        })
