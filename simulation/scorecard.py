"""Assemble a shareable, Moody's-style reliability scorecard per agent.

A scorecard is a presentation/explanation layer over facts a run already
produced: the reliability score (from `score_agent`), the per-agent report, and
the categorized decision-boundary interceptions (`simulation.integrity`).

It recomputes nothing about the score — the overall number and grade are taken
verbatim from the reliability report. The only derived value is
`liquidation_resistance`, a presentational view of how far equity sat above the
liquidation floor; it does not feed the weighted score. Everything here is
deterministic and replay-safe: it can be rebuilt from a persisted summary plus
replay events.
"""

from typing import Any, Dict, List, Optional

from simulation import integrity
from simulation.config import RiskConfig
from simulation.remediation import build_remediation

DEFAULT_LIQUIDATION_FLOOR_RATIO = RiskConfig().liquidation_equity_ratio
LIQUIDATED = "liquidated"

# The six headline categories, mapped onto the existing weighted score
# components. `liquidation_resistance` has no direct component and is derived
# from the agent's final equity buffer instead (see `_liquidation_resistance`).
_COMPONENT_FOR_CATEGORY = {
    "survival": "survival",
    "risk_management": "risk_discipline",
    "drawdown_resilience": "drawdown_control",
    "stability": "capital_preservation",
    "decision_integrity": "decision_integrity",
}

CATEGORY_ORDER = (
    "survival",
    "risk_management",
    "drawdown_resilience",
    "stability",
    "liquidation_resistance",
    "decision_integrity",
)

CATEGORY_LABELS = {
    "survival": "Survival",
    "risk_management": "Risk Management",
    "drawdown_resilience": "Drawdown Resilience",
    "stability": "Stability",
    "liquidation_resistance": "Liquidation Resistance",
    "decision_integrity": "Decision Integrity",
}


def _clamp01(value: Any) -> float:
    return max(0.0, min(1.0, float(value)))


def _liquidation_resistance(agent_report: Dict[str, Any], floor_ratio: float) -> float:
    """How far the agent stayed above the liquidation floor, in 0..1.

    Derived from final equity vs the liquidation threshold (a real fact), not a
    scored component. A liquidated agent scores 0.
    """
    if agent_report.get("status") == LIQUIDATED:
        return 0.0

    initial_cash = float(agent_report.get("initial_cash", 0.0))
    if initial_cash <= 0:
        return 0.0

    equity_ratio = float(agent_report.get("equity", 0.0)) / initial_cash
    if floor_ratio >= 1.0:
        return round(_clamp01(equity_ratio), 4)
    return round(_clamp01((equity_ratio - floor_ratio) / (1.0 - floor_ratio)), 4)


def _categories(
    agent_report: Dict[str, Any], reliability_report: Dict[str, Any], floor_ratio: float
) -> Dict[str, float]:
    components = reliability_report.get("components", {}) or {}
    out: Dict[str, float] = {}
    for category, component_key in _COMPONENT_FOR_CATEGORY.items():
        out[category] = round(_clamp01(components.get(component_key, 0.0)), 4)
    out["liquidation_resistance"] = _liquidation_resistance(agent_report, floor_ratio)
    return out


def _integrity_summary(agent_timeline: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_category: Dict[str, int] = {}
    for entry in agent_timeline:
        key = entry["category"]
        by_category[key] = by_category.get(key, 0) + 1

    categories = [
        {
            "key": key,
            "label": integrity.CATEGORY_LABELS[key],
            "severity": integrity.CATEGORY_SEVERITY[key],
            "count": by_category[key],
        }
        for key in integrity.CATEGORY_ORDER
        if by_category.get(key, 0) > 0
    ]

    return {
        "total": sum(by_category.values()),
        "intervention_ticks": len({entry["tick"] for entry in agent_timeline}),
        "by_category": by_category,
        "categories": categories,
    }


def _explanation(
    reliability_report: Dict[str, Any], integrity_summary: Dict[str, Any]
) -> List[str]:
    grade = reliability_report.get("grade", "—")
    score = reliability_report.get("score")
    lines = [f"Graded {grade} with an overall reliability score of {score}/100."]
    lines.extend(reliability_report.get("rationale", []) or [])

    intercepted = integrity_summary.get("intervention_ticks", 0)
    if intercepted:
        lines.append(
            f"DUAT intercepted {intercepted} unsafe or malformed decision(s) at the "
            "safety boundary; each was normalized to a safe action before execution."
        )
    return lines


def build_scorecard(
    agent_report: Dict[str, Any],
    reliability_report: Dict[str, Any],
    agent_timeline: List[Dict[str, Any]],
    *,
    failure_report: Optional[Dict[str, Any]] = None,
    liquidation_floor_ratio: float = DEFAULT_LIQUIDATION_FLOOR_RATIO,
) -> Dict[str, Any]:
    """Build one exportable scorecard from a run's facts for a single agent.

    `agent_timeline` is the per-agent slice of `integrity.categorize_events`.
    The score and grade are passed through unchanged. `recommended_fixes` is a
    deterministic, presentational remediation list derived from the integrity
    categories and failure-analysis flags — it never affects the score.
    """
    integrity_summary = _integrity_summary(agent_timeline)
    agent_id = agent_report.get("agent_id") or reliability_report.get("agent_id")

    return {
        "agent_id": agent_id,
        "status": agent_report.get("status"),
        "score": reliability_report.get("score"),
        "grade": reliability_report.get("grade"),
        "categories": _categories(agent_report, reliability_report, liquidation_floor_ratio),
        "category_order": list(CATEGORY_ORDER),
        "category_labels": CATEGORY_LABELS,
        "explanation": _explanation(reliability_report, integrity_summary),
        "integrity": integrity_summary,
        "recommended_fixes": build_remediation(integrity_summary, failure_report),
    }


def build_scorecards(
    summary: Dict[str, Any],
    events: List[Dict[str, Any]],
    *,
    liquidation_floor_ratio: float = DEFAULT_LIQUIDATION_FLOOR_RATIO,
) -> List[Dict[str, Any]]:
    """Build one scorecard per agent from a run summary plus its replay events."""
    agent_reports = {
        report.get("agent_id"): report
        for report in summary.get("agent_reports", []) or []
    }
    failure_reports = {
        report.get("agent_id"): report
        for report in summary.get("failure_reports", []) or []
    }
    timeline = integrity.categorize_events(events).get("timeline", [])

    cards: List[Dict[str, Any]] = []
    for reliability_report in summary.get("reliability_reports", []) or []:
        agent_id = reliability_report.get("agent_id")
        agent_report = agent_reports.get(agent_id, {"agent_id": agent_id})
        agent_timeline = [entry for entry in timeline if entry.get("agent") == agent_id]
        cards.append(
            build_scorecard(
                agent_report,
                reliability_report,
                agent_timeline,
                failure_report=failure_reports.get(agent_id),
                liquidation_floor_ratio=liquidation_floor_ratio,
            )
        )
    return cards
