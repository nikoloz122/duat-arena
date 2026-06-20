import tempfile
import unittest

from agents.templates import build_default_agents
from scenarios.liquidation_cascade import LiquidationCascadeScenario
from scenarios.oracle_failure import OracleFailureScenario
from scenarios.registry import (
    DEFAULT_SCENARIO_ID,
    get_scenario,
    list_scenarios,
    scenario_ids,
)
from scenarios.stablecoin_depeg import StablecoinDepegScenario
from simulation.engine import SimulationEngine
from simulation.events import EventType
from simulation.market import MarketState
from simulation.replay import ReplayRecorder
from simulation.replay_parser import load_replay


class OracleFailureTests(unittest.TestCase):
    def test_dislocation_mutates_state(self) -> None:
        state = MarketState()
        event = OracleFailureScenario().apply(4, state)

        self.assertIsNotNone(event)
        self.assertEqual(event.type, EventType.CHAOS_INJECTION)
        self.assertEqual(event.payload["shock"], "oracle_dislocation")
        self.assertEqual(state.current_price, 60.0)
        self.assertEqual(state.volatility, 0.33)
        self.assertEqual(state.market_sentiment, -0.4)

    def test_correction_snaps_back(self) -> None:
        state = MarketState(current_price=60.0, volatility=0.3)
        event = OracleFailureScenario().apply(6, state)

        self.assertIsNotNone(event)
        self.assertEqual(event.payload["shock"], "oracle_correction")
        self.assertEqual(state.current_price, 75.0)
        self.assertEqual(state.volatility, 0.2)

    def test_quiet_tick_returns_none(self) -> None:
        self.assertIsNone(OracleFailureScenario().apply(5, MarketState()))


class StablecoinDepegTests(unittest.TestCase):
    def test_onset_mutates_state(self) -> None:
        state = MarketState()
        event = StablecoinDepegScenario().apply(3, state)

        self.assertIsNotNone(event)
        self.assertEqual(event.type, EventType.CHAOS_INJECTION)
        self.assertEqual(event.payload["shock"], "depeg_onset")
        self.assertEqual(state.current_price, 96.0)
        self.assertEqual(state.market_sentiment, -0.05)
        self.assertEqual(state.liquidity, 970.0)
        self.assertEqual(state.volatility, 0.07)

    def test_deepening_is_worse_than_onset(self) -> None:
        onset_state = MarketState()
        StablecoinDepegScenario().apply(3, onset_state)

        deep_state = MarketState()
        deep_event = StablecoinDepegScenario().apply(8, deep_state)

        self.assertEqual(deep_event.payload["shock"], "depeg_deepening")
        # Deeper tick applies a larger single-step decay than the onset tick.
        self.assertLess(deep_state.current_price, onset_state.current_price)

    def test_outside_window_returns_none(self) -> None:
        self.assertIsNone(StablecoinDepegScenario().apply(2, MarketState()))
        self.assertIsNone(StablecoinDepegScenario().apply(9, MarketState()))


class LiquidationCascadeTests(unittest.TestCase):
    def test_first_wave_mutates_state(self) -> None:
        state = MarketState()
        event = LiquidationCascadeScenario().apply(3, state)

        self.assertIsNotNone(event)
        self.assertEqual(event.type, EventType.CHAOS_INJECTION)
        self.assertEqual(event.payload["wave"], 1)
        self.assertEqual(state.current_price, 90.0)
        self.assertEqual(state.liquidity, 850.0)
        self.assertEqual(state.volatility, 0.15)
        self.assertEqual(state.market_sentiment, -0.1)

    def test_waves_compound(self) -> None:
        scenario = LiquidationCascadeScenario()
        wave1 = scenario.apply(3, MarketState())
        wave3 = scenario.apply(7, MarketState())

        self.assertEqual(wave1.payload["wave"], 1)
        self.assertEqual(wave3.payload["wave"], 3)

    def test_non_cascade_tick_returns_none(self) -> None:
        self.assertIsNone(LiquidationCascadeScenario().apply(4, MarketState()))


class ScenarioRegistryTests(unittest.TestCase):
    def test_registry_lists_all_six_scenarios(self) -> None:
        ids = set(scenario_ids())
        self.assertEqual(
            ids,
            {
                "flash-crash",
                "liquidity-drain",
                "panic-contagion",
                "oracle-failure",
                "stablecoin-depeg",
                "liquidation-cascade",
            },
        )

    def test_listing_has_id_name_description(self) -> None:
        for entry in list_scenarios():
            self.assertTrue(entry["id"])
            self.assertTrue(entry["name"])
            self.assertTrue(entry["description"])

    def test_get_scenario_by_id(self) -> None:
        scenario = get_scenario("oracle-failure")
        self.assertEqual(scenario.id, "oracle-failure")

    def test_unknown_scenario_falls_back_to_default(self) -> None:
        scenario = get_scenario("does-not-exist")
        self.assertEqual(scenario.id, DEFAULT_SCENARIO_ID)


class NewScenarioEngineTests(unittest.TestCase):
    def _run(self, scenario_id: str):
        with tempfile.TemporaryDirectory() as log_dir:
            result = SimulationEngine(
                agents=build_default_agents(),
                scenario=get_scenario(scenario_id),
                max_ticks=10,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()
            replay = load_replay(result.replay_id, log_dir=log_dir)
            return result, replay

    def test_each_new_scenario_runs_end_to_end(self) -> None:
        for scenario_id in ("oracle-failure", "stablecoin-depeg", "liquidation-cascade"):
            with self.subTest(scenario=scenario_id):
                result, replay = self._run(scenario_id)
                self.assertEqual(result.ticks, 10)
                self.assertEqual(len(result.reliability_reports), 3)
                self.assertTrue(replay["events"])
                self.assertIsNotNone(replay["manifest"])
                self.assertEqual(replay["manifest"]["scenario_id"], scenario_id)


if __name__ == "__main__":
    unittest.main()
