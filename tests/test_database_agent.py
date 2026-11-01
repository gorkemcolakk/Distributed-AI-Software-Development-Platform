"""
Unit Tests for S3-04: DatabaseAgent local Ollama SQL generation and schema validation.
Sorumlu: Mahmut Karaalioğlu (Database Agent — llama3.2:3b)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.database_agent import (
    DatabaseAgent,
    ModelOutputError,
    OllamaCallError,
    extract_sql,
    validate_sql_schema,
)

VALID_SQL_REPLY = """Here is the relational database schema for the project:

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
```
Hope this helps!
"""

SAMPLE_DB_TASK = {
    "task_id": "task-db-1",
    "title": "Database Schema & Migration Definition",
    "category": "DATABASE",
    "description": "Design SQL schemas, tables, relationships, and indices for the system.",
    "dependencies": ["task-req-1"],
    "required_specialty": "database",
    "context_artifacts": {"project_title": "Document Manager"},
}


def fixed_llm_reply(text: str):
    calls = []

    def client(prompt: str) -> str:
        calls.append(prompt)
        return text

    client.calls = calls
    return client


def failing_llm_client(error_type: str):
    def client(prompt: str):
        raise OllamaCallError(f"Simulated {error_type}", error_type=error_type)

    return client


class TestSqlExtractionAndValidation(unittest.TestCase):

    def test_extract_sql_from_fenced_block(self):
        sql = extract_sql(VALID_SQL_REPLY)
        self.assertIn("CREATE TABLE IF NOT EXISTS users", sql)
        self.assertNotIn("```", sql)
        self.assertNotIn("Hope this helps!", sql)

    def test_extract_sql_without_fences(self):
        raw = "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT);"
        self.assertEqual(extract_sql(raw), raw)

    def test_extract_sql_empty_raises(self):
        for empty in ("", "   \n\t", None):
            with self.assertRaises(ModelOutputError):
                extract_sql(empty)

    def test_validate_valid_sql_returns_objects(self):
        sql = extract_sql(VALID_SQL_REPLY)
        objs = validate_sql_schema(sql)
        self.assertIn("users", objs["tables"])
        self.assertIn("documents", objs["tables"])
        self.assertIn("idx_documents_user", objs["indexes"])

    def test_validate_syntax_error_raises(self):
        broken = "CREATE TABLE broken (id INTEGER PRIMARY"
        with self.assertRaises(ModelOutputError) as ctx:
            validate_sql_schema(broken)
        self.assertIn("geçerli SQLite SQL değil", str(ctx.exception))

    def test_validate_no_tables_created_raises(self):
        queries_only = "SELECT 1 + 1;"
        with self.assertRaises(ModelOutputError) as ctx:
            validate_sql_schema(queries_only)
        self.assertIn("hiçbir tablo oluşturmuyor", str(ctx.exception))

    def test_validate_forbidden_statements_denied(self):
        forbidden_payloads = [
            "ATTACH DATABASE 'evil.db' AS evil; CREATE TABLE evil.t (x INT);",
            "PRAGMA writable_schema = 1; CREATE TABLE t (x INT);",
            "VACUUM; CREATE TABLE t (x INT);",
            "DETACH DATABASE evil; CREATE TABLE t (x INT);",
        ]
        for payload in forbidden_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ModelOutputError) as ctx:
                    validate_sql_schema(payload)
                self.assertIn("izin verilmeyen ifade", str(ctx.exception).lower())


class TestDatabaseAgentExecution(unittest.TestCase):

    def test_successful_ollama_execution(self):
        client = fixed_llm_reply(VALID_SQL_REPLY)
        agent = DatabaseAgent(use_ollama=True, llm_client=client)

        result = agent.execute_task(SAMPLE_DB_TASK)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(client.calls), 1)
        self.assertIn("users", result.output_artifacts["tables_designed"])
        self.assertIn("documents", result.output_artifacts["tables_designed"])
        self.assertEqual(result.output_artifacts["generation_mode"], "ollama")
        self.assertEqual(result.output_artifacts["model_used"], "llama3.2:3b")

        files = result.output_artifacts.get("files", [])
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0]["filename"].endswith(".sql"))
        self.assertIn("CREATE TABLE IF NOT EXISTS users", files[0]["content"])

    def test_broken_model_output_fails_task(self):
        # Case 1: Plain text / invalid SQL syntax
        client_syntax = fixed_llm_reply("Sorry, I cannot generate database schemas.")
        agent_syntax = DatabaseAgent(use_ollama=True, llm_client=client_syntax)
        result_syntax = agent_syntax.execute_task(SAMPLE_DB_TASK)
        self.assertEqual(result_syntax.status, "FAILED")
        self.assertIn("geçerli SQLite SQL değil", result_syntax.error_message)

        # Case 2: Valid SQL syntax but no table created
        client_no_table = fixed_llm_reply("SELECT 1 + 1;")
        agent_no_table = DatabaseAgent(use_ollama=True, llm_client=client_no_table)
        result_no_table = agent_no_table.execute_task(SAMPLE_DB_TASK)
        self.assertEqual(result_no_table.status, "FAILED")
        self.assertIn("hiçbir tablo oluşturmuyor", result_no_table.error_message)

    def test_ollama_unavailable_with_fallback_enabled(self):
        client = failing_llm_client("CONNECTION_REFUSED")
        agent = DatabaseAgent(use_ollama=True, fallback_enabled=True, llm_client=client)

        result = agent.execute_task(SAMPLE_DB_TASK)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["generation_mode"], "fallback")
        self.assertIn("users", result.output_artifacts["tables_designed"])
        self.assertEqual(result.output_artifacts["status"], "DATABASE_SCHEMA_FALLBACK")
        self.assertEqual(result.output_artifacts["fallback_reason"], "CONNECTION_REFUSED")

    def test_ollama_unavailable_with_fallback_disabled_raises(self):
        client = failing_llm_client("TIMEOUT")
        agent = DatabaseAgent(use_ollama=True, fallback_enabled=False, llm_client=client)

        result = agent.execute_task(SAMPLE_DB_TASK)

        self.assertEqual(result.status, "FAILED")
        self.assertIn("Simulated TIMEOUT", result.error_message)

    def test_ollama_disabled_returns_template(self):
        agent = DatabaseAgent(use_ollama=False)
        result = agent.execute_task(SAMPLE_DB_TASK)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["generation_mode"], "template")
        self.assertIn("users", result.output_artifacts["tables_designed"])


if __name__ == "__main__":
    unittest.main()
