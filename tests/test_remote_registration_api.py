import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import backend.api.routes as routes_module
from agents.registry import REMOTE, build_default_registry
from backend.api.routes import RemoteAgentRequest, register_remote_agent


def _register(name: str, endpoint: str):
    return asyncio.run(
        register_remote_agent(RemoteAgentRequest(name=name, endpoint=endpoint))
    )


class RemoteRegistrationApiTests(unittest.TestCase):
    def test_register_success_and_listed(self) -> None:
        registry = build_default_registry()
        with patch.object(routes_module, "DEFAULT_REGISTRY", registry), patch.object(
            routes_module, "validate_public_url", side_effect=lambda url: url
        ):
            created = _register("My Agent", "https://agent.example.com/decide")
            self.assertEqual(created["kind"], REMOTE)
            self.assertTrue(created["id"].startswith("agent-remote-my-agent-"))
            self.assertTrue(registry.is_registered(created["id"]))

            listing = {item["id"]: item for item in registry.list_agents()}
            self.assertIn(created["id"], listing)
            self.assertEqual(listing[created["id"]]["kind"], REMOTE)

    def test_registration_is_idempotent(self) -> None:
        registry = build_default_registry()
        with patch.object(routes_module, "DEFAULT_REGISTRY", registry), patch.object(
            routes_module, "validate_public_url", side_effect=lambda url: url
        ):
            first = _register("Repeat", "https://agent.example.com/decide")
            count_after_first = len(registry.ids())
            second = _register("Repeat", "https://agent.example.com/decide")

            self.assertEqual(first["id"], second["id"])
            self.assertEqual(len(registry.ids()), count_after_first)

    def test_different_endpoint_yields_different_id(self) -> None:
        registry = build_default_registry()
        with patch.object(routes_module, "DEFAULT_REGISTRY", registry), patch.object(
            routes_module, "validate_public_url", side_effect=lambda url: url
        ):
            a = _register("Agent", "https://agent.example.com/a")
            b = _register("Agent", "https://agent.example.com/b")
            self.assertNotEqual(a["id"], b["id"])

    def test_rejected_url_returns_400(self) -> None:
        # No guard patch: the real SSRF guard rejects a loopback literal
        # (numeric host, so no network call is made).
        registry = build_default_registry()
        with patch.object(routes_module, "DEFAULT_REGISTRY", registry):
            with self.assertRaises(HTTPException) as ctx:
                _register("Local", "http://127.0.0.1:9000/decide")
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(len(registry.ids()), len(build_default_registry().ids()))


if __name__ == "__main__":
    unittest.main()
