"""
Schema Conflict Detector (S4-04 — Mahmut Karaalioğlu).

Two tasks of the same run may each produce SQL that defines the same table.
With ``CREATE TABLE IF NOT EXISTS`` the second definition would be silently
ignored when the scripts are applied together, so the project would end up
with a table that does not match what the second agent's code expects.

``SchemaConflictDetector`` keeps the first definition of every table as the
canonical one. Each later SQL file is compared against it; a table with a
different column set (name, type, NOT NULL, PRIMARY KEY) is reported as a
``SCHEMA`` conflict with resolution ``REPORTED`` (the first definition stays,
the conflict goes to the Integration Agent for review).

SQL is only executed in an isolated ``:memory:`` SQLite database; ATTACH,
DETACH, PRAGMA and load_extension are denied while the script runs, so a
model-produced file can never touch the disk here.
"""

import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

Column = Tuple[str, str, int, int]  # (name, TYPE, notnull, pk)

_SCRIPT_TIMEOUT_SECONDS = 5.0


def _deny_dangerous(action, arg1, arg2, db_name, trigger):
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() == "load_extension":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def table_definitions(sql: str) -> Optional[Dict[str, List[Column]]]:
    """
    Runs ``sql`` in a throw-away in-memory database and returns
    ``{table_name_lower: [(column, TYPE, notnull, pk), ...]}``.
    Returns None if the script is not valid SQLite (nothing to compare).
    """
    if not isinstance(sql, str) or not sql.strip():
        return None
    conn = sqlite3.connect(":memory:")
    deadline = time.monotonic() + _SCRIPT_TIMEOUT_SECONDS
    try:
        conn.set_authorizer(_deny_dangerous)
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            conn.executescript(sql)
        except sqlite3.Error:
            return None
        conn.set_authorizer(None)
        conn.set_progress_handler(None, 0)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result: Dict[str, List[Column]] = {}
        for name in tables:
            quoted = name.replace('"', '""')
            cols = conn.execute(f'PRAGMA table_info("{quoted}")').fetchall()
            result[name.lower()] = [(c[1].lower(), (c[2] or "").upper(), int(c[3]), int(c[5])) for c in cols]
        return result
    finally:
        conn.close()


def describe_difference(canonical: List[Column], other: List[Column]) -> str:
    """Short human-readable summary of how two column lists differ."""
    a = {c[0]: c for c in canonical}
    b = {c[0]: c for c in other}
    parts = []
    missing = sorted(set(a) - set(b))
    extra = sorted(set(b) - set(a))
    changed = sorted(n for n in set(a) & set(b) if a[n] != b[n])
    if missing:
        parts.append(f"eksik sütunlar: {', '.join(missing)}")
    if extra:
        parts.append(f"fazla sütunlar: {', '.join(extra)}")
    if changed:
        parts.append("farklı tanımlı sütunlar: " + ", ".join(
            f"{n} ({a[n][1] or '-'} -> {b[n][1] or '-'})" for n in changed))
    return "; ".join(parts) or "sütun tanımları farklı"


class SchemaConflictDetector:
    """Remembers the first definition of each table in a run and flags later mismatches."""

    def __init__(self):
        # table -> {"columns": [...], "file_path": str, "task_id": str}
        self.tables: Dict[str, Dict[str, Any]] = {}

    def check(self, task_id: Optional[str], file_path: str, sql: str) -> List[Dict[str, Any]]:
        """
        Registers the tables defined in ``sql`` and returns one SCHEMA conflict per
        table that was already defined differently by another file of the run.
        """
        definitions = table_definitions(sql)
        if not definitions:
            return []
        conflicts = []
        for table, columns in definitions.items():
            known = self.tables.get(table)
            if known is None:
                self.tables[table] = {"columns": columns, "file_path": file_path, "task_id": task_id}
                continue
            if known["file_path"] == file_path:
                continue
            if sorted(known["columns"]) == sorted(columns):
                continue
            conflicts.append({
                "conflict_type": "SCHEMA",
                "file_path": file_path,
                "task_id": task_id,
                "other_task_id": known["task_id"],
                "resolution": "REPORTED",
                "resolved_path": known["file_path"],
                "table": table,
                "detail": (f"'{table}' tablosu '{known['file_path']}' dosyasında farklı tanımlanmış "
                           f"({describe_difference(known['columns'], columns)}). İlk tanım geçerli kabul edildi."),
            })
        return conflicts
