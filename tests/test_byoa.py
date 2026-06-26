import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import backend.api.byoa_routes as byoa_routes
from agents.byoa_contract import validate_decide_response
from agents.byoa_http import probe_decide_endpoint
from agents.byoa_store import BYOAgentStore
from agents.registry import REMOTE, build_default_registry
from backend.api.byoa_routes import RemoteAgentRequest, register_remote_agent


def _valid_post(url, payload, timeout, headers):
    return 200, {
        "action": "hold",
        "size": 0.5,
        "reason": "Stable",
        "confidence": 0.7,
    }


def _bad_schema_post(url, payload, timeout, headers):
    return 200, {"action": "explode", "size": 2.0}


class BYOAContractTests(unittest.TestCase):
    def test_validate_decide_response_accepts_valid(self) -> None:
        ok, errors = validate_decide_response(
            {"action": "buy", "size": 0.5, "reason": "ok", "confidence": 0.8}
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_validate_decide_response_rejects_invalid(self) -> None:
        ok, errors = validate_decide_response({"action": "explode"})
        self.assertFalse(ok)
        self.assertTrue(errors)


class BYOAProbeTests(unittest.TestCase):
    def test_probe_success(self) -> None:
        result = probe_decide_endpoint(
            url="https://agent.example.com/decide",
            timeout=5,
            post_fn=_valid_post,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.connection_status, "online")

    def test_probe_schema_failure(self) -> None:
        result = probe_decide_endpoint(
            url="https://agent.example.com/decide",
            timeout=5,
            post_fn=_bad_schema_post,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.errors)


class RemoteRegistrationApiTests(unittest.TestCase):
    def _register(self, name: str, endpoint: str, store_path: Path):
        registry = build_default_registry()
        store = BYOAgentStore(store_path)
        store.load()
        registry.attach_store(store)
        with patch.object(byoa_routes, "DEFAULT_REGISTRY", registry), patch.object(
            byoa_routes, "get_byoa_store", return_value=store
        ), patch.object(
            byoa_routes, "validate_public_url", side_effect=lambda url: url
        ):
            return asyncio.run(
                register_remote_agent(
                    RemoteAgentRequest(name=name, endpoint=endpoint, description="Test agent")
                )
            ), registry, store

    def test_register_success_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "byoa_agents.json"
            created, registry, store = self._register("My Agent", "https://agent.example.com/decide", path)
            self.assertEqual(created["kind"], REMOTE)
            self.assertTrue(created["id"].startswith("agent-remote-my-agent-"))
            self.assertTrue(registry.is_registered(created["id"]))
            self.assertIsNotNone(store.get(created["id"]))

    def test_registration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "byoa_agents.json"
            first, registry, _ = self._register("Repeat", "https://agent.example.com/decide", path)
            count_after_first = len(registry.ids())
            second, _, _ = self._register("Repeat", "https://agent.example.com/decide", path)
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(len(registry.ids()), count_after_first)

    def test_rejected_url_returns_400(self) -> None:
        registry = build_default_registry()
        with patch.object(byoa_routes, "DEFAULT_REGISTRY", registry):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(
                    register_remote_agent(
                        RemoteAgentRequest(name="Local", endpoint="http://127.0.0.1:9000/decide")
                    )
                )
            self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
