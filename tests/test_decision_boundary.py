import math
import tempfile
import unittest
from pathlib import Path

from agents.base import AgentDecision, TradingAgent
from scenarios.flash_crash import FlashCrashScenario
from simulation.config import RiskConfig, SimulationConfig
from simulation.decision_normalizer import (
    DEFAULT_CONFIDENCE,
    DEFAULT_SIZE,
    MAX_SIZE,
    normalize_decision,
)
from simulation.engine import SimulationEngine
from simulation.market import MarketState
from simulation.replay import ReplayRecorder
from simulation.replay_parser import load_replay


class _AlwaysBuyAgent(TradingAgent):
    def __init__(self, agent_id: str = "agent-always-buy") -> None:
        super().__init__(agent_id=agent_id, risk_profile="high")

    def decide(self, tick: int, market_state: MarketState) -> AgentDecision:
        return AgentDecision(action="buy", size=1.0, reason="always buys", confidence=0.9)


class _RaisingAgent(TradingAgent):
    def __init__(self, agent_id: str = "agent-raises") -> None:
        super().__init__(agent_id=agent_id, risk_profile="high")

    def decide(self, tick: int, market_state: MarketState) -> AgentDecision:
        raise RuntimeError("boom")


class _SnapshotAgent(TradingAgent):
    """Opts into the read-only portfolio snapshot and inspects it."""

    def __init__(self, agent_id: str = "agent-snapshot") -> None:
        super().__init__(agent_id=agent_id, risk_profile="moderate")
        self.received_snapshot = None
        self.snapshot_is_read_only = False

    def decide(self, tick: int, market_state: MarketState, portfolio_snapshot=None) -> AgentDecision:
        self.received_snapshot = portfolio_snapshot
        if portfolio_snapshot is not None:
            try:
                portfolio_snapshot["cash"] = -1
            except TypeError:
                self.snapshot_is_read_only = True
        return AgentDecision(action="hold")


class DecisionNormalizerTests(unittest.TestCase):
    def test_valid_decision_is_a_no_op(self) -> None:
        original = AgentDecision(action="buy", size=1.1, reason="trend", confidence=0.68)
        result = normalize_decision(original)

        self.assertEqual(result.notes, [])
        self.assertEqual(result.decision.action, "buy")
        self.assertEqual(result.decision.size, 1.1)
        self.assertEqual(result.decision.reason, "trend")
        self.assertEqual(result.decision.confidence, 0.68)

    def test_invalid_action_coerced_to_hold(self) -> None:
        result = normalize_decision(AgentDecision(action="teleport", size=1.0))

        self.assertEqual(result.decision.action, "hold")
        self.assertTrue(any("action" in note for note in result.notes))

    def test_nan_size_rejected(self) -> None:
        result = normalize_decision(AgentDecision(action="buy", size=float("nan")))

        self.assertEqual(result.decision.size, DEFAULT_SIZE)
        self.assertTrue(any("finite" in note for note in result.notes))

    def test_inf_size_rejected(self) -> None:
        result = normalize_decision(AgentDecision(action="buy", size=float("inf")))

        self.assertEqual(result.decision.size, DEFAULT_SIZE)
        self.assertFalse(math.isinf(result.decision.size))

    def test_negative_size_rejected(self) -> None:
        result = normalize_decision(AgentDecision(action="buy", size=-3.0))

        self.assertEqual(result.decision.size, DEFAULT_SIZE)
        self.assertTrue(any("negative" in note for note in result.notes))

    def test_zero_size_defaulted(self) -> None:
        result = normalize_decision(AgentDecision(action="buy", size=0.0))

        self.assertEqual(result.decision.size, DEFAULT_SIZE)

    def test_oversized_size_clamped(self) -> None:
        result = normalize_decision(AgentDecision(action="buy", size=MAX_SIZE * 10))

        self.assertEqual(result.decision.size, MAX_SIZE)

    def test_missing_confidence_defaulted(self) -> None:
        result = normalize_decision({"action": "hold", "size": 1.0, "confidence": None})

        self.assertEqual(result.decision.confidence, DEFAULT_CONFIDENCE)

    def test_confidence_clamped_to_range(self) -> None:
        high = normalize_decision(AgentDecision(action="hold", confidence=5.0))
        low = normalize_decision(AgentDecision(action="hold", confidence=-5.0))

        self.assertEqual(high.decision.confidence, 1.0)
        self.assertEqual(low.decision.confidence, 0.0)

    def test_missing_reason_defaulted(self) -> None:
        result = normalize_decision({"action": "hold", "size": 1.0, "reason": None})

        self.assertEqual(result.decision.reason, "")

    def test_none_decision_returns_safe_hold(self) -> None:
        result = normalize_decision(None)

        self.assertEqual(result.decision.action, "hold")
        self.assertTrue(result.notes)

    def test_unsupported_type_returns_safe_hold(self) -> None:
        result = normalize_decision("not a decision")

        self.assertEqual(result.decision.action, "hold")
        self.assertTrue(result.notes)

    def test_dict_decision_supported(self) -> None:
        result = normalize_decision(
            {"action": "sell", "size": 2.0, "reason": "exit", "confidence": 0.7}
        )

        self.assertEqual(result.decision.action, "sell")
        self.assertEqual(result.decision.size, 2.0)
        self.assertEqual(result.notes, [])


class EngineBoundaryTests(unittest.TestCase):
    def test_raising_agent_does_not_crash_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=[_RaisingAgent()],
                scenario=FlashCrashScenario(),
                max_ticks=5,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertEqual(result.ticks, 5)
        # Every entry falls back to a safe hold with a recorded error note.
        for event in replay["events"]:
            self.assertEqual(event["executed_action"], "hold")
            self.assertTrue(event["normalization_notes"])
            self.assertTrue(any("raised" in note for note in event["normalization_notes"]))

    def test_intended_vs_executed_differ_on_override(self) -> None:
        config = SimulationConfig(
            risk=RiskConfig(liquidation_equity_ratio=0.95, failure_drawdown_ratio=0.05)
        )
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=[_AlwaysBuyAgent()],
                scenario=FlashCrashScenario(),
                max_ticks=30,
                recorder=ReplayRecorder(log_dir=log_dir),
                config=config,
            ).run()
            replay = load_replay(result.replay_id, log_dir=log_dir)

        overrides = [
            event
            for event in replay["events"]
            if event["intended_action"] == "buy" and event["executed_action"] == "hold"
        ]
        self.assertTrue(overrides, "expected at least one buy->hold override after failure")

    def test_manifest_is_persisted_and_reloadable(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=[_AlwaysBuyAgent(), _SnapshotAgent()],
                scenario=FlashCrashScenario(),
                max_ticks=5,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

            manifest_path = Path(log_dir) / f"{result.replay_id}.manifest.json"
            self.assertTrue(manifest_path.exists())

            replay = load_replay(result.replay_id, log_dir=log_dir)

        manifest = replay["manifest"]
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["scenario_id"], "flash-crash")
        self.assertEqual(manifest["ticks"], 5)
        self.assertIn("initial_cash", manifest["simulation_config"])
        self.assertIn("risk", manifest["simulation_config"])
        manifest_agent_ids = {a["id"] for a in manifest["agents"]}
        self.assertEqual(manifest_agent_ids, {"agent-always-buy", "agent-snapshot"})

    def test_old_replay_without_manifest_returns_none(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as log_dir:
            # Write an authentic legacy JSONL replay: old schema, no manifest,
            # none of the Phase 1 fields present.
            legacy_event = {
                "timestamp": "2026-01-01T09:30:00+00:00",
                "tick": 0,
                "agent": "agent-x",
                "action": "hold",
                "market_state": MarketState().to_dict(),
                "scenario_event": None,
                "reason": "legacy",
                "metadata": {"confidence": 0.5, "size": 1.0},
            }
            path = Path(log_dir) / "legacy-run.jsonl"
            path.write_text(json.dumps(legacy_event) + "\n", encoding="utf-8")

            replay = load_replay("legacy-run", log_dir=log_dir)

        self.assertIsNone(replay["manifest"])
        # Old entries still shape correctly; new fields fall back to action.
        self.assertEqual(replay["events"][0]["executed_action"], "hold")
        self.assertEqual(replay["events"][0]["intended_action"], "hold")
        self.assertEqual(replay["events"][0]["normalization_notes"], [])

    def test_read_only_portfolio_snapshot_passed_to_opt_in_agent(self) -> None:
        agent = _SnapshotAgent()
        with tempfile.TemporaryDirectory() as log_dir:
            SimulationEngine(
                agents=[agent],
                scenario=FlashCrashScenario(),
                max_ticks=3,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

        self.assertIsNotNone(agent.received_snapshot)
        self.assertIn("equity", agent.received_snapshot)
        self.assertIn("status", agent.received_snapshot)
        self.assertTrue(agent.snapshot_is_read_only)

    def test_replay_body_is_deterministic(self) -> None:
        def run(log_dir: str) -> str:
            result = SimulationEngine(
                agents=[_AlwaysBuyAgent()],
                scenario=FlashCrashScenario(),
                max_ticks=8,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()
            return Path(result.replay_path).read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(run(a), run(b))


if __name__ == "__main__":
    unittest.main()
