"""Tests for the read-only integrity + scorecard replay endpoints.

These endpoints are thin wrappers over `simulation.integrity.categorize_events`
and `simulation.scorecard.build_scorecards`, so the tests confirm wiring and
error handling rather than re-testing that (already covered) logic. Offline:
runs go to a temp log dir and the routes' settings are patched to point at it.
"""

import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import backend.api.routes as routes_module
from agents.base import AgentDecision, TradingAgent
from agents.templates import build_default_agents
from scenarios.registry import get_scenario
from simulation.engine import SimulationEngine
from simulation.replay import ReplayRecorder


class _OversizedAgent(TradingAgent):
    """Always asks to buy far above the size cap, forcing real interceptions."""

    def __init__(self) -> None:
        super().__init__("agent-oversized-001", risk_profile="chaos", name="Oversized Agent")

    def decide(self, tick: int, market_state):
        return AgentDecision(action="buy", size=5000.0, reason="oversize", confidence=0.9)


def _run(log_dir: str, agents=None, scenario_id: str = "flash-crash", ticks: int = 6):
    return SimulationEngine(
        agents=agents if agents is not None else build_default_agents(),
        scenario=get_scenario(scenario_id),
        max_ticks=ticks,
        recorder=ReplayRecorder(log_dir=log_dir),
    ).run()


class ReplayIntegrityApiTests(unittest.TestCase):
    def test_integrity_endpoint_categorizes_real_events(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                result = _run(log_dir, agents=[_OversizedAgent()], ticks=6)
                return await routes_module.get_replay_integrity(result.replay_id)

        with tempfile.TemporaryDirectory() as log_dir:
            violations = asyncio.run(run_flow(log_dir))

        # Every tick the oversized buy is clamped -> real interceptions recorded.
        self.assertEqual(violations["intervention_ticks"], 6)
        self.assertGreater(violations["total"], 0)
        self.assertTrue(any(c["key"] == "oversized_position" for c in violations["categories"]))
        self.assertIn("timeline", violations)

    def test_integrity_clean_run_is_zeroed(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                result = _run(log_dir)
                return await routes_module.get_replay_integrity(result.replay_id)

        with tempfile.TemporaryDirectory() as log_dir:
            violations = asyncio.run(run_flow(log_dir))

        self.assertEqual(violations["total"], 0)
        self.assertEqual(violations["categories"], [])

    def test_integrity_unknown_replay_returns_404(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                with self.assertRaises(HTTPException) as error:
                    await routes_module.get_replay_integrity("missing-run")
                self.assertEqual(error.exception.status_code, 404)

        with tempfile.TemporaryDirectory() as log_dir:
            asyncio.run(run_flow(log_dir))


class ReplayScorecardApiTests(unittest.TestCase):
    def test_scorecards_endpoint_returns_one_card_per_agent(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                result = _run(log_dir)
                return await routes_module.get_replay_scorecards(result.replay_id)

        with tempfile.TemporaryDirectory() as log_dir:
            payload = asyncio.run(run_flow(log_dir))

        cards = payload["scorecards"]
        self.assertEqual(len(cards), 3)
        for card in cards:
            self.assertIn("agent_id", card)
            self.assertIn("score", card)
            self.assertIn("grade", card)
            self.assertEqual(
                set(card["categories"]),
                {
                    "survival",
                    "risk_management",
                    "drawdown_resilience",
                    "stability",
                    "liquidation_resistance",
                    "decision_integrity",
                },
            )

    def test_scorecards_missing_summary_returns_404(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                with self.assertRaises(HTTPException) as error:
                    await routes_module.get_replay_scorecards("missing-run")
                self.assertEqual(error.exception.status_code, 404)

        with tempfile.TemporaryDirectory() as log_dir:
            asyncio.run(run_flow(log_dir))


if __name__ == "__main__":
    unittest.main()
