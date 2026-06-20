import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import backend.api.routes as routes_module
from agents.base import AgentDecision
from agents.templates import build_default_agents
from backend.api.routes import SimulationRunRequest
from backend.main import app
from scenarios.flash_crash import FlashCrashScenario
from scenarios.liquidity_drain import LiquidityDrainScenario
from scenarios.panic_contagion import PanicContagionScenario
from simulation.behavior import BehaviorTracker
from simulation.config import RiskConfig, SimulationConfig
from simulation.failure_analysis import analyze_agent
from simulation.engine import SimulationEngine
from simulation.market import MarketState
from simulation.portfolio import PortfolioState
from simulation.replay import ReplayRecorder
from simulation.replay_parser import ReplayNotFoundError, load_replay


class SimulationStabilizationTests(unittest.TestCase):
    def test_simulation_saves_and_loads_replay(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=build_default_agents(),
                scenario=FlashCrashScenario(),
                max_ticks=6,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

            replay_path = Path(result.replay_path)
            replay = load_replay(result.replay_id, log_dir=log_dir)

            self.assertTrue(replay_path.exists())
            self.assertEqual(result.total_events, 18)
            self.assertEqual(replay["total_events"], result.total_events)
            self.assertEqual(replay["final_market_state"]["current_price"], result.final_price)
            self.assertEqual(replay["simulation_duration"], 5.0)

    def test_replay_entries_keep_expected_schema(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=build_default_agents(),
                scenario=FlashCrashScenario(),
                max_ticks=6,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()
            replay = load_replay(result.replay_id, log_dir=log_dir)

            first_event = replay["events"][0]
            expected_fields = {
                "timestamp",
                "tick",
                "agent",
                "action",
                "reason",
                "market_state",
                "scenario_event",
                "portfolio_state",
                "behavior_counters",
                "intended_action",
                "executed_action",
                "normalization_notes",
            }
            self.assertEqual(set(first_event.keys()), expected_fields)
            self.assertIn("current_price", first_event["market_state"])
            self.assertIn("liquidity", first_event["market_state"])
            self.assertIn("equity", first_event["portfolio_state"])
            self.assertIn("buy_count", first_event["behavior_counters"])

    def test_missing_replay_raises_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            with self.assertRaises(ReplayNotFoundError):
                load_replay("missing-replay", log_dir=log_dir)

    def test_flash_crash_mutates_market_state_deterministically(self) -> None:
        market_state = MarketState()
        scenario = FlashCrashScenario()

        no_event = scenario.apply(2, market_state)
        self.assertIsNone(no_event)
        self.assertEqual(market_state.current_price, 100.0)

        event = scenario.apply(3, market_state)
        self.assertIsNotNone(event)
        self.assertEqual(market_state.current_price, 68.0)
        self.assertEqual(market_state.liquidity, 420.0)
        self.assertEqual(market_state.volatility, 0.37)
        self.assertEqual(market_state.market_sentiment, -0.85)

    def test_agent_decisions_use_structured_interface(self) -> None:
        market_state = MarketState(liquidity=400.0, volatility=0.3)

        for agent in build_default_agents():
            decision = agent.decide(tick=3, market_state=market_state)
            self.assertIsInstance(decision, AgentDecision)
            self.assertIn(decision.action, {"buy", "sell", "hold", "reduce_exposure"})
            self.assertGreaterEqual(decision.confidence, 0.0)

    def test_engine_outputs_are_deterministic_except_replay_identity(self) -> None:
        with tempfile.TemporaryDirectory() as first_log_dir, tempfile.TemporaryDirectory() as second_log_dir:
            first = SimulationEngine(
                agents=build_default_agents(),
                scenario=FlashCrashScenario(),
                max_ticks=6,
                recorder=ReplayRecorder(log_dir=first_log_dir),
            ).run()
            second = SimulationEngine(
                agents=build_default_agents(),
                scenario=FlashCrashScenario(),
                max_ticks=6,
                recorder=ReplayRecorder(log_dir=second_log_dir),
            ).run()

            self.assertNotEqual(first.replay_id, second.replay_id)
            self.assertEqual(first.ticks, second.ticks)
            self.assertEqual(first.total_events, second.total_events)
            self.assertEqual(first.panic_sell_count, second.panic_sell_count)
            self.assertEqual(first.normal_sell_count, second.normal_sell_count)
            self.assertEqual(first.final_price, second.final_price)
            self.assertEqual(first.final_liquidity, second.final_liquidity)
            self.assertEqual(first.contagion_score, second.contagion_score)

    def test_api_route_prefixes_are_not_duplicated(self) -> None:
        paths = {route.path for route in app.routes if hasattr(route, "path")}

        self.assertIn("/api/simulations/run", paths)
        self.assertIn("/api/replays/{replay_id}", paths)
        self.assertNotIn("/api/api/simulations/run", paths)

    def test_api_handlers_run_and_load_replay(self) -> None:
        async def run_flow(log_dir: str) -> None:
            with patch.object(routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)):
                result = await routes_module.run_simulation(SimulationRunRequest(ticks=6))
                replay = await routes_module.get_replay(result["replay_id"])

            self.assertEqual(result["total_events"], replay["total_events"])
            self.assertEqual(result["final_price"], replay["final_market_state"]["current_price"])

        with tempfile.TemporaryDirectory() as log_dir:
            asyncio.run(run_flow(log_dir))

    def test_api_rejects_unavailable_agent_count(self) -> None:
        async def run_flow() -> None:
            with self.assertRaises(HTTPException) as error:
                await routes_module.run_simulation(SimulationRunRequest(ticks=6, agent_count=4))
            self.assertEqual(error.exception.status_code, 400)

        asyncio.run(run_flow())

    def test_secondary_scenarios_mutate_expected_market_fields(self) -> None:
        liquidity_state = MarketState()
        liquidity_event = LiquidityDrainScenario().apply(2, liquidity_state)

        self.assertIsNotNone(liquidity_event)
        self.assertEqual(liquidity_state.liquidity, 780.0)
        self.assertEqual(liquidity_state.volatility, 0.13)

        panic_state = MarketState()
        panic_event = PanicContagionScenario().apply(5, panic_state)

        self.assertIsNotNone(panic_event)
        self.assertEqual(panic_state.market_sentiment, -0.18)
        self.assertEqual(panic_state.volatility, 0.1)

    def test_simulation_result_includes_agent_reports(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=build_default_agents(),
                scenario=FlashCrashScenario(),
                max_ticks=6,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

        self.assertEqual(len(result.agent_reports), 3)
        report = result.agent_reports[0]
        for field_name in ("agent_id", "status", "equity", "max_drawdown", "behavior_counters"):
            self.assertIn(field_name, report)
        self.assertIn(report["status"], {"active", "failed", "liquidated"})


class PortfolioStateTests(unittest.TestCase):
    def _portfolio(self, **kwargs) -> PortfolioState:
        return PortfolioState(agent_id="agent-x", initial_cash=1000.0, **kwargs)

    def test_buy_decreases_cash_and_increases_position_and_exposure(self) -> None:
        portfolio = self._portfolio()
        portfolio.apply_action("buy", price=100.0, size=2.0)

        self.assertEqual(portfolio.position, 2.0)
        self.assertEqual(portfolio.cash, 800.0)
        self.assertEqual(portfolio.exposure, 200.0)
        self.assertEqual(portfolio.average_entry_price, 100.0)

    def test_sell_increases_cash_and_reduces_position_and_exposure(self) -> None:
        portfolio = self._portfolio()
        portfolio.apply_action("buy", price=100.0, size=2.0)
        portfolio.apply_action("sell", price=110.0, size=1.0)

        self.assertEqual(portfolio.position, 1.0)
        self.assertEqual(portfolio.cash, 910.0)
        self.assertEqual(portfolio.exposure, 110.0)
        self.assertEqual(portfolio.realized_pnl, 10.0)

    def test_sell_cannot_exceed_position(self) -> None:
        portfolio = self._portfolio()
        portfolio.apply_action("buy", price=100.0, size=1.0)
        portfolio.apply_action("sell", price=100.0, size=5.0)

        self.assertEqual(portfolio.position, 0.0)
        self.assertEqual(portfolio.average_entry_price, 0.0)

    def test_reduce_exposure_reduces_position(self) -> None:
        portfolio = self._portfolio()
        portfolio.apply_action("buy", price=100.0, size=3.0)
        portfolio.apply_action("reduce_exposure", price=100.0, size=1.0)

        self.assertEqual(portfolio.position, 2.0)

    def test_hold_does_not_change_holdings(self) -> None:
        portfolio = self._portfolio()
        portfolio.apply_action("buy", price=100.0, size=1.0)
        cash_before = portfolio.cash
        position_before = portfolio.position
        portfolio.apply_action("hold", price=120.0, size=1.0)

        self.assertEqual(portfolio.cash, cash_before)
        self.assertEqual(portfolio.position, position_before)

    def test_update_market_price_changes_equity_and_unrealized_pnl(self) -> None:
        portfolio = self._portfolio()
        portfolio.apply_action("buy", price=100.0, size=2.0)
        portfolio.update_market_price(120.0)

        self.assertEqual(portfolio.unrealized_pnl, 40.0)
        self.assertEqual(portfolio.equity, 1040.0)

    def test_max_drawdown_updates_on_price_drop(self) -> None:
        portfolio = self._portfolio()
        portfolio.apply_action("buy", price=100.0, size=5.0)
        portfolio.update_market_price(60.0)

        self.assertGreater(portfolio.max_drawdown, 0.0)

    def test_liquidation_triggers_below_threshold(self) -> None:
        portfolio = self._portfolio(risk_config=RiskConfig(liquidation_equity_ratio=0.6))
        portfolio.apply_action("buy", price=100.0, size=10.0)
        portfolio.update_market_price(40.0)

        self.assertEqual(portfolio.status, "liquidated")
        self.assertIsNotNone(portfolio.failure_reason)

    def test_failed_or_liquidated_cannot_increase_exposure(self) -> None:
        portfolio = self._portfolio(risk_config=RiskConfig(liquidation_equity_ratio=0.6))
        portfolio.apply_action("buy", price=100.0, size=10.0)
        portfolio.update_market_price(40.0)

        self.assertFalse(portfolio.can_increase_exposure())

    def test_initial_cash_is_configurable(self) -> None:
        portfolio = PortfolioState(agent_id="agent-x", initial_cash=500.0)
        self.assertEqual(portfolio.cash, 500.0)
        self.assertEqual(portfolio.equity, 500.0)


class BehaviorTrackerTests(unittest.TestCase):
    def test_action_counters_increment(self) -> None:
        tracker = BehaviorTracker("agent-x")
        tracker.record("buy", exposure_before=0.0, exposure_after=100.0)
        tracker.record("sell", exposure_before=100.0, exposure_after=50.0)
        tracker.record("hold", exposure_before=50.0, exposure_after=50.0)
        tracker.record("reduce_exposure", exposure_before=50.0, exposure_after=20.0)

        counters = tracker.to_dict()
        self.assertEqual(counters["buy_count"], 1)
        self.assertEqual(counters["sell_count"], 1)
        self.assertEqual(counters["hold_count"], 1)
        self.assertEqual(counters["reduce_exposure_count"], 1)

    def test_exposure_change_counters(self) -> None:
        tracker = BehaviorTracker("agent-x")
        tracker.record("buy", exposure_before=0.0, exposure_after=100.0)
        tracker.record("sell", exposure_before=100.0, exposure_after=50.0)
        tracker.record("hold", exposure_before=50.0, exposure_after=50.0)

        counters = tracker.to_dict()
        self.assertEqual(counters["exposure_increase_count"], 1)
        self.assertEqual(counters["exposure_reduction_count"], 1)

    def test_simulation_config_owns_risk_config(self) -> None:
        config = SimulationConfig()
        self.assertIsInstance(config.risk, RiskConfig)
        self.assertEqual(config.initial_cash, 1000.0)


class ConsequenceGenerationTests(unittest.TestCase):
    def _flash_crash_reports(self, log_dir: str):
        return SimulationEngine(
            agents=build_default_agents(),
            scenario=FlashCrashScenario(),
            max_ticks=30,
            recorder=ReplayRecorder(log_dir=log_dir),
        ).run()

    def test_initial_exposure_applied_correctly(self) -> None:
        portfolio = PortfolioState(agent_id="agent-x", initial_cash=1000.0)
        portfolio.seed_position(price=100.0, allocation_value=500.0)

        self.assertEqual(portfolio.position, 5.0)
        self.assertEqual(portfolio.exposure, 500.0)
        self.assertEqual(portfolio.cash, 500.0)
        self.assertEqual(portfolio.equity, 1000.0)

    def test_momentum_agent_can_establish_exposure(self) -> None:
        from agents.templates import MomentumAgent

        decision = MomentumAgent().decide(tick=0, market_state=MarketState())
        self.assertEqual(decision.action, "buy")

    def test_portfolios_diverge_under_flash_crash(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = self._flash_crash_reports(log_dir)

        equities = [report["equity"] for report in result.agent_reports]
        self.assertGreater(len(set(equities)), 1)

    def test_drawdowns_differ_between_agents(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = self._flash_crash_reports(log_dir)

        drawdowns = [report["max_drawdown"] for report in result.agent_reports]
        self.assertGreater(len(set(drawdowns)), 1)

    def test_at_least_one_agent_experiences_failure(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = self._flash_crash_reports(log_dir)

        statuses = {report["status"] for report in result.agent_reports}
        self.assertTrue(statuses & {"failed", "liquidated"})

    def test_exposure_changes_occur(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = self._flash_crash_reports(log_dir)

        total_exposure_changes = sum(
            report["behavior_counters"]["exposure_increase_count"]
            + report["behavior_counters"]["exposure_reduction_count"]
            for report in result.agent_reports
        )
        self.assertGreater(total_exposure_changes, 0)

    def test_failure_analysis_receives_meaningful_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = self._flash_crash_reports(log_dir)

        informative = [
            report for report in result.failure_reports
            if report["risk_flags"] or report["primary_failure_reason"]
        ]
        self.assertGreater(len(informative), 0)

    def test_behavior_counters_remain_correct(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = self._flash_crash_reports(log_dir)

        momentum = next(
            report for report in result.agent_reports
            if report["agent_id"] == "agent-momentum-001"
        )
        self.assertGreater(momentum["behavior_counters"]["buy_count"], 0)

    def test_surviving_agents_matches_portfolio_status(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = self._flash_crash_reports(log_dir)

        active_agents = {
            report["agent_id"]
            for report in result.agent_reports
            if report["status"] == "active"
        }
        self.assertEqual(set(result.surviving_agents), active_agents)
        # The failed agent must not be reported as surviving.
        failed_agents = {
            report["agent_id"]
            for report in result.agent_reports
            if report["status"] in ("failed", "liquidated")
        }
        self.assertTrue(failed_agents)
        self.assertFalse(failed_agents & set(result.surviving_agents))


class PanicDetectionTests(unittest.TestCase):
    def test_panic_detection_uses_attribute_not_class_name(self) -> None:
        from agents.base import AgentDecision, TradingAgent
        from scenarios.flash_crash import FlashCrashScenario

        class RenamedReactiveAgent(TradingAgent):
            def __init__(self) -> None:
                super().__init__(agent_id="agent-reactive-001", risk_profile="high")
                self.is_panic_agent = True

            def decide(self, tick, market_state) -> AgentDecision:
                return AgentDecision(action="hold")

        engine = SimulationEngine(
            agents=[RenamedReactiveAgent()],
            scenario=FlashCrashScenario(),
            max_ticks=5,
            recorder=ReplayRecorder(log_dir=tempfile.mkdtemp()),
        )
        agent = engine.agents[0]
        # Class name contains no "panic", but the explicit contract marks it panic.
        self.assertNotIn("panic", agent.__class__.__name__.lower())
        self.assertTrue(engine._is_panic_agent(agent))

    def test_non_panic_agent_not_flagged(self) -> None:
        from agents.templates import ConservativeAgent
        from scenarios.flash_crash import FlashCrashScenario

        engine = SimulationEngine(
            agents=[ConservativeAgent()],
            scenario=FlashCrashScenario(),
            max_ticks=5,
            recorder=ReplayRecorder(log_dir=tempfile.mkdtemp()),
        )
        self.assertFalse(engine._is_panic_agent(engine.agents[0]))


class FailureAnalysisTests(unittest.TestCase):
    def _report(self, **overrides) -> dict:
        report = {
            "agent_id": "agent-x",
            "initial_cash": 1000.0,
            "equity": 1000.0,
            "max_drawdown": 0.0,
            "status": "active",
            "behavior_counters": {
                "buy_count": 0,
                "sell_count": 0,
                "hold_count": 0,
                "reduce_exposure_count": 0,
                "exposure_increase_count": 0,
                "exposure_reduction_count": 0,
            },
        }
        report.update(overrides)
        return report

    def test_survived_agent(self) -> None:
        result = analyze_agent(self._report(), RiskConfig())

        self.assertEqual(result.status, "active")
        self.assertIsNone(result.primary_failure_reason)
        self.assertEqual(result.risk_flags, [])
        self.assertEqual(result.recommended_fix, [])
        self.assertIn("maintained capital", result.summary)

    def test_failed_agent(self) -> None:
        result = analyze_agent(
            self._report(status="failed", max_drawdown=0.45), RiskConfig()
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.primary_failure_reason, "Drawdown exceeded configured threshold.")
        self.assertIn("failure_threshold_breach", result.risk_flags)
        self.assertIn("high_drawdown", result.risk_flags)
        self.assertIn("Improve drawdown control.", result.recommended_fix)

    def test_liquidated_agent(self) -> None:
        result = analyze_agent(
            self._report(status="liquidated", equity=500.0, max_drawdown=0.5), RiskConfig()
        )

        self.assertEqual(result.status, "liquidated")
        self.assertEqual(result.primary_failure_reason, "Equity fell below liquidation threshold.")
        self.assertIn("liquidation_threshold_breach", result.risk_flags)
        self.assertIn("Lower maximum exposure.", result.recommended_fix)

    def test_risk_flag_repeated_exposure_increase(self) -> None:
        counters = {
            "buy_count": 4,
            "sell_count": 0,
            "hold_count": 0,
            "reduce_exposure_count": 0,
            "exposure_increase_count": 4,
            "exposure_reduction_count": 0,
        }
        result = analyze_agent(self._report(behavior_counters=counters), RiskConfig())

        self.assertIn("repeated_exposure_increase", result.risk_flags)
        self.assertIn("Limit position growth.", result.recommended_fix)

    def test_recommendation_reduce_exposure_earlier(self) -> None:
        result = analyze_agent(
            self._report(status="liquidated", equity=500.0), RiskConfig()
        )
        self.assertIn("Reduce exposure earlier.", result.recommended_fix)

    def test_simulation_result_includes_failure_reports(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=build_default_agents(),
                scenario=FlashCrashScenario(),
                max_ticks=6,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

        self.assertEqual(len(result.failure_reports), 3)
        report = result.failure_reports[0]
        for field_name in ("agent_id", "status", "summary", "primary_failure_reason", "risk_flags", "recommended_fix"):
            self.assertIn(field_name, report)
