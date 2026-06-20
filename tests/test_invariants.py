"""Invariants that must hold for every DUAT run, across scenarios and agents.

These guard the financial accounting, status machine, score ranges, and replay
determinism that the product's claims depend on.
"""

import math

import pytest

from agents.templates import build_default_agents
from scenarios.registry import get_scenario
from simulation.engine import SimulationEngine
from simulation.portfolio import ACTIVE, FAILED, LIQUIDATED
from simulation.replay import ReplayRecorder

REPRESENTATIVE_SCENARIOS = ("flash-crash", "liquidation-cascade", "stablecoin-depeg")
TERMINAL_STATUSES = (FAILED, LIQUIDATED)


def _run(tmp_path, scenario_id: str, ticks: int = 20):
    engine = SimulationEngine(
        agents=build_default_agents(),
        scenario=get_scenario(scenario_id),
        max_ticks=ticks,
        recorder=ReplayRecorder(log_dir=str(tmp_path)),
    )
    result = engine.run()
    entries = [entry.to_dict() for entry in engine.recorder.entries]
    return result, entries


@pytest.mark.parametrize("scenario_id", REPRESENTATIVE_SCENARIOS)
def test_equity_accounting_is_consistent(tmp_path, scenario_id):
    _, entries = _run(tmp_path, scenario_id)

    for entry in entries:
        portfolio = entry["portfolio_state"]
        price = entry["market_state"]["current_price"]
        recomputed = portfolio["cash"] + portfolio["position"] * price
        # Allow for the portfolio's 2-decimal rounding of equity/cash.
        assert abs(portfolio["equity"] - recomputed) <= 0.05


@pytest.mark.parametrize("scenario_id", REPRESENTATIVE_SCENARIOS)
def test_cash_never_negative(tmp_path, scenario_id):
    _, entries = _run(tmp_path, scenario_id)
    for entry in entries:
        assert entry["portfolio_state"]["cash"] >= -1e-9


@pytest.mark.parametrize("scenario_id", REPRESENTATIVE_SCENARIOS)
def test_status_never_recovers(tmp_path, scenario_id):
    _, entries = _run(tmp_path, scenario_id)

    last_status: dict[str, str] = {}
    for entry in entries:
        agent = entry["agent"]
        status = entry["portfolio_state"]["status"]
        assert status in (ACTIVE, FAILED, LIQUIDATED)

        previous = last_status.get(agent)
        if previous in TERMINAL_STATUSES:
            # Once terminal, status is sticky — it must never change back.
            assert status == previous, f"{agent} recovered from {previous} to {status}"
        last_status[agent] = status


@pytest.mark.parametrize("scenario_id", REPRESENTATIVE_SCENARIOS)
def test_drawdown_bounded(tmp_path, scenario_id):
    result, entries = _run(tmp_path, scenario_id)

    for entry in entries:
        drawdown = entry["portfolio_state"]["max_drawdown"]
        assert 0.0 <= drawdown <= 1.0

    for report in result.to_dict()["agent_reports"]:
        assert 0.0 <= report["max_drawdown"] <= 1.0


@pytest.mark.parametrize("scenario_id", REPRESENTATIVE_SCENARIOS)
def test_reliability_scores_finite_and_in_range(tmp_path, scenario_id):
    result, _ = _run(tmp_path, scenario_id)

    reports = result.to_dict()["reliability_reports"]
    assert reports
    for report in reports:
        score = report["score"]
        assert isinstance(score, float)
        assert math.isfinite(score)
        assert 0.0 <= score <= 100.0
        assert report["grade"] in {"A", "B", "C", "D", "F"}


@pytest.mark.parametrize("scenario_id", REPRESENTATIVE_SCENARIOS)
def test_replay_is_deterministic(tmp_path, scenario_id):
    """Identical inputs produce an identical replay body."""
    _, first = _run(tmp_path / "a", scenario_id)
    _, second = _run(tmp_path / "b", scenario_id)
    assert first == second
