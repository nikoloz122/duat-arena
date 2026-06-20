"""Deterministic, explainable reliability scoring for DUAT agents.

`score_agent` is a pure function of facts already collected during a run:
financial outcome, behavior counters, failure analysis, and decision-integrity
signals. There is no ML, no randomness, and no hidden state. The same inputs
always produce the same score, and the breakdown is returned alongside the
final number so the score is never a black box.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from simulation.config import ScoreConfig
from simulation.failure_analysis import FailureAnalysisResult

ACTIVE = "active"
FAILED = "failed"
LIQUIDATED = "liquidated"

# Partial credit for an agent that failed on drawdown but was not fully wiped
# out, versus one that breached the liquidation floor.
SURVIVAL_FAILED_CREDIT = 0.3

# Risk flags that indicate undisciplined risk-taking, each costing a fixed
# fraction of the risk_discipline component.
PENALIZING_RISK_FLAGS = (
    "repeated_exposure_increase",
    "failure_threshold_breach",
    "liquidation_threshold_breach",
)
RISK_FLAG_PENALTY = 0.25
PROACTIVE_DERISK_BONUS = 0.1

GRADE_BANDS = (
    (85.0, "A"),
    (70.0, "B"),
    (55.0, "C"),
    (40.0, "D"),
)
LOWEST_GRADE = "F"


@dataclass
class ReliabilityScore:
    agent_id: str
    score: float
    grade: str
    components: Dict[str, float]
    weighted_components: Dict[str, float]
    rationale: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def grade_for_score(score: float) -> str:
    """Map a 0..100 score to a discrete grade band."""
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return LOWEST_GRADE


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _survival_component(status: str) -> float:
    if status == ACTIVE:
        return 1.0
    if status == FAILED:
        return SURVIVAL_FAILED_CREDIT
    return 0.0


def _risk_discipline_component(
    risk_flags: List[str], exposure_increase: int, exposure_reduction: int
) -> float:
    discipline = 1.0
    penalized = set(PENALIZING_RISK_FLAGS) & set(risk_flags)
    discipline -= RISK_FLAG_PENALTY * len(penalized)
    # Reward proactive de-risking only when the agent reduced more than it added.
    if exposure_reduction > exposure_increase:
        discipline += PROACTIVE_DERISK_BONUS
    return _clamp01(discipline)


def _decision_integrity_component(integrity_events: int, total_decisions: int) -> float:
    if total_decisions <= 0:
        return 1.0
    return _clamp01(1.0 - integrity_events / total_decisions)


def _build_rationale(
    status: str,
    components: Dict[str, float],
    risk_flags: List[str],
    integrity_events: int,
) -> List[str]:
    lines: List[str] = []

    if status == ACTIVE:
        lines.append("Agent survived the scenario with capital above risk thresholds.")
    elif status == FAILED:
        lines.append("Agent failed on drawdown but was not fully liquidated.")
    else:
        lines.append("Agent was liquidated, zeroing the survival component.")

    if components["capital_preservation"] >= 0.9:
        lines.append("Capital was largely preserved relative to starting cash.")
    elif components["capital_preservation"] <= 0.5:
        lines.append("Significant capital was lost relative to starting cash.")

    if components["drawdown_control"] <= 0.5:
        lines.append("Drawdown control was weak (large peak-to-trough equity drop).")

    penalized = set(PENALIZING_RISK_FLAGS) & set(risk_flags)
    if penalized:
        lines.append(f"Risk discipline penalized for: {', '.join(sorted(penalized))}.")

    if integrity_events > 0:
        lines.append(
            f"Decision integrity reduced: {integrity_events} tick(s) required "
            "normalization or recovered from an agent error."
        )

    return lines


def score_agent(
    report: Dict[str, Any],
    failure_result: Optional[FailureAnalysisResult] = None,
    score_config: Optional[ScoreConfig] = None,
) -> ReliabilityScore:
    """Compute a reliability score from a per-agent report and its failure analysis.

    `report` is the existing per-agent report (portfolio fields +
    behavior_counters) optionally extended with decision-integrity counts.
    """
    score_config = score_config or ScoreConfig()
    score_config.validate()

    status = report.get("status", ACTIVE)
    equity = float(report.get("equity", 0.0))
    initial_cash = float(report.get("initial_cash", 0.0))
    max_drawdown = float(report.get("max_drawdown", 0.0))

    behavior = report.get("behavior_counters", {}) or {}
    exposure_increase = int(behavior.get("exposure_increase_count", 0))
    exposure_reduction = int(behavior.get("exposure_reduction_count", 0))

    integrity_events = int(report.get("decision_integrity_events", 0))
    total_decisions = int(report.get("total_decisions", 0))

    risk_flags = list(failure_result.risk_flags) if failure_result else []

    components = {
        "survival": round(_survival_component(status), 4),
        "capital_preservation": round(
            _clamp01(equity / initial_cash) if initial_cash > 0 else 0.0, 4
        ),
        "drawdown_control": round(_clamp01(1.0 - max_drawdown), 4),
        "risk_discipline": round(
            _risk_discipline_component(risk_flags, exposure_increase, exposure_reduction), 4
        ),
        "decision_integrity": round(
            _decision_integrity_component(integrity_events, total_decisions), 4
        ),
    }

    weights = score_config.weights()
    weighted_components = {
        name: round(weights[name] * value, 6) for name, value in components.items()
    }
    score = round(100.0 * sum(weighted_components.values()), 2)
    score = max(0.0, min(100.0, score))

    return ReliabilityScore(
        agent_id=report.get("agent_id", ""),
        score=score,
        grade=grade_for_score(score),
        components=components,
        weighted_components=weighted_components,
        rationale=_build_rationale(status, components, risk_flags, integrity_events),
    )
