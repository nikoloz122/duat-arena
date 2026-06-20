import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import backend.api.routes as routes_module
from agents.adapters import CallableAgentAdapter
from agents.base import AgentDecision
from agents.registry import (
    EXTERNAL,
    PRESET,
    AgentRegistry,
    AgentRegistryError,
    build_default_registry,
)
from agents.templates import ConservativeAgent
from backend.api.routes import SimulationRunRequest
from scenarios.flash_crash import FlashCrashScenario
from simulation.engine import SimulationEngine
from simulation.market import MarketState
from simulation.replay import ReplayRecorder
from simulation.replay_parser import load_replay


def _hold_fn(tick, market_state):
    return AgentDecision(action="hold", reason="external hold", confidence=0.5)


def _junk_fn(tick, market_state):
    return {"action": "explode", "size": float("nan")}


def _raise_fn(tick, market_state):
    raise RuntimeError("external boom")


class AgentRegistryTests(unittest.TestCase):
    def test_presets_registered_by_default(self) -> None:
        registry = build_default_registry()
        ids = set(registry.ids())
        self.assertEqual(
            ids,
            {"agent-conservative-001", "agent-momentum-001", "agent-panic-seller-001"},
        )

    def test_build_by_ids_returns_instances(self) -> None:
        registry = build_default_registry()
        agents = registry.build(["agent-momentum-001", "agent-conservative-001"])

        self.assertEqual([a.id for a in agents], ["agent-momentum-001", "agent-conservative-001"])

    def test_register_and_build_external(self) -> None:
        registry = AgentRegistry()
        registry.register(
            "agent-ext-1",
            lambda: CallableAgentAdapter("agent-ext-1", _hold_fn),
            kind=EXTERNAL,
        )
        agents = registry.build(["agent-ext-1"])

        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_kind, EXTERNAL)

    def test_duplicate_registration_raises(self) -> None:
        registry = build_default_registry()
        with self.assertRaises(AgentRegistryError):
            registry.register("agent-momentum-001", ConservativeAgent, kind=PRESET)

    def test_unknown_id_raises(self) -> None:
        registry = build_default_registry()
        with self.assertRaises(AgentRegistryError):
            registry.build(["does-not-exist"])

    def test_duplicate_request_raises(self) -> None:
        registry = build_default_registry()
        with self.assertRaises(AgentRegistryError):
            registry.build(["agent-momentum-001", "agent-momentum-001"])

    def test_list_agents_reports_kind(self) -> None:
        registry = build_default_registry()
        listing = {item["id"]: item for item in registry.list_agents()}

        self.assertEqual(listing["agent-momentum-001"]["kind"], PRESET)
        self.assertIn("name", listing["agent-momentum-001"])


class CallableAdapterEngineTests(unittest.TestCase):
    def test_adapter_runs_end_to_end(self) -> None:
        agent = CallableAgentAdapter("agent-ext-hold", _hold_fn, name="Ext Hold")
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=[agent],
                scenario=FlashCrashScenario(),
                max_ticks=6,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

        self.assertEqual(result.ticks, 6)
        self.assertEqual(len(result.reliability_reports), 1)

    def test_malformed_external_agent_is_handled_safely(self) -> None:
        agent = CallableAgentAdapter("agent-ext-junk", _junk_fn)
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=[agent],
                scenario=FlashCrashScenario(),
                max_ticks=6,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()
            replay = load_replay(result.replay_id, log_dir=log_dir)

        # Simulation completed and the boundary recorded the deviations.
        self.assertEqual(result.ticks, 6)
        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))
        self.assertTrue(all(e["normalization_notes"] for e in replay["events"]))
        self.assertEqual(
            result.reliability_reports[0]["components"]["decision_integrity"], 0.0
        )

    def test_raising_external_agent_does_not_crash(self) -> None:
        agent = CallableAgentAdapter("agent-ext-raise", _raise_fn)
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=[agent],
                scenario=FlashCrashScenario(),
                max_ticks=5,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

        self.assertEqual(result.ticks, 5)
        self.assertLess(
            result.reliability_reports[0]["components"]["decision_integrity"], 1.0
        )

    def test_manifest_records_agent_kind(self) -> None:
        external = CallableAgentAdapter("agent-ext-hold", _hold_fn)
        preset = ConservativeAgent()
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=[external, preset],
                scenario=FlashCrashScenario(),
                max_ticks=5,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()
            replay = load_replay(result.replay_id, log_dir=log_dir)

        kinds = {a["id"]: a["agent_kind"] for a in replay["manifest"]["agents"]}
        self.assertEqual(kinds["agent-ext-hold"], "external")
        self.assertEqual(kinds[preset.id], "preset")

    def test_external_agent_replay_is_deterministic(self) -> None:
        def run(log_dir: str) -> str:
            result = SimulationEngine(
                agents=[CallableAgentAdapter("agent-ext-hold", _hold_fn)],
                scenario=FlashCrashScenario(),
                max_ticks=8,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()
            return Path(result.replay_path).read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(run(a), run(b))


class ExternalAgentApiTests(unittest.TestCase):
    def test_list_agents_endpoint_returns_presets(self) -> None:
        agents = asyncio.run(routes_module.list_agents())
        ids = {a["id"] for a in agents}
        self.assertIn("agent-momentum-001", ids)

    def test_run_with_explicit_agent_ids(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                return await routes_module.run_simulation(
                    SimulationRunRequest(ticks=6, agent_ids=["agent-momentum-001"])
                )

        with tempfile.TemporaryDirectory() as log_dir:
            result = asyncio.run(run_flow(log_dir))

        self.assertEqual(result["agents"], ["agent-momentum-001"])

    def test_run_with_unknown_agent_id_returns_400(self) -> None:
        async def run_flow():
            with self.assertRaises(HTTPException) as error:
                await routes_module.run_simulation(
                    SimulationRunRequest(ticks=6, agent_ids=["not-real"])
                )
            self.assertEqual(error.exception.status_code, 400)

        asyncio.run(run_flow())


if __name__ == "__main__":
    unittest.main()
