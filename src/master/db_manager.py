"""
SQLite Persistence Layer (S1-04, S2-07, S3-04, S4-04).

Stores run lifecycle (run_id), agent capability profiles, per-run task
statuses and execution attempts. S3-04 adds the run workspace directory
(runs.workspace_path) and the files each task wrote into it (tasks.output_files).
S4-04 adds the output_files table (path, size, SHA-256, review status),
the file_conflicts table (path / schema conflicts and how they were resolved)
and attempts.model_used.
See docs/DATA_MODEL.md for the schema.
"""

import ctypes
import json
import logging
import os
import sqlite3
import sys
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# Veritabanı dosyasını projenin ana dizinine state.db olarak kaydeder.
# STATE_DB_PATH ortam değişkeni ile (ör. testlerde) farklı bir dosya kullanılabilir.
DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../state.db'))
DB_PATH = os.environ.get("STATE_DB_PATH", DEFAULT_DB_PATH)

# Şema sürümü: PRAGMA user_version içinde tutulur.
# v3 (S3-04): runs.workspace_path + tasks.output_files
# v4 (S4-04): output_files + file_conflicts tabloları, attempts.model_used
# v5 (S4):    runs.owner_pid + ABORTED durumu (yarıda kalan RUNNING kayıtlarının kurtarılması)
SCHEMA_VERSION = 5
DEFAULT_STALE_RUN_TIMEOUT_SECONDS = 1800  # 30 dakika

AGENT_STATUSES = ("IDLE", "BUSY", "OFFLINE", "ERROR")
TASK_STATUSES = ("PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "UNASSIGNED", "BLOCKED")
TERMINAL_FAILURE_STATUSES = ("FAILED", "UNASSIGNED", "BLOCKED")
RUN_STATUSES = ("RUNNING", "COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "ABORTED")
REVIEW_STATUSES = ("PENDING", "APPROVED", "REVIEW_REQUIRED", "REJECTED")
CONFLICT_TYPES = ("PATH", "SCHEMA")
CONFLICT_RESOLUTIONS = ("RENAMED", "DEDUPLICATED", "REPORTED")

EXPECTED_TABLES = ("runs", "agents", "tasks", "attempts", "output_files", "file_conflicts")


def _stale_run_timeout() -> int:
    raw = os.environ.get("STALE_RUN_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return DEFAULT_STALE_RUN_TIMEOUT_SECONDS
    try:
        return max(0, int(raw.strip()))
    except ValueError:
        return DEFAULT_STALE_RUN_TIMEOUT_SECONDS


def _is_pid_alive(pid: Optional[int]) -> bool:
    """Cross-platform check for whether an OS process with ``pid`` is still running."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process_query_limited = 0x1000
        still_active = 259
        handle = kernel32.OpenProcess(process_query_limited, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED -> process exists
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False


def _sql_in(values: Iterable[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _resolve_path(db_path: Optional[str]) -> str:
    return db_path or os.environ.get("STATE_DB_PATH", DB_PATH)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    # Asenkron çalışan ajanların aynı bağlantıyı kullanmasına izin verir
    conn = sqlite3.connect(_resolve_path(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Kilitlenmeleri (Database is locked hatasını) önlemek için WAL modunu aktif eder
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA foreign_keys=ON;')
    return conn


def _table_columns(cursor: sqlite3.Cursor, table: str) -> List[str]:
    return [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]


def _migrate_legacy_schema(cursor: sqlite3.Cursor):
    """
    Sprint 1 şemasındaki (run_id içermeyen) tabloları silmek yerine
    '<tablo>_legacy_v1' olarak yeniden adlandırır; yeni şema temiz oluşturulur.
    """
    legacy_markers = {"tasks": "run_id", "agents": "agent_id"}
    for table, required_col in legacy_markers.items():
        cols = _table_columns(cursor, table)
        if cols and required_col not in cols:
            cursor.execute(f"DROP TABLE IF EXISTS {table}_legacy_v1")
            cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy_v1")


# Columns added after v2. Existing databases get them through ALTER TABLE (data kept).
_ADDED_COLUMNS = {
    "runs": [("workspace_path", "TEXT"), ("owner_pid", "INTEGER")],
    "tasks": [("output_files", "TEXT DEFAULT '[]'")],
    "attempts": [("model_used", "TEXT")],
}


def _add_missing_columns(cursor: sqlite3.Cursor):
    for table, columns in _ADDED_COLUMNS.items():
        existing = _table_columns(cursor, table)
        for name, ddl in columns:
            if existing and name not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


_RUNS_TABLE_COLS = (
    "run_id", "project_title", "requirement_id", "system_status",
    "total_tasks", "completed_count", "failed_count", "unassigned_count",
    "blocked_count", "workspace_path", "owner_pid", "started_at", "finished_at",
)


def _runs_table_ddl(table_name: str = "runs") -> str:
    return f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            run_id TEXT PRIMARY KEY,
            project_title TEXT,
            requirement_id TEXT,
            system_status TEXT NOT NULL DEFAULT 'RUNNING'
                CHECK (system_status IN ({_sql_in(RUN_STATUSES)})),
            total_tasks INTEGER DEFAULT 0,
            completed_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            unassigned_count INTEGER DEFAULT 0,
            blocked_count INTEGER DEFAULT 0,
            workspace_path TEXT,
            owner_pid INTEGER,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP
        )
    '''


def _migrate_runs_check_for_aborted(conn: sqlite3.Connection):
    """
    Existing v2-v4 databases have a CHECK constraint on `runs.system_status` that
    does not include 'ABORTED'. Rebuild `runs` in-place with foreign_keys=OFF so
    child rows in tasks/attempts/output_files/file_conflicts stay intact.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='runs'"
    ).fetchone()
    if not row or not row[0]:
        return
    ddl = row[0]
    if "'ABORTED'" in ddl or "CHECK" not in ddl.upper():
        return

    existing_cols = _table_columns(conn.cursor(), "runs")
    common = [c for c in existing_cols if c in _RUNS_TABLE_COLS]
    if not common:
        return
    col_list = ", ".join(common)

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS runs_v5_new")
        conn.execute(_runs_table_ddl("runs_v5_new"))
        conn.execute(f"INSERT INTO runs_v5_new ({col_list}) SELECT {col_list} FROM runs")
        conn.execute("DROP TABLE runs")
        conn.execute("ALTER TABLE runs_v5_new RENAME TO runs")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")


def init_db(db_path: Optional[str] = None, verbose: bool = True,
            recover_stale: bool = True) -> str:
    """Creates all tables idempotently (CREATE TABLE IF NOT EXISTS) and recovers stale RUNNING runs."""
    path = _resolve_path(db_path)
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        current_version = cursor.execute("PRAGMA user_version").fetchone()[0]
        if current_version < SCHEMA_VERSION:
            _migrate_legacy_schema(cursor)

        # Çalıştırma (Run) Tablosu: Her orchestrator çağrısı izole bir run_id alır
        cursor.execute(_runs_table_ddl("runs"))

        # Ajan Profilleri Tablosu (Yetenek skorları + anlık durum)
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                model_name TEXT,
                coding_score REAL CHECK (coding_score BETWEEN 0 AND 100),
                reasoning_score REAL CHECK (reasoning_score BETWEEN 0 AND 100),
                context_capacity REAL CHECK (context_capacity BETWEEN 0 AND 100),
                specialties TEXT DEFAULT '[]',
                provenance TEXT DEFAULT '{{}}',
                status TEXT NOT NULL DEFAULT 'IDLE'
                    CHECK (status IN ({_sql_in(AGENT_STATUSES)})),
                current_task_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Görevler Tablosu (Task Decomposition sonrası görevler run_id ile buraya düşer)
        # CHECK: COMPLETED yalnızca ajan sonucu SUCCESS ise ve bir ajan atanmışsa yazılabilir.
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                title TEXT,
                description TEXT,
                category TEXT,
                required_capability TEXT,
                dependencies TEXT DEFAULT '[]',
                assigned_agent_id TEXT,
                assigned_agent_name TEXT,
                model_used TEXT,
                fit_score REAL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ({_sql_in(TASK_STATUSES)})),
                agent_result_status TEXT
                    CHECK (agent_result_status IS NULL OR agent_result_status IN ('SUCCESS', 'FAILED')),
                reason TEXT,
                attempted_agents TEXT DEFAULT '[]',
                output_files TEXT DEFAULT '[]',
                execution_time_seconds REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (run_id, task_id),
                CHECK (status != 'COMPLETED'
                       OR (agent_result_status = 'SUCCESS' AND assigned_agent_name IS NOT NULL)),
                FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_agent_id) REFERENCES agents (agent_id)
            )
        ''')

        # Deneme (Attempt) Tablosu: Failover sırasında her ajan denemesi kaydedilir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                agent_id TEXT,
                agent_name TEXT,
                attempt_no INTEGER NOT NULL,
                is_successful INTEGER NOT NULL CHECK (is_successful IN (0, 1)),
                error_message TEXT,
                execution_time_seconds REAL DEFAULT 0.0,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id, task_id) REFERENCES tasks (run_id, task_id) ON DELETE CASCADE
            )
        ''')

        # S4-04: Üretilen dosya özetleri (içerik diske yazılır, burada yalnızca özet tutulur)
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS output_files (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                agent_name TEXT,
                relative_path TEXT NOT NULL,
                requested_path TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
                sha256 TEXT CHECK (sha256 IS NULL OR length(sha256) = 64),
                review_status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (review_status IN ({_sql_in(REVIEW_STATUSES)})),
                conflict_resolution TEXT
                    CHECK (conflict_resolution IS NULL OR conflict_resolution IN ({_sql_in(CONFLICT_RESOLUTIONS)})),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (run_id, task_id, relative_path),
                FOREIGN KEY (run_id, task_id) REFERENCES tasks (run_id, task_id) ON DELETE CASCADE
            )
        ''')

        # S4-04: Dosya yolu / şema çakışmaları ve nasıl çözüldükleri
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS file_conflicts (
                conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                conflict_type TEXT NOT NULL CHECK (conflict_type IN ({_sql_in(CONFLICT_TYPES)})),
                file_path TEXT NOT NULL,
                resolved_path TEXT,
                other_task_id TEXT,
                resolution TEXT NOT NULL CHECK (resolution IN ({_sql_in(CONFLICT_RESOLUTIONS)})),
                detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id, task_id) REFERENCES tasks (run_id, task_id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_run_status ON tasks (run_id, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attempts_run_task ON attempts (run_id, task_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_output_files_run ON output_files (run_id, relative_path)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_conflicts_run ON file_conflicts (run_id)')

        # Başarısız/engellenmiş bir görevin aynı run içinde sonradan COMPLETED'a çekilmesini engeller
        cursor.execute(f'''
            CREATE TRIGGER IF NOT EXISTS trg_tasks_no_failed_to_completed
            BEFORE UPDATE OF status ON tasks
            WHEN OLD.status IN ({_sql_in(TERMINAL_FAILURE_STATUSES)}) AND NEW.status = 'COMPLETED'
            BEGIN
                SELECT RAISE(ABORT, 'Terminal failure status cannot transition to COMPLETED');
            END
        ''')

        _add_missing_columns(cursor)
        _migrate_runs_check_for_aborted(conn)
        cursor.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()

    recovered: List[Dict[str, Any]] = []
    if recover_stale:
        recovered = recover_stale_runs(db_path=path)

    if verbose:
        print(f"SQLite veritabanı başarıyla başlatıldı: {path}")
        if recovered:
            print(f"  [KURTARILDI] {len(recovered)} adet yarıda kalan RUNNING kaydı kapatıldı.")
    return path


def verify_schema(db_path: Optional[str] = None) -> Dict[str, bool]:
    """Returns {table_name: exists} for all expected tables."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        existing = {r["name"] for r in rows}
        return {t: t in existing for t in EXPECTED_TABLES}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_task_record(record: Dict[str, Any]):
    """
    Python-level guard (DB CHECK constraint is the second layer):
    a task may only be persisted as COMPLETED if the agent result was SUCCESS.
    """
    status = record.get("status")
    if status not in TASK_STATUSES:
        raise ValueError(f"Invalid task status '{status}' for task '{record.get('task_id')}'")
    if status == "COMPLETED":
        if record.get("agent_result_status") != "SUCCESS" or not record.get("assigned_agent"):
            raise ValueError(
                f"Task '{record.get('task_id')}' cannot be stored as COMPLETED "
                f"(agent_result_status={record.get('agent_result_status')!r}, "
                f"assigned_agent={record.get('assigned_agent')!r})"
            )


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def _status_value(status: Any) -> str:
    return getattr(status, "value", str(status))


def upsert_agent(agent: Any, db_path: Optional[str] = None):
    """Inserts or updates an agent capability profile (accepts BaseAgent)."""
    upsert_agents([agent], db_path=db_path)


def upsert_agents(agents: Iterable[Any], db_path: Optional[str] = None):
    conn = get_connection(db_path)
    try:
        for agent in agents:
            caps = agent.capabilities
            current_task = agent.current_tasks[0] if getattr(agent, "current_tasks", None) else None
            conn.execute('''
                INSERT INTO agents (agent_id, name, model_name, coding_score, reasoning_score,
                                    context_capacity, specialties, provenance, status,
                                    current_task_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(agent_id) DO UPDATE SET
                    name = excluded.name,
                    model_name = excluded.model_name,
                    coding_score = excluded.coding_score,
                    reasoning_score = excluded.reasoning_score,
                    context_capacity = excluded.context_capacity,
                    specialties = excluded.specialties,
                    provenance = excluded.provenance,
                    status = excluded.status,
                    current_task_id = excluded.current_task_id,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                agent.agent_id, agent.name, agent.model_name,
                caps.coding_score, caps.reasoning_score, caps.context_capacity,
                json.dumps(list(caps.specialties)), json.dumps(dict(caps.provenance)),
                _status_value(agent.status), current_task,
            ))
        conn.commit()
    finally:
        conn.close()


def create_run(run_id: str, project_title: str, requirement_id: Optional[str] = None,
               total_tasks: int = 0, workspace_path: Optional[str] = None,
               owner_pid: Optional[int] = None, db_path: Optional[str] = None):
    pid = os.getpid() if owner_pid is None else owner_pid
    conn = get_connection(db_path)
    try:
        conn.execute('''
            INSERT INTO runs (run_id, project_title, requirement_id, total_tasks, workspace_path,
                              owner_pid, system_status)
            VALUES (?, ?, ?, ?, ?, ?, 'RUNNING')
        ''', (run_id, project_title, requirement_id, total_tasks, workspace_path, pid))
        conn.commit()
    finally:
        conn.close()


def save_task_result(run_id: str, task: Dict[str, Any], record: Dict[str, Any],
                     attempts: Optional[List[Dict[str, Any]]] = None,
                     agent_ids: Optional[Dict[str, str]] = None,
                     file_records: Optional[List[Dict[str, Any]]] = None,
                     conflicts: Optional[List[Dict[str, Any]]] = None,
                     db_path: Optional[str] = None):
    """
    Persists a task's terminal record (and its attempts, output file metadata,
    and detected conflicts) for a run.
    `record` is the assignment dict produced by MasterOrchestrator.
    Raises ValueError if the record would wrongly mark a task COMPLETED.
    """
    validate_task_record(record)
    agent_ids = agent_ids or {}
    agent_name = record.get("assigned_agent")
    task_id = record["task_id"]

    conn = get_connection(db_path)
    try:
        conn.execute('''
            INSERT INTO tasks (run_id, task_id, title, description, category, required_capability,
                               dependencies, assigned_agent_id, assigned_agent_name, model_used,
                               fit_score, status, agent_result_status, reason, attempted_agents,
                               output_files, execution_time_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, task_id) DO UPDATE SET
                assigned_agent_id = excluded.assigned_agent_id,
                assigned_agent_name = excluded.assigned_agent_name,
                model_used = excluded.model_used,
                fit_score = excluded.fit_score,
                status = excluded.status,
                agent_result_status = excluded.agent_result_status,
                reason = excluded.reason,
                attempted_agents = excluded.attempted_agents,
                output_files = excluded.output_files,
                execution_time_seconds = excluded.execution_time_seconds,
                updated_at = CURRENT_TIMESTAMP
        ''', (
            run_id, task_id, record.get("title") or task.get("title"),
            task.get("description"), task.get("category"), task.get("required_specialty"),
            json.dumps(task.get("dependencies", [])),
            agent_ids.get(agent_name) if agent_name else None, agent_name,
            record.get("model_used"), record.get("fit_score", 0.0),
            record["status"], record.get("agent_result_status"), record.get("reason"),
            json.dumps(record.get("attempted_agents", [])),
            json.dumps(record.get("output_files", [])),
            record.get("execution_time_seconds", 0.0),
        ))

        for i, att in enumerate(attempts or [], start=1):
            conn.execute('''
                INSERT INTO attempts (run_id, task_id, agent_id, agent_name, attempt_no,
                                      is_successful, error_message, execution_time_seconds, model_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                run_id, task_id, att.get("agent_id"), att.get("agent_name"), i,
                1 if att.get("is_successful") else 0, att.get("error_message"),
                att.get("execution_time_seconds", 0.0), att.get("model_used"),
            ))

        all_conflicts: List[Dict[str, Any]] = list(conflicts or [])
        for f_rec in file_records or []:
            rel_path = f_rec.get("relative_path")
            if not rel_path:
                continue
            conflict = f_rec.get("conflict")
            resolution = conflict.get("resolution") if isinstance(conflict, dict) else f_rec.get("conflict_resolution")
            if isinstance(conflict, dict) and conflict not in all_conflicts:
                all_conflicts.append(conflict)
            review_status = f_rec.get("review_status", "PENDING")
            if review_status not in REVIEW_STATUSES:
                review_status = "PENDING"
            conn.execute('''
                INSERT INTO output_files (run_id, task_id, agent_name, relative_path, requested_path,
                                          size_bytes, sha256, review_status, conflict_resolution)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, task_id, relative_path) DO UPDATE SET
                    agent_name = excluded.agent_name,
                    requested_path = excluded.requested_path,
                    size_bytes = excluded.size_bytes,
                    sha256 = excluded.sha256,
                    review_status = excluded.review_status,
                    conflict_resolution = excluded.conflict_resolution,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                run_id, task_id, agent_name, rel_path,
                f_rec.get("requested_path") or rel_path,
                int(f_rec.get("size_bytes", 0)),
                f_rec.get("sha256"),
                review_status,
                resolution,
            ))

        for conf in all_conflicts:
            conn.execute('''
                INSERT INTO file_conflicts (run_id, task_id, conflict_type, file_path,
                                            resolved_path, other_task_id, resolution, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                run_id,
                conf.get("task_id") or task_id,
                conf["conflict_type"],
                conf["file_path"],
                conf.get("resolved_path"),
                conf.get("other_task_id"),
                conf["resolution"],
                conf.get("detail"),
            ))

        conn.commit()
    finally:
        conn.close()


def update_output_file_reviews(run_id: str, status_by_path: Dict[str, str],
                               db_path: Optional[str] = None):
    """Updates review_status (APPROVED / REVIEW_REQUIRED / REJECTED) on output_files for a run."""
    if not status_by_path:
        return
    for rel_path, st in status_by_path.items():
        if st not in REVIEW_STATUSES:
            raise ValueError(f"Invalid review_status '{st}' for '{rel_path}'")
    conn = get_connection(db_path)
    try:
        for rel_path, st in status_by_path.items():
            conn.execute('''
                UPDATE output_files
                SET review_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND relative_path = ?
            ''', (st, run_id, rel_path))
        conn.commit()
    finally:
        conn.close()


def finish_run(run_id: str, system_status: str, status_counts: Dict[str, int],
               db_path: Optional[str] = None):
    if system_status not in RUN_STATUSES:
        raise ValueError(f"Invalid run status '{system_status}'")
    conn = get_connection(db_path)
    try:
        conn.execute('''
            UPDATE runs SET system_status = ?, completed_count = ?, failed_count = ?,
                            unassigned_count = ?, blocked_count = ?, finished_at = CURRENT_TIMESTAMP
            WHERE run_id = ?
        ''', (
            system_status, status_counts.get("COMPLETED", 0), status_counts.get("FAILED", 0),
            status_counts.get("UNASSIGNED", 0), status_counts.get("BLOCKED", 0), run_id,
        ))
        conn.commit()
    finally:
        conn.close()


def _close_interrupted_run(conn: sqlite3.Connection, run_id: str,
                           status_counts: Optional[Dict[str, int]] = None,
                           interrupt_reason: str = "Çalıştırma yarıda kesildi") -> str:
    """
    Transitions any stuck PENDING/IN_PROGRESS tasks of ``run_id`` to FAILED,
    tallies final counts, and closes the ``RUNNING`` row as ``ABORTED``
    (never left RUNNING and never silently COMPLETED). Caller commits.
    """
    task_cols = set(_table_columns(conn.cursor(), "tasks"))
    if {"run_id", "status", "agent_result_status", "reason"} <= task_cols:
        conn.execute('''
            UPDATE tasks
            SET status = 'FAILED',
                agent_result_status = COALESCE(agent_result_status, 'FAILED'),
                reason = COALESCE(NULLIF(reason, ''), ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE run_id = ? AND status IN ('PENDING', 'IN_PROGRESS')
        ''', (interrupt_reason, run_id))

    if status_counts is None:
        counts = {"COMPLETED": 0, "FAILED": 0, "UNASSIGNED": 0, "BLOCKED": 0}
        if {"run_id", "status"} <= task_cols:
            for st, cnt in conn.execute(
                "SELECT status, COUNT(*) FROM tasks WHERE run_id = ? GROUP BY status",
                (run_id,),
            ).fetchall():
                if st in counts:
                    counts[st] = cnt
    else:
        counts = {
            "COMPLETED": int(status_counts.get("COMPLETED", 0)),
            "FAILED": int(status_counts.get("FAILED", 0)),
            "UNASSIGNED": int(status_counts.get("UNASSIGNED", 0)),
            "BLOCKED": int(status_counts.get("BLOCKED", 0)),
        }

    final_status = "ABORTED"
    conn.execute('''
        UPDATE runs
        SET system_status = ?,
            completed_count = ?,
            failed_count = ?,
            unassigned_count = ?,
            blocked_count = ?,
            finished_at = CURRENT_TIMESTAMP
        WHERE run_id = ? AND system_status = 'RUNNING'
    ''', (
        final_status,
        counts["COMPLETED"],
        counts["FAILED"],
        counts["UNASSIGNED"],
        counts["BLOCKED"],
        run_id,
    ))
    return final_status


def mark_run_aborted(run_id: str, status_counts: Optional[Dict[str, int]] = None,
                     reason: str = "Çalıştırma yarıda kesildi",
                     db_path: Optional[str] = None) -> Optional[str]:
    """
    Safely closes a single run that is still ``RUNNING`` (e.g. from a ``finally`` block
    on KeyboardInterrupt, Streamlit stop, or unexpected exception). No-op if already finished.
    """
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT system_status FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        if row["system_status"] != "RUNNING":
            return row["system_status"]
        final_status = _close_interrupted_run(conn, run_id, status_counts=status_counts,
                                              interrupt_reason=reason)
        conn.commit()
        return final_status
    finally:
        conn.close()


def recover_stale_runs(db_path: Optional[str] = None,
                       max_age_seconds: Optional[int] = None,
                       check_pid: bool = True,
                       exclude_run_ids: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """
    Finds runs left stuck in ``RUNNING`` and transitions them to ``ABORTED``
    with ``finished_at`` set and accurate task counts.

    A ``RUNNING`` row is recovered when:
    - ``max_age_seconds == 0`` (explicit immediate cleanup), OR
    - ``check_pid`` is True, ``owner_pid`` is set, and that process is no longer alive, OR
    - ``started_at`` is older than ``max_age_seconds`` (default: 1800s / 30 min).
    """
    timeout = _stale_run_timeout() if max_age_seconds is None else max(0, int(max_age_seconds))
    excluded = set(exclude_run_ids or ())
    conn = get_connection(db_path)
    recovered: List[Dict[str, Any]] = []
    try:
        run_cols = set(_table_columns(conn.cursor(), "runs"))
        required = {"run_id", "system_status", "started_at", "finished_at",
                    "completed_count", "failed_count", "unassigned_count", "blocked_count"}
        if not required <= run_cols:
            return []

        pid_col = "owner_pid" if "owner_pid" in run_cols else "NULL AS owner_pid"
        rows = conn.execute(f'''
            SELECT run_id, {pid_col}, started_at,
                   CAST(strftime('%s', 'now') AS INTEGER) - CAST(strftime('%s', started_at) AS INTEGER) AS age_seconds
            FROM runs
            WHERE system_status = 'RUNNING'
        ''').fetchall()

        for row in rows:
            rid = row["run_id"]
            if rid in excluded:
                continue
            pid = row["owner_pid"]
            age = row["age_seconds"]
            reason = None

            if timeout == 0:
                reason = "force_recovery"
            elif check_pid and pid is not None and not _is_pid_alive(pid):
                reason = f"dead_pid:{pid}"
            elif age is not None and age >= timeout:
                reason = f"timeout:{age}s"

            if reason is None:
                continue

            interrupt_msg = f"Çalıştırma yarıda kesildi (otomatik kurtarma: {reason})"
            new_status = _close_interrupted_run(conn, rid, status_counts=None,
                                                interrupt_reason=interrupt_msg)
            recovered.append({
                "run_id": rid,
                "previous_status": "RUNNING",
                "new_status": new_status,
                "reason": reason,
                "owner_pid": pid,
                "age_seconds": age,
            })

        if recovered:
            conn.commit()
            logger.warning("Recovered %d stale RUNNING run(s): %s",
                           len(recovered), [r["run_id"] for r in recovered])
        return recovered
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_running_runs(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns all runs currently marked as RUNNING (newest first)."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM runs WHERE system_status = 'RUNNING' ORDER BY started_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_run(run_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_tasks_for_run(run_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM tasks WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_attempts_for_task(run_id: str, task_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM attempts WHERE run_id = ? AND task_id = ? ORDER BY attempt_no",
            (run_id, task_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_output_files_for_run(run_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM output_files WHERE run_id = ? ORDER BY file_id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_conflicts_for_run(run_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM file_conflicts WHERE run_id = ? ORDER BY conflict_id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    db_file = init_db()
    if "--recover-all" in sys.argv[1:]:
        forced = recover_stale_runs(db_path=db_file, max_age_seconds=0)
        print(f"  [ZORLA KURTARILDI] {len(forced)} adet RUNNING kaydı kapatıldı.")
    status = verify_schema(db_file)
    for table, ok in status.items():
        print(f"  [{'OK' if ok else 'MISSING'}] {table}")