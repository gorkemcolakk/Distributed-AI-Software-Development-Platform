"""
S4-02: Comprehensive tests for Error Classification & Input/Output Security.

Covers:
 1. Transient vs Permanent error classification
 2. Input validation (requirement text, task payload, file paths)
 3. Model output sanitisation (HTML/XSS, JSON validation)
 4. Log redaction (API keys, tokens, passwords never leak)
"""

import json
import socket
import unittest
import urllib.error
from unittest.mock import MagicMock

from src.security.error_classification import (
    ClassifiedError,
    ErrorKind,
    PERMANENT_CODES,
    TRANSIENT_CODES,
    classify_error_code,
    classify_exception,
    classify_http_status,
    classify_task_result,
    extract_error_code_from_message,
    extract_error_code_from_result,
)
from src.security.input_validation import (
    InputValidationError,
    MAX_REQUIREMENT_LENGTH,
    MIN_REQUIREMENT_LENGTH,
    validate_output_path,
    validate_requirement_text,
    validate_task_payload,
    sanitize_string,
    check_no_null_bytes,
    check_no_control_chars,
    check_length,
)
from src.security.output_sanitizer import (
    REDACTED,
    redact_secrets,
    safe_log_message,
    sanitize_for_display,
    strip_dangerous_html,
    validate_json_output,
)
from src.contracts import WorkerErrorCode


# =====================================================================
# 1. HATA SINIFLANDIRMA TESTLERİ
# =====================================================================

class TestErrorKindClassification(unittest.TestCase):
    """Transient and permanent error code classification."""

    def test_timeout_is_transient(self):
        self.assertEqual(classify_error_code("TIMEOUT"), ErrorKind.TRANSIENT)

    def test_unreachable_is_transient(self):
        self.assertEqual(classify_error_code("UNREACHABLE"), ErrorKind.TRANSIENT)

    def test_unauthorized_is_permanent(self):
        self.assertEqual(classify_error_code("UNAUTHORIZED"), ErrorKind.PERMANENT)

    def test_invalid_payload_is_permanent(self):
        self.assertEqual(classify_error_code("INVALID_PAYLOAD"), ErrorKind.PERMANENT)

    def test_duplicate_task_is_permanent(self):
        self.assertEqual(classify_error_code("DUPLICATE_TASK"), ErrorKind.PERMANENT)

    def test_unsafe_path_is_permanent(self):
        self.assertEqual(classify_error_code("UNSAFE_PATH"), ErrorKind.PERMANENT)

    def test_contract_violation_is_permanent(self):
        self.assertEqual(classify_error_code("CONTRACT_VIOLATION"), ErrorKind.PERMANENT)

    def test_none_code_is_permanent(self):
        self.assertEqual(classify_error_code(None), ErrorKind.PERMANENT)

    def test_unknown_code_is_permanent(self):
        self.assertEqual(classify_error_code("SOMETHING_RANDOM"), ErrorKind.PERMANENT)


class TestHttpStatusClassification(unittest.TestCase):
    """HTTP status code classification."""

    def test_429_is_transient(self):
        self.assertEqual(classify_http_status(429), ErrorKind.TRANSIENT)

    def test_503_is_transient(self):
        self.assertEqual(classify_http_status(503), ErrorKind.TRANSIENT)

    def test_408_is_transient(self):
        self.assertEqual(classify_http_status(408), ErrorKind.TRANSIENT)

    def test_504_is_transient(self):
        self.assertEqual(classify_http_status(504), ErrorKind.TRANSIENT)

    def test_502_is_transient(self):
        self.assertEqual(classify_http_status(502), ErrorKind.TRANSIENT)

    def test_400_is_permanent(self):
        self.assertEqual(classify_http_status(400), ErrorKind.PERMANENT)

    def test_401_is_permanent(self):
        self.assertEqual(classify_http_status(401), ErrorKind.PERMANENT)

    def test_404_is_permanent(self):
        self.assertEqual(classify_http_status(404), ErrorKind.PERMANENT)

    def test_500_is_permanent(self):
        self.assertEqual(classify_http_status(500), ErrorKind.PERMANENT)


class TestExceptionClassification(unittest.TestCase):
    """Exception to ClassifiedError mapping."""

    def test_socket_timeout(self):
        err = classify_exception(socket.timeout("timed out"))
        self.assertEqual(err.kind, ErrorKind.TRANSIENT)
        self.assertTrue(err.retryable)
        self.assertEqual(err.code, "TIMEOUT")

    def test_timeout_error(self):
        err = classify_exception(TimeoutError("deadline exceeded"))
        self.assertEqual(err.kind, ErrorKind.TRANSIENT)
        self.assertTrue(err.retryable)

    def test_syntax_error_is_permanent(self):
        err = classify_exception(SyntaxError("invalid syntax"))
        self.assertEqual(err.kind, ErrorKind.PERMANENT)
        self.assertFalse(err.retryable)

    def test_value_error_is_permanent(self):
        err = classify_exception(ValueError("bad value"))
        self.assertEqual(err.kind, ErrorKind.PERMANENT)
        self.assertFalse(err.retryable)

    def test_generic_exception_is_permanent(self):
        err = classify_exception(RuntimeError("unknown"))
        self.assertEqual(err.kind, ErrorKind.PERMANENT)
        self.assertFalse(err.retryable)

    def test_classified_error_to_dict(self):
        err = ClassifiedError(
            kind=ErrorKind.TRANSIENT,
            code="TIMEOUT",
            http_status=408,
            message="test",
            retryable=True,
            source_error="TimeoutError",
        )
        d = err.to_dict()
        self.assertEqual(d["kind"], "TRANSIENT")
        self.assertEqual(d["code"], "TIMEOUT")
        self.assertTrue(d["retryable"])


class TestExtractErrorCode(unittest.TestCase):
    """Error code extraction from messages and results."""

    def test_extract_from_message_prefix(self):
        self.assertEqual(
            extract_error_code_from_message("[TIMEOUT] Worker HTTP zaman aşımı"),
            "TIMEOUT",
        )

    def test_extract_from_message_unknown(self):
        self.assertIsNone(extract_error_code_from_message("[FAKE_CODE] nope"))

    def test_extract_from_message_none(self):
        self.assertIsNone(extract_error_code_from_message(None))

    def test_extract_from_result_contract(self):
        result = MagicMock()
        result.output_artifacts = {
            "error_contract": {"error_code": "UNAUTHORIZED"}
        }
        result.error_message = None
        self.assertEqual(extract_error_code_from_result(result), "UNAUTHORIZED")

    def test_extract_from_result_message(self):
        result = MagicMock()
        result.output_artifacts = {}
        result.error_message = "[UNREACHABLE] sunucuya ulaşılamadı"
        self.assertEqual(extract_error_code_from_result(result), "UNREACHABLE")

    def test_classify_task_result_transient(self):
        result = MagicMock()
        result.output_artifacts = {"error_contract": {"error_code": "TIMEOUT"}}
        result.error_message = "timeout"
        classified = classify_task_result(result)
        self.assertEqual(classified.kind, ErrorKind.TRANSIENT)
        self.assertTrue(classified.retryable)

    def test_classify_task_result_permanent(self):
        result = MagicMock()
        result.output_artifacts = {}
        result.error_message = "[INVALID_PAYLOAD] bad data"
        classified = classify_task_result(result)
        self.assertEqual(classified.kind, ErrorKind.PERMANENT)
        self.assertFalse(classified.retryable)


# =====================================================================
# 2. GİRDİ DOĞRULAMA TESTLERİ
# =====================================================================

class TestRequirementValidation(unittest.TestCase):
    """Requirement text input validation."""

    def test_valid_requirement(self):
        result = validate_requirement_text("Bu bir kullanıcı gereksinim metnidir, en az on karakter.")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) >= MIN_REQUIREMENT_LENGTH)

    def test_empty_requirement_rejected(self):
        with self.assertRaises(InputValidationError) as ctx:
            validate_requirement_text("")
        self.assertEqual(ctx.exception.field, "requirement")

    def test_whitespace_only_requirement_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_requirement_text("     ")

    def test_too_short_requirement_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_requirement_text("")

    def test_too_long_requirement_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_requirement_text("x" * (MAX_REQUIREMENT_LENGTH + 1))

    def test_null_byte_requirement_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_requirement_text("geçerli metin\x00 enjeksiyon")

    def test_control_char_requirement_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_requirement_text("metin\x07bip sesi")

    def test_non_string_requirement_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_requirement_text(12345)

    def test_stripped_output(self):
        result = validate_requirement_text("  Bu bir gereksinim metnidir, yeterince uzun.  ")
        self.assertFalse(result.startswith(" "))
        self.assertFalse(result.endswith(" "))


class TestTaskPayloadValidation(unittest.TestCase):
    """Task payload validation."""

    def test_valid_payload(self):
        payload = {"task_id": "task-be-1", "title": "Backend API"}
        result = validate_task_payload(payload)
        self.assertEqual(result["task_id"], "task-be-1")

    def test_missing_task_id_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_task_payload({"title": "No ID"})

    def test_empty_task_id_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_task_payload({"task_id": "   "})

    def test_non_dict_payload_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_task_payload("not a dict")

    def test_null_byte_in_task_id_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_task_payload({"task_id": "task\x00evil"})


class TestOutputPathValidation(unittest.TestCase):
    """Output file path validation."""

    def test_valid_python_file(self):
        result = validate_output_path("backend_api.py")
        self.assertEqual(result, "backend_api.py")

    def test_valid_nested_path(self):
        result = validate_output_path("src/generated/api.py")
        self.assertEqual(result, "src/generated/api.py")

    def test_path_traversal_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_output_path("../../../etc/passwd")

    def test_absolute_path_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_output_path("/etc/passwd")

    def test_windows_absolute_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_output_path("C:\\Windows\\System32\\evil.py")

    def test_disallowed_extension_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_output_path("evil.exe")

    def test_null_byte_in_path_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_output_path("file\x00.py")

    def test_empty_path_rejected(self):
        with self.assertRaises(InputValidationError):
            validate_output_path("")

    def test_sql_file_allowed(self):
        result = validate_output_path("schema.sql")
        self.assertEqual(result, "schema.sql")

    def test_html_file_allowed(self):
        result = validate_output_path("index.html")
        self.assertEqual(result, "index.html")


class TestSanitizeString(unittest.TestCase):
    """Generic string sanitisation."""

    def test_valid_string(self):
        result = sanitize_string("hello world")
        self.assertEqual(result, "hello world")

    def test_non_string_rejected(self):
        with self.assertRaises(InputValidationError):
            sanitize_string(42)

    def test_null_byte_rejected(self):
        with self.assertRaises(InputValidationError):
            sanitize_string("test\x00value")


# =====================================================================
# 3. ÇIKTI TEMİZLEME TESTLERİ
# =====================================================================

class TestOutputSanitization(unittest.TestCase):
    """Model output sanitisation for display."""

    def test_script_tag_escaped(self):
        result = sanitize_for_display('<script>alert("xss")</script>')
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_iframe_escaped(self):
        result = sanitize_for_display('<iframe src="evil.com"></iframe>')
        self.assertNotIn("<iframe", result)

    def test_normal_text_preserved(self):
        text = "Bu normal bir metin çıktısıdır."
        result = sanitize_for_display(text)
        self.assertEqual(result, text)

    def test_ampersand_escaped(self):
        result = sanitize_for_display("A & B")
        self.assertIn("&amp;", result)

    def test_empty_string(self):
        self.assertEqual(sanitize_for_display(""), "")

    def test_none_returns_none(self):
        self.assertIsNone(sanitize_for_display(None))


class TestStripDangerousHtml(unittest.TestCase):
    """Strip dangerous HTML tags without full escaping."""

    def test_script_removed(self):
        result = strip_dangerous_html('<div><script>alert(1)</script></div>')
        self.assertNotIn("<script>", result)
        self.assertIn("<!-- removed -->", result)

    def test_onclick_removed(self):
        result = strip_dangerous_html('<div onclick="evil()">click</div>')
        self.assertNotIn("onclick=", result)
        self.assertIn("data-removed=", result)


class TestJsonOutputValidation(unittest.TestCase):
    """Model JSON output validation."""

    def test_valid_json(self):
        ok, parsed = validate_json_output('{"key": "value"}')
        self.assertTrue(ok)
        self.assertEqual(parsed["key"], "value")

    def test_fenced_json(self):
        ok, parsed = validate_json_output('```json\n{"name": "test"}\n```')
        self.assertTrue(ok)
        self.assertEqual(parsed["name"], "test")

    def test_invalid_json(self):
        ok, error = validate_json_output("this is not json")
        self.assertFalse(ok)
        self.assertIn("Geçersiz JSON", error)

    def test_missing_required_keys(self):
        ok, error = validate_json_output('{"a": 1}', required_keys={"a", "b"})
        self.assertFalse(ok)
        self.assertIn("b", error)

    def test_empty_input(self):
        ok, error = validate_json_output("")
        self.assertFalse(ok)

    def test_non_dict_json(self):
        ok, error = validate_json_output("[1, 2, 3]")
        self.assertFalse(ok)
        self.assertIn("sözlük", error)

    def test_too_long_input(self):
        ok, error = validate_json_output("x" * 600_000)
        self.assertFalse(ok)
        self.assertIn("çok uzun", error)


# =====================================================================
# 4. LOG REDACTION TESTLERİ — API ANAHTARI / HASSAS VERİ SIZINTISI
# =====================================================================

class TestLogRedaction(unittest.TestCase):
    """Secret redaction in log messages."""

    def test_api_key_redacted(self):
        text = "Config: api_key=AIzaSyAbcDefGhiJklMnoPqrStUvWxYz123456789"
        result = redact_secrets(text)
        self.assertNotIn("AIzaSyAbcDefGhiJklMnoPqrStUvWxYz123456789", result)
        self.assertIn(REDACTED, result)

    def test_bearer_token_redacted(self):
        text = 'Authorization: Bearer sk-abcdefghij1234567890abcdefghij12'
        result = redact_secrets(text)
        self.assertNotIn("sk-abcdefghij1234567890abcdefghij12", result)
        self.assertIn(REDACTED, result)

    def test_openai_key_redacted(self):
        text = "Using model with key sk-proj12345678901234567890123456789012"
        result = redact_secrets(text)
        self.assertNotIn("sk-proj12345678901234567890123456789012", result)
        self.assertIn(REDACTED, result)

    def test_password_redacted(self):
        text = "Database password=SuperSecret123!"
        result = redact_secrets(text)
        self.assertNotIn("SuperSecret123!", result)
        self.assertIn(REDACTED, result)

    def test_connection_string_redacted(self):
        text = "Connecting to postgres://user:pass@host:5432/db"
        result = redact_secrets(text)
        self.assertNotIn("postgres://user:pass@host:5432/db", result)
        self.assertIn(REDACTED, result)

    def test_gemini_api_key_env_redacted(self):
        text = 'export GEMINI_API_KEY="AIzaSyB1234567890abcdefghijklmnopqrstuvwx"'
        result = redact_secrets(text)
        self.assertIn(REDACTED, result)

    def test_worker_auth_token_redacted(self):
        text = "WORKER_AUTH_TOKEN=my-super-secret-token-12345678"
        result = redact_secrets(text)
        self.assertNotIn("my-super-secret-token-12345678", result)
        self.assertIn(REDACTED, result)

    def test_no_secrets_unchanged(self):
        text = "Normal log message: task completed successfully in 2.5 seconds."
        result = redact_secrets(text)
        self.assertEqual(result, text)

    def test_empty_text(self):
        self.assertEqual(redact_secrets(""), "")

    def test_multiple_secrets_redacted(self):
        text = (
            "api_key=ABCDEFGHIJKLMNOP1234 "
            "password=mysecretpwd "
            "Authorization: Bearer tok-abcdef123456"
        )
        result = redact_secrets(text)
        self.assertNotIn("ABCDEFGHIJKLMNOP1234", result)
        self.assertNotIn("mysecretpwd", result)
        self.assertNotIn("tok-abcdef123456", result)
        self.assertEqual(result.count(REDACTED), 3)


class TestSafeLogMessage(unittest.TestCase):
    """Combined log sanitisation (redaction + truncation + control chars)."""

    def test_secrets_removed(self):
        msg = "Error: api_key=SuperSecretKeyValue1234 caused failure"
        result = safe_log_message(msg)
        self.assertNotIn("SuperSecretKeyValue1234", result)
        self.assertIn(REDACTED, result)

    def test_control_chars_removed(self):
        msg = "Error\x07message\x01with\x0econtrol"
        result = safe_log_message(msg)
        self.assertNotIn("\x07", result)
        self.assertNotIn("\x01", result)
        self.assertNotIn("\x0e", result)

    def test_newline_preserved(self):
        msg = "Line 1\nLine 2\nLine 3"
        result = safe_log_message(msg)
        self.assertIn("\n", result)

    def test_long_message_truncated(self):
        msg = "x" * 5000
        result = safe_log_message(msg, max_length=100)
        self.assertTrue(len(result) <= 120)  # 100 + truncation marker
        self.assertIn("[kesildi]", result)

    def test_empty_message(self):
        self.assertEqual(safe_log_message(""), "")


# =====================================================================
# 5. ENTEGRASYON — retry_policy İLE UYUMLULUK
# =====================================================================

class TestRetryPolicyCompatibility(unittest.TestCase):
    """Verify that the new module is consistent with existing retry_policy."""

    def test_transient_codes_match_retry_policy(self):
        from src.master.retry_policy import TRANSIENT_CODES as RP_TRANSIENT
        for code in RP_TRANSIENT:
            self.assertEqual(
                classify_error_code(code), ErrorKind.TRANSIENT,
                f"Code '{code}' in retry_policy TRANSIENT_CODES should be TRANSIENT"
            )

    def test_permanent_codes_not_in_transient(self):
        for code in PERMANENT_CODES:
            self.assertNotEqual(
                classify_error_code(code), ErrorKind.TRANSIENT,
                f"Code '{code}' should not be TRANSIENT"
            )


class TestOrchestratorSecurityIntegration(unittest.TestCase):
    """MasterOrchestrator input validation and permanent error no-retry integration."""

    def test_orchestrator_rejects_empty_or_oversized_requirement(self):
        from src.master.orchestrator import MasterOrchestrator
        orch = MasterOrchestrator(persist=False)
        with self.assertRaises(InputValidationError):
            orch.process_requirement("   ", "Empty Test")
        with self.assertRaises(InputValidationError):
            orch.process_requirement("a" * (MAX_REQUIREMENT_LENGTH + 1), "Oversized Test")

    def test_orchestrator_does_not_retry_permanent_error(self):
        from src.master.orchestrator import MasterOrchestrator
        from src.master.capability_eval import CapabilityEvaluator
        from src.master.retry_policy import RetryPolicy
        from src.agents.base_agent import BaseAgent, AgentCapabilityProfile, TaskResult

        class PermanentFailAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    "agent-perm", "PermAgent", "test-model",
                    AgentCapabilityProfile(90, 90, 90, ["requirements", "backend", "frontend", "database", "testing", "integration"])
                )
                self.call_count = 0

            def execute_task(self, task):
                self.call_count += 1
                return TaskResult(
                    task_id=task["task_id"],
                    agent_id=self.agent_id,
                    status="FAILED",
                    output_artifacts={},
                    logs=[],
                    execution_time_seconds=0.01,
                    error_message="[INVALID_PAYLOAD] Syntax error",
                    error_kind="PERMANENT",
                )

        agent = PermanentFailAgent()
        orch = MasterOrchestrator(
            evaluator=CapabilityEvaluator([agent]),
            persist=False,
            retry_policy=RetryPolicy(max_retries=3, backoff_seconds=0.0),
        )
        orch.process_requirement("Geçerli bir yazılım gereksinimi metni giriliyor.", "Test Projesi")
        # Her görev için kalıcı hatada sadece 1 kez çağrılmalı (retry=3 olmasına rağmen tekrar denenmemeli)
        self.assertEqual(agent.call_count, 1)


if __name__ == "__main__":
    unittest.main()
