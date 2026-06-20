import asyncio
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backend.api.routes as routes_module
from agents.registry import (
    REMOTE,
    AgentRegistry,
    build_default_registry,
)
from agents.remote_adapter import RemoteHttpAgentAdapter
from backend.api.routes import SimulationRunRequest
from scenarios.flash_crash import FlashCrashScenario
from simulation.engine import SimulationEngine
from simulation.market import MarketState
from simulation.replay import ReplayRecorder
from simulation.replay_parser import load_replay

ENDPOINT = "http://localhost:9/decide"


def _valid_buy_post(url, payload, timeout):
    return {"action": "buy", "size": 1.0, "reason": "remote buy", "confidence": 0.6}


def _malformed_body_post(url, payload, timeout):
    # Valid JSON, malformed decision: the engine's normalizer must coerce it.
    return {"action": "explode", "size": "big"}


def _timeout_post(url, payload, timeout):
    raise TimeoutError("remote timed out")


def _http_500_post(url, payload, timeout):
    raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)


def _connection_error_post(url, payload, timeout):
    raise urllib.error.URLError("connection refused")


def _run(agent, *, ticks=6, log_dir=None):
    return SimulationEngine(
        agents=[agent],
        scenario=FlashCrashScenario(),
        max_ticks=ticks,
        recorder=ReplayRecorder(log_dir=log_dir),
    ).run()


class RemoteAdapterEngineTests(unittest.TestCase):
    def test_happy_path_runs_end_to_end(self) -> None:
        agent = RemoteHttpAgentAdapter("agent-remote-buy", ENDPOINT, post_fn=_valid_buy_post)
        with tempfile.TemporaryDirectory() as log_dir:
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertEqual(result.ticks, 6)
        self.assertEqual(len(result.reliability_reports), 1)
        # Clean responses produce no boundary notes, so integrity is intact.
        self.assertEqual(
            result.reliability_reports[0]["components"]["decision_integrity"], 1.0
        )
        self.assertTrue(all(not e["normalization_notes"] for e in replay["events"]))

    def test_timeout_falls_back_to_safe_hold_and_lowers_integrity(self) -> None:
        agent = RemoteHttpAgentAdapter("agent-remote-timeout", ENDPOINT, post_fn=_timeout_post)
        with tempfile.TemporaryDirectory() as log_dir:
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertEqual(result.ticks, 6)
        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))
        self.assertTrue(all(e["normalization_notes"] for e in replay["events"]))
        self.assertEqual(
            result.reliability_reports[0]["components"]["decision_integrity"], 0.0
        )

    def test_non_2xx_falls_back_to_safe_hold(self) -> None:
        agent = RemoteHttpAgentAdapter("agent-remote-500", ENDPOINT, post_fn=_http_500_post)
        with tempfile.TemporaryDirectory() as log_dir:
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))
        self.assertLess(
            result.reliability_reports[0]["components"]["decision_integrity"], 1.0
        )

    def test_connection_error_falls_back_to_safe_hold(self) -> None:
        agent = RemoteHttpAgentAdapter(
            "agent-remote-conn", ENDPOINT, post_fn=_connection_error_post
        )
        with tempfile.TemporaryDirectory() as log_dir:
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))

    def test_malformed_body_is_normalized(self) -> None:
        agent = RemoteHttpAgentAdapter(
            "agent-remote-junk", ENDPOINT, post_fn=_malformed_body_post
        )
        with tempfile.TemporaryDirectory() as log_dir:
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        # An invalid action is coerced to hold by the shared normalizer.
        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))
        self.assertTrue(all(e["normalization_notes"] for e in replay["events"]))

    def test_manifest_records_remote_kind_and_endpoint(self) -> None:
        agent = RemoteHttpAgentAdapter("agent-remote-buy", ENDPOINT, post_fn=_valid_buy_post)
        with tempfile.TemporaryDirectory() as log_dir:
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        identity = {a["id"]: a for a in replay["manifest"]["agents"]}["agent-remote-buy"]
        self.assertEqual(identity["agent_kind"], "remote")
        self.assertEqual(identity["endpoint"], ENDPOINT)

    def test_replay_is_deterministic_with_fixed_responses(self) -> None:
        def run(log_dir: str) -> str:
            agent = RemoteHttpAgentAdapter(
                "agent-remote-buy", ENDPOINT, post_fn=_valid_buy_post
            )
            result = _run(agent, ticks=8, log_dir=log_dir)
            return Path(result.replay_path).read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(run(a), run(b))


class RemoteAdapterUnitTests(unittest.TestCase):
    def test_empty_endpoint_raises(self) -> None:
        with self.assertRaises(ValueError):
            RemoteHttpAgentAdapter("agent-remote", "")

    def test_decide_returns_none_on_transport_failure(self) -> None:
        agent = RemoteHttpAgentAdapter("agent-remote", ENDPOINT, post_fn=_timeout_post)
        self.assertIsNone(agent.decide(tick=0, market_state=MarketState()))

    def test_payload_includes_context(self) -> None:
        captured = {}

        def capture_post(url, payload, timeout):
            captured["url"] = url
            captured["payload"] = payload
            return {"action": "hold"}

        agent = RemoteHttpAgentAdapter("agent-remote", ENDPOINT, post_fn=capture_post)
        agent.decide(
            tick=3,
            market_state=MarketState(),
            portfolio_snapshot={"cash": 10.0, "status": "active"},
        )

        self.assertEqual(captured["url"], ENDPOINT)
        self.assertEqual(captured["payload"]["tick"], 3)
        self.assertIn("current_price", captured["payload"]["market_state"])
        self.assertEqual(captured["payload"]["portfolio_snapshot"]["cash"], 10.0)


class RemoteAgentRegistryTests(unittest.TestCase):
    def test_register_remote_lists_with_remote_kind(self) -> None:
        registry = build_default_registry()
        registry.register_remote("agent-remote-1", ENDPOINT, post_fn=_valid_buy_post)

        listing = {item["id"]: item for item in registry.list_agents()}
        self.assertEqual(listing["agent-remote-1"]["kind"], REMOTE)

    def test_build_remote_returns_adapter(self) -> None:
        registry = AgentRegistry()
        registry.register_remote("agent-remote-1", ENDPOINT, post_fn=_valid_buy_post)
        agents = registry.build(["agent-remote-1"])

        self.assertIsInstance(agents[0], RemoteHttpAgentAdapter)
        self.assertEqual(agents[0].agent_kind, REMOTE)
        self.assertEqual(agents[0].endpoint, ENDPOINT)

    def test_empty_endpoint_registration_raises(self) -> None:
        registry = AgentRegistry()
        with self.assertRaises(Exception):
            registry.register_remote("agent-remote-1", "")


class RemoteAgentApiTests(unittest.TestCase):
    def _registry_with_remote(self) -> AgentRegistry:
        registry = build_default_registry()
        registry.register_remote(
            "agent-remote-buy", ENDPOINT, name="Remote Buyer", post_fn=_valid_buy_post
        )
        return registry

    def test_list_agents_endpoint_shows_remote(self) -> None:
        with patch.object(routes_module, "DEFAULT_REGISTRY", self._registry_with_remote()):
            agents = asyncio.run(routes_module.list_agents())

        remote = {a["id"]: a for a in agents}["agent-remote-buy"]
        self.assertEqual(remote["kind"], "remote")

    def test_run_with_remote_agent_id(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(
                routes_module, "DEFAULT_REGISTRY", self._registry_with_remote()
            ), patch.object(
                routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)
            ):
                return await routes_module.run_simulation(
                    SimulationRunRequest(ticks=6, agent_ids=["agent-remote-buy"])
                )

        with tempfile.TemporaryDirectory() as log_dir:
            result = asyncio.run(run_flow(log_dir))

        self.assertEqual(result["agents"], ["agent-remote-buy"])


if __name__ == "__main__":
    unittest.main()
