import tempfile
import unittest

from agents.templates import build_default_agents
from scenarios.flash_crash import FlashCrashScenario
from simulation.config import RiskConfig, ScoreConfig
from simulation.engine import SimulationEngine
from simulation.failure_analysis import analyze_agent
from simulation.replay import ReplayRecorder
from simulation.scoring import ReliabilityScore, grade_for_score, score_agent


def _report(**overrides) -> dict:
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
        "decision_integrity_events": 0,
        "total_decisions": 30,
    }
    report.update(overrides)
    return report


def _scored(report: dict, config: ScoreConfig | None = None) -> ReliabilityScore:
    failure_result = analyze_agent(report, RiskConfig())
    return score_agent(report, failure_result, config)


class ScoreConfigTests(unittest.TestCase):
    def test_default_weights_sum_to_one(self) -> None:
        ScoreConfig().validate()  # must not raise

    def test_invalid_weights_raise(self) -> None:
        with self.assertRaises(ValueError):
            ScoreConfig(survival_weight=0.9).validate()


class ScoreAgentTests(unittest.TestCase):
    def test_clean_survivor_scores_high(self) -> None:
        result = _scored(_report())
        self.assertGreaterEqual(result.score, 85.0)
        self.assertEqual(result.grade, "A")

    def test_liquidated_agent_scores_low(self) -> None:
        result = _scored(
            _report(status="liquidated", equity=300.0, max_drawdown=0.7)
        )
        self.assertLess(result.score, 50.0)

    def test_survivor_outscores_liquidated(self) -> None:
        survivor = _scored(_report())
        liquidated = _scored(_report(status="liquidated", equity=300.0, max_drawdown=0.7))
        self.assertGreater(survivor.score, liquidated.score)

    def test_score_is_deterministic(self) -> None:
        report = _report(status="failed", equity=650.0, max_drawdown=0.45)
        first = _scored(report)
        second = _scored(report)
        self.assertEqual(first.score, second.score)
        self.assertEqual(first.components, second.components)

    def test_components_within_unit_range(self) -> None:
        result = _scored(_report(status="liquidated", equity=200.0, max_drawdown=0.8))
        for value in result.components.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_weighted_sum_matches_final_score(self) -> None:
        result = _scored(_report(status="failed", equity=700.0, max_drawdown=0.5))
        recomputed = round(100.0 * sum(result.weighted_components.values()), 2)
        self.assertAlmostEqual(result.score, recomputed, places=2)

    def test_decision_integrity_lowers_score(self) -> None:
        clean = _scored(_report(decision_integrity_events=0, total_decisions=30))
        noisy = _scored(_report(decision_integrity_events=30, total_decisions=30))

        self.assertEqual(clean.components["decision_integrity"], 1.0)
        self.assertEqual(noisy.components["decision_integrity"], 0.0)
        self.assertGreater(clean.score, noisy.score)

    def test_rationale_cites_integrity_events(self) -> None:
        result = _scored(_report(decision_integrity_events=4, total_decisions=30))
        self.assertTrue(any("Decision integrity" in line for line in result.rationale))

    def test_score_config_weights_are_respected(self) -> None:
        report = _report(status="liquidated", equity=300.0, max_drawdown=0.7)
        default_score = _scored(report).score
        survival_heavy = ScoreConfig(
            survival_weight=0.6,
            capital_preservation_weight=0.1,
            drawdown_control_weight=0.1,
            risk_discipline_weight=0.1,
            decision_integrity_weight=0.1,
        )
        heavy_score = _scored(report, survival_heavy).score
        # Survival is zero for a liquidated agent, so weighting it more heavily
        # must lower the overall score.
        self.assertLess(heavy_score, default_score)


class GradeBandTests(unittest.TestCase):
    def test_grade_boundaries(self) -> None:
        self.assertEqual(grade_for_score(100.0), "A")
        self.assertEqual(grade_for_score(85.0), "A")
        self.assertEqual(grade_for_score(84.99), "B")
        self.assertEqual(grade_for_score(70.0), "B")
        self.assertEqual(grade_for_score(69.99), "C")
        self.assertEqual(grade_for_score(55.0), "C")
        self.assertEqual(grade_for_score(54.99), "D")
        self.assertEqual(grade_for_score(40.0), "D")
        self.assertEqual(grade_for_score(39.99), "F")
        self.assertEqual(grade_for_score(0.0), "F")


class EngineScoringIntegrationTests(unittest.TestCase):
    def _run(self):
        with tempfile.TemporaryDirectory() as log_dir:
            return SimulationEngine(
                agents=build_default_agents(),
                scenario=FlashCrashScenario(),
                max_ticks=30,
                recorder=ReplayRecorder(log_dir=log_dir),
            ).run()

    def test_simulation_exposes_reliability_reports(self) -> None:
        result = self._run()

        self.assertEqual(len(result.reliability_reports), 3)
        for report in result.reliability_reports:
            for field_name in (
                "agent_id",
                "score",
                "grade",
                "components",
                "weighted_components",
                "rationale",
            ):
                self.assertIn(field_name, report)
            self.assertGreaterEqual(report["score"], 0.0)
            self.assertLessEqual(report["score"], 100.0)

    def test_existing_reports_unchanged_in_shape(self) -> None:
        result = self._run()

        self.assertEqual(len(result.agent_reports), 3)
        for report in result.agent_reports:
            for field_name in ("agent_id", "status", "equity", "max_drawdown", "behavior_counters"):
                self.assertIn(field_name, report)

        self.assertEqual(len(result.failure_reports), 3)
        for report in result.failure_reports:
            for field_name in (
                "agent_id",
                "status",
                "summary",
                "primary_failure_reason",
                "risk_flags",
                "recommended_fix",
            ):
                self.assertIn(field_name, report)


if __name__ == "__main__":
    unittest.main()
