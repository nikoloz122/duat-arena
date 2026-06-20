"""Tests for the reliability scorecard assembler.

Deterministic and offline. Uses synthetic reliability + agent reports (the same
shape `score_agent` and the engine produce) so the assembler is exercised
without running a simulation or touching the network.
"""

import json

from simulation import scorecard
from simulation.config import RiskConfig

FLOOR = RiskConfig().liquidation_equity_ratio  # 0.6


def _reliability_report(agent_id="agent-x", score=72.5, grade="B"):
    return {
        "agent_id": agent_id,
        "score": score,
        "grade": grade,
        "components": {
            "survival": 1.0,
            "capital_preservation": 0.8,
            "drawdown_control": 0.6,
            "risk_discipline": 0.75,
            "decision_integrity": 0.5,
        },
        "weighted_components": {},
        "rationale": ["Agent survived the scenario with capital above risk thresholds."],
    }


def _agent_report(agent_id="agent-x", status="active", equity=800.0, initial_cash=1000.0):
    return {
        "agent_id": agent_id,
        "status": status,
        "equity": equity,
        "initial_cash": initial_cash,
    }


def test_score_and_grade_pass_through_unchanged():
    card = scorecard.build_scorecard(_agent_report(), _reliability_report(), [])
    assert card["score"] == 72.5
    assert card["grade"] == "B"
    assert card["status"] == "active"


def test_six_categories_present_and_mapped():
    card = scorecard.build_scorecard(_agent_report(), _reliability_report(), [])
    categories = card["categories"]

    assert set(categories.keys()) == {
        "survival",
        "risk_management",
        "drawdown_resilience",
        "stability",
        "liquidation_resistance",
        "decision_integrity",
    }
    # Mapped verbatim from the existing score components.
    assert categories["survival"] == 1.0
    assert categories["risk_management"] == 0.75
    assert categories["drawdown_resilience"] == 0.6
    assert categories["stability"] == 0.8
    assert categories["decision_integrity"] == 0.5
    # All values stay within 0..1.
    assert all(0.0 <= v <= 1.0 for v in categories.values())


def test_liquidation_resistance_derivation():
    # equity at the starting bankroll -> full resistance.
    full = scorecard.build_scorecard(
        _agent_report(equity=1000.0, initial_cash=1000.0), _reliability_report(), []
    )
    assert full["categories"]["liquidation_resistance"] == 1.0

    # equity exactly at the floor -> zero buffer.
    at_floor = scorecard.build_scorecard(
        _agent_report(equity=FLOOR * 1000.0, initial_cash=1000.0), _reliability_report(), []
    )
    assert at_floor["categories"]["liquidation_resistance"] == 0.0

    # liquidated -> always zero regardless of equity figure.
    liquidated = scorecard.build_scorecard(
        _agent_report(status="liquidated", equity=900.0), _reliability_report(), []
    )
    assert liquidated["categories"]["liquidation_resistance"] == 0.0


def test_explanation_includes_intercepted_count_when_violations_exist():
    from simulation import integrity

    agent_timeline = [
        {
            "tick": 3,
            "agent": "agent-x",
            "category": integrity.INVALID_ACTION,
            "label": integrity.CATEGORY_LABELS[integrity.INVALID_ACTION],
            "severity": "high",
            "note": "action 'yolo' is not allowed; coerced to 'hold'",
        }
    ]
    card = scorecard.build_scorecard(_agent_report(), _reliability_report(), agent_timeline)

    assert card["integrity"]["intervention_ticks"] == 1
    assert card["integrity"]["total"] == 1
    assert any("intercepted" in line.lower() for line in card["explanation"])


def test_scorecard_is_json_serializable():
    card = scorecard.build_scorecard(_agent_report(), _reliability_report(), [])
    # Round-trips cleanly (exportable JSON requirement).
    assert json.loads(json.dumps(card)) == card


def test_recommended_fixes_empty_when_clean():
    card = scorecard.build_scorecard(_agent_report(), _reliability_report(), [])
    assert card["recommended_fixes"] == []


def test_recommended_fixes_from_integrity_and_failure_do_not_affect_score():
    from simulation import integrity

    agent_timeline = [
        {
            "tick": 3,
            "agent": "agent-x",
            "category": integrity.OVERSIZED_POSITION,
            "label": integrity.CATEGORY_LABELS[integrity.OVERSIZED_POSITION],
            "severity": "medium",
            "note": "size 9.0 exceeds max 1.0; clamped to 1.0",
        }
    ]
    failure_report = {"agent_id": "agent-x", "risk_flags": ["liquidation_threshold_breach"]}
    card = scorecard.build_scorecard(
        _agent_report(),
        _reliability_report(),
        agent_timeline,
        failure_report=failure_report,
    )
    issues = [fix["issue"] for fix in card["recommended_fixes"]]
    assert "Oversized Position" in issues
    assert "Liquidation Breach" in issues
    # Remediation is presentational only — score and grade are untouched.
    assert card["score"] == 72.5
    assert card["grade"] == "B"


def test_build_scorecards_threads_failure_reports():
    summary = {
        "agent_reports": [_agent_report("agent-b", status="liquidated", equity=500.0)],
        "reliability_reports": [_reliability_report("agent-b", score=40.0, grade="D")],
        "failure_reports": [
            {"agent_id": "agent-b", "risk_flags": ["liquidation_threshold_breach"]}
        ],
    }
    cards = scorecard.build_scorecards(summary, [])
    fixes = cards[0]["recommended_fixes"]
    assert any(fix["issue"] == "Liquidation Breach" for fix in fixes)


def test_build_scorecards_joins_summary_and_events():
    summary = {
        "agent_reports": [_agent_report("agent-a"), _agent_report("agent-b", status="liquidated", equity=500.0)],
        "reliability_reports": [
            _reliability_report("agent-a", score=88.0, grade="A"),
            _reliability_report("agent-b", score=40.0, grade="D"),
        ],
    }
    events = [
        {
            "tick": 2,
            "agent": "agent-b",
            "normalization_notes": ["agent returned no decision; defaulted to safe hold"],
        }
    ]

    cards = scorecard.build_scorecards(summary, events)
    by_id = {c["agent_id"]: c for c in cards}

    assert set(by_id) == {"agent-a", "agent-b"}
    # Only agent-b had an intercepted decision.
    assert by_id["agent-a"]["integrity"]["intervention_ticks"] == 0
    assert by_id["agent-b"]["integrity"]["intervention_ticks"] == 1
    assert by_id["agent-b"]["categories"]["liquidation_resistance"] == 0.0
