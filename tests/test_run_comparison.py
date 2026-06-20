import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import backend.api.routes as routes_module
from agents.templates import build_default_agents
from backend.api.routes import ReplayCompareRequest
from scenarios.registry import get_scenario
from simulation.engine import SimulationEngine
from simulation.market import MarketState
from simulation.replay import ReplayRecorder
from simulation.replay_parser import (
    list_runs,
    load_replay,
    load_run_summary,
)


def _run(log_dir: str, scenario_id: str = "flash-crash", ticks: int = 6):
    return SimulationEngine(
        agents=build_default_agents(),
        scenario=get_scenario(scenario_id),
        max_ticks=ticks,
        recorder=ReplayRecorder(log_dir=log_dir),
    ).run()


def _strip_identity(summary: dict) -> dict:
    clone = dict(summary)
    for key in ("run_id", "replay_id", "replay_path"):
        clone.pop(key, None)
    return clone


class RunPersistenceTests(unittest.TestCase):
    def test_summary_sidecar_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = _run(log_dir)
            summary_path = Path(log_dir) / f"{result.replay_id}.summary.json"
            self.assertTrue(summary_path.exists())

            with summary_path.open(encoding="utf-8") as f:
                summary = json.load(f)
            self.assertIn("reliability_reports", summary)
            self.assertEqual(len(summary["reliability_reports"]), 3)

    def test_parser_exposes_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = _run(log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertIsNotNone(replay["run_summary"])
        self.assertIn("reliability_reports", replay["run_summary"])

    def test_legacy_replay_has_no_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            legacy_event = {
                "timestamp": "2026-01-01T09:30:00+00:00",
                "tick": 0,
                "agent": "agent-x",
                "action": "hold",
                "market_state": MarketState().to_dict(),
            }
            path = Path(log_dir) / "legacy-run.jsonl"
            path.write_text(json.dumps(legacy_event) + "\n", encoding="utf-8")

            replay = load_replay("legacy-run", log_dir=log_dir)

        self.assertIsNone(replay["run_summary"])

    def test_summary_is_deterministic_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = _run(a, ticks=8)
            second = _run(b, ticks=8)
            first_summary = load_run_summary(first.replay_id, log_dir=a)
            second_summary = load_run_summary(second.replay_id, log_dir=b)

        self.assertEqual(_strip_identity(first_summary), _strip_identity(second_summary))


class ListRunsTests(unittest.TestCase):
    def test_list_runs_returns_brief_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            _run(log_dir, scenario_id="flash-crash")
            _run(log_dir, scenario_id="oracle-failure")

            runs = list_runs(log_dir=log_dir)

        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertIn("replay_id", run)
            self.assertEqual(run["agent_count"], 3)
            self.assertIsNotNone(run["scenario"])
            self.assertIsNotNone(run["best_score"])
            self.assertIsNotNone(run["best_grade"])

    def test_list_runs_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            self.assertEqual(list_runs(log_dir=log_dir), [])


class CompareApiTests(unittest.TestCase):
    def test_compare_returns_side_by_side(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                first = _run(log_dir, scenario_id="flash-crash")
                second = _run(log_dir, scenario_id="liquidation-cascade")
                return await routes_module.compare_replays(
                    ReplayCompareRequest(replay_ids=[first.replay_id, second.replay_id])
                )

        with tempfile.TemporaryDirectory() as log_dir:
            comparison = asyncio.run(run_flow(log_dir))

        self.assertEqual(len(comparison["runs"]), 2)
        for run in comparison["runs"]:
            self.assertIn("scenario", run)
            self.assertEqual(len(run["agents"]), 3)
            for agent in run["agents"]:
                self.assertIn("agent_id", agent)
                self.assertIn("score", agent)
                self.assertIn("grade", agent)

    def test_compare_unknown_replay_returns_404(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                real = _run(log_dir)
                with self.assertRaises(HTTPException) as error:
                    await routes_module.compare_replays(
                        ReplayCompareRequest(replay_ids=[real.replay_id, "missing-run"])
                    )
                self.assertEqual(error.exception.status_code, 404)

        with tempfile.TemporaryDirectory() as log_dir:
            asyncio.run(run_flow(log_dir))

    def test_list_replays_endpoint(self) -> None:
        async def run_flow(log_dir: str):
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                _run(log_dir)
                return await routes_module.list_replays()

        with tempfile.TemporaryDirectory() as log_dir:
            runs = asyncio.run(run_flow(log_dir))

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["agent_count"], 3)


if __name__ == "__main__":
    unittest.main()
