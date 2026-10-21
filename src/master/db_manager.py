"""
SQLite Persistence Layer (S1-04, S2-07).

Stores run lifecycle (run_id), agent capability profiles, per-run task
statuses and execution attempts. See docs/DATA_MODEL.md for the schema.
"""

import json
import os
import sqlite3
from typing import Any, Dict, Iterable, List, Optional

# Veritabanı dosyasını projenin ana dizinine state.db olarak kaydeder.
# STATE_DB_PATH ortam değişkeni ile (ör. testlerde) farklı bir dosya kullanılabilir.
DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../state.db'))
DB_PATH = os.environ.get("STATE_DB_PATH", DEFAULT_DB_PATH)

# Şema sürümü: PRAGMA user_version içinde tutulur.
SCHEMA_VERSION = 2

AGENT_STATUSES = ("IDLE", "BUSY", "OFFLINE", "ERROR")
TASK_STATUSES = ("PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "UNASSIGNED", "BLOCKED")
TERMINAL_FAILURE_STATUSES = ("FAILED", "UNASSIGNED", "BLOCKED")
RUN_STATUSES = ("RUNNING", "COMPLETED", "PARTIALLY_COMPLETED", "FAILED")

EXPECTED_TABLES = ("runs", "agents", "tasks", "attempts")


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


def init_db(db_path: Optional[str] = None, verbose: bool = True) -> str:
    """Creates all tables idempotently (CREATE TABLE IF NOT EXISTS). Returns DB path."""
    path = _resolve_path(db_path)
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        current_version = cursor.execute("PRAGMA user_version").fetchone()[0]
        if current_version < SCHEMA_VERSION:
            _migrate_legacy_schema(cursor)

        # Çalıştırma (Run) Tablosu: Her orchestrator çağrısı izole bir run_id alır
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS runs (
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
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP
            )
        ''')

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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id, task_id) REFERENCES tasks (run_id, task_id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_run_status ON tasks (run_id, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attempts_run_task ON attempts (run_id, task_id)')

        # Başarısız/engellenmiş bir görevin aynı run içinde sonradan COMPLETED'a çekilmesini engeller
        cursor.execute(f'''
            CREATE TRIGGER IF NOT EXISTS trg_tasks_no_failed_to_completed
            BEFORE UPDATE OF status ON tasks
            WHEN OLD.status IN ({_sql_in(TERMINAL_FAILURE_STATUSES)}) AND NEW.status = 'COMPLETED'
            BEGIN
                SELECT RAISE(ABORT, 'Terminal failure status cannot transition to COMPLETED');
            END
        ''')

        cursor.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()

    if verbose:
        print(f"SQLite veritabanı başarıyla başlatıldı: {path}")
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
               total_tasks: int = 0, db_path: Optional[str] = None):
    conn = get_connection(db_path)
    try:
        conn.execute('''
            INSERT INTO runs (run_id, project_title, requirement_id, total_tasks, system_status)
            VALUES (?, ?, ?, ?, 'RUNNING')
        ''', (run_id, project_title, requirement_id, total_tasks))
        conn.commit()
    finally:
        conn.close()


def save_task_result(run_id: str, task: Dict[str, Any], record: Dict[str, Any],
                     attempts: Optional[List[Dict[str, Any]]] = None,
                     agent_ids: Optional[Dict[str, str]] = None,
                     db_path: Optional[str] = None):
    """
    Persists a task's terminal record (and its attempts) for a run.
    `record` is the assignment dict produced by MasterOrchestrator.
    Raises ValueError if the record would wrongly mark a task COMPLETED.
    """
    validate_task_record(record)
    agent_ids = agent_ids or {}
    agent_name = record.get("assigned_agent")

    conn = get_connection(db_path)
    try:
        conn.execute('''
            INSERT INTO tasks (run_id, task_id, title, description, category, required_capability,
                               dependencies, assigned_agent_id, assigned_agent_name, model_used,
                               fit_score, status, agent_result_status, reason, attempted_agents,
                               execution_time_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, task_id) DO UPDATE SET
                assigned_agent_id = excluded.assigned_agent_id,
                assigned_agent_name = excluded.assigned_agent_name,
                model_used = excluded.model_used,
                fit_score = excluded.fit_score,
                status = excluded.status,
                agent_result_status = excluded.agent_result_status,
                reason = excluded.reason,
                attempted_agents = excluded.attempted_agents,
                execution_time_seconds = excluded.execution_time_seconds,
                updated_at = CURRENT_TIMESTAMP
        ''', (
            run_id, record["task_id"], record.get("title") or task.get("title"),
            task.get("description"), task.get("category"), task.get("required_specialty"),
            json.dumps(task.get("dependencies", [])),
            agent_ids.get(agent_name) if agent_name else None, agent_name,
            record.get("model_used"), record.get("fit_score", 0.0),
            record["status"], record.get("agent_result_status"), record.get("reason"),
            json.dumps(record.get("attempted_agents", [])),
            record.get("execution_time_seconds", 0.0),
        ))

        for i, att in enumerate(attempts or [], start=1):
            conn.execute('''
                INSERT INTO attempts (run_id, task_id, agent_id, agent_name, attempt_no,
                                      is_successful, error_message, execution_time_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                run_id, record["task_id"], att.get("agent_id"), att.get("agent_name"), i,
                1 if att.get("is_successful") else 0, att.get("error_message"),
                att.get("execution_time_seconds", 0.0),
            ))
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


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

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


if __name__ == "__main__":
    db_file = init_db()
    status = verify_schema(db_file)
    for table, ok in status.items():
        print(f"  [{'OK' if ok else 'MISSING'}] {table}")