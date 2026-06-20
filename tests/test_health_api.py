import unittest
from unittest.mock import patch

from agents.llm_agent import DEFAULT_MODEL
from fastapi.testclient import TestClient

from backend.main import app


class HealthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_exposes_llm_diagnostics(self) -> None:
        with patch(
            "backend.api.routes.llm_runtime_status",
            return_value={
                "mode": "auto",
                "model": DEFAULT_MODEL,
                "cache_path": "logs/llm_cache.json",
                "cache_exists": False,
                "cache_entries": 0,
                "api_key_configured": True,
            },
        ):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["DUAT_LLM_MODE"], "auto")
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertTrue(body["api_key_configured"])
        self.assertEqual(body["cache_entries"], 0)
        self.assertTrue(body["llm_ready"])

    def test_health_llm_not_ready_in_replay_without_cache(self) -> None:
        with patch(
            "backend.api.routes.llm_runtime_status",
            return_value={
                "mode": "replay",
                "model": DEFAULT_MODEL,
                "cache_path": "logs/llm_cache.json",
                "cache_exists": False,
                "cache_entries": 0,
                "api_key_configured": True,
            },
        ):
            body = self.client.get("/api/health").json()

        self.assertEqual(body["DUAT_LLM_MODE"], "replay")
        self.assertFalse(body["llm_ready"])
