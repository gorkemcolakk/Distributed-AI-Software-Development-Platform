"""
Unit Tests for S2-01: API Configuration, Local Ollama Handling & Safe Fallback Logic.
Sorumlu: İrem Yılmaz (Backend Agent & Scrum Master)
"""

import sys
import os
import unittest
import json
import urllib.error
import socket
from unittest.mock import patch, MagicMock

# Add project root and master_agent_projesi to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "master_agent_projesi")))

from master_agent_projesi.app import (
    load_api_key,
    get_model_config,
    call_local_ollama,
    decompose_task,
    ModelServiceError,
    get_fallback_json
)


class TestApiConfigAndFallback(unittest.TestCase):

    def setUp(self):
        # Clean environment before each test
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_load_api_key_empty(self):
        """Test that missing or unset API key safely returns an empty string without raising exceptions."""
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        key = load_api_key("GEMINI_API_KEY")
        self.assertEqual(key, "")

    def test_load_api_key_filters_dummy_placeholders(self):
        """Test that dummy credentials like 'api.key' are not treated as valid API keys."""
        os.environ["GEMINI_API_KEY"] = "api.key"
        self.assertEqual(load_api_key("GEMINI_API_KEY"), "")

        os.environ["GEMINI_API_KEY"] = "YOUR_API_KEY_HERE"
        self.assertEqual(load_api_key("GEMINI_API_KEY"), "")

    def test_load_api_key_valid(self):
        """Test that a legitimate environment API key is loaded cleanly."""
        os.environ["GEMINI_API_KEY"] = "AIzaSyRealApiKeyForTesting123"
        self.assertEqual(load_api_key("GEMINI_API_KEY"), "AIzaSyRealApiKeyForTesting123")

    def test_get_model_config_defaults(self):
        """Test central model configuration returns required defaults."""
        if "OLLAMA_HOST" in os.environ:
            del os.environ["OLLAMA_HOST"]
        if "OLLAMA_MODEL" in os.environ:
            del os.environ["OLLAMA_MODEL"]

        config = get_model_config()
        self.assertEqual(config["ollama_host"], "http://localhost:11434")
        self.assertEqual(config["ollama_model"], "qwen2.5:3b")
        self.assertGreater(config["timeout"], 0)
        self.assertTrue(config["fallback_enabled"])

    @patch("urllib.request.urlopen")
    def test_call_local_ollama_quota_exceeded_429(self, mock_urlopen):
        """Test that HTTP 429 quota/rate limit error is caught and classified."""
        mock_error = urllib.error.HTTPError(
            url="http://localhost:11434/api/generate",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None
        )
        mock_urlopen.side_effect = mock_error

        with self.assertRaises(ModelServiceError) as ctx:
            call_local_ollama("Test prompt", host="http://localhost:11434")

        self.assertEqual(ctx.exception.error_type, "QUOTA_EXCEEDED")
        self.assertEqual(ctx.exception.status_code, 429)

    @patch("urllib.request.urlopen")
    def test_call_local_ollama_timeout(self, mock_urlopen):
        """Test that socket/request timeout is classified as TIMEOUT."""
        mock_urlopen.side_effect = urllib.error.URLError(reason=socket.timeout("The read operation timed out"))

        with self.assertRaises(ModelServiceError) as ctx:
            call_local_ollama("Test prompt", timeout=5)

        self.assertEqual(ctx.exception.error_type, "TIMEOUT")

    @patch("urllib.request.urlopen")
    def test_call_local_ollama_connection_refused(self, mock_urlopen):
        """Test that offline Ollama server connection refused is classified properly."""
        mock_urlopen.side_effect = urllib.error.URLError(reason=ConnectionRefusedError("Connection refused"))

        with self.assertRaises(ModelServiceError) as ctx:
            call_local_ollama("Test prompt", host="http://localhost:11434")

        self.assertEqual(ctx.exception.error_type, "CONNECTION_REFUSED")

    @patch("master_agent_projesi.app.call_local_ollama")
    @patch("streamlit.toast")
    @patch("streamlit.warning")
    @patch("streamlit.info")
    def test_decompose_task_fallback_on_429(self, mock_info, mock_warning, mock_toast, mock_call):
        """Test that decompose_task smoothly transitions to labeled fallback mode on 429 quota error."""
        mock_call.side_effect = ModelServiceError("Rate limit", error_type="QUOTA_EXCEEDED", status_code=429)

        result_json, is_demo, label = decompose_task("Kütüphane takip sistemi")
        self.assertTrue(is_demo)
        self.assertIn("429", label)
        
        # Verify result is valid JSON containing all 5 standard tasks
        parsed = json.loads(result_json)
        self.assertIn("Requirements_Analysis", parsed)
        self.assertIn("Frontend_Development", parsed)
        self.assertIn("Backend_Development", parsed)
        self.assertIn("Database_Design", parsed)
        self.assertIn("Quality_Assurance_and_Testing", parsed)

    @patch("master_agent_projesi.app.call_local_ollama")
    @patch("streamlit.toast")
    @patch("streamlit.warning")
    @patch("streamlit.info")
    def test_decompose_task_fallback_on_offline(self, mock_info, mock_warning, mock_toast, mock_call):
        """Test that decompose_task transitions to labeled fallback mode when Ollama is offline."""
        mock_call.side_effect = ModelServiceError("Offline", error_type="CONNECTION_REFUSED")

        result_json, is_demo, label = decompose_task("E-ticaret platformu")
        self.assertTrue(is_demo)
        self.assertIn("Ollama Çevrimdışı", label)
        
        parsed = json.loads(result_json)
        self.assertEqual(len(parsed), 5)


if __name__ == "__main__":
    unittest.main()
