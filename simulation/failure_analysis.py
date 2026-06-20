from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from simulation.config import RiskConfig

# Objective thresholds for fact-based flags. These are deterministic constants,
# not subjective judgments.
REPEATED_ACTION_THRESHOLD = 3
HIGH_DRAWDOWN_FRACTION_OF_FAILURE = 0.5

ACTIVE = "active"
FAILED = "failed"
LIQUIDATED = "liquidated"


@dataclass
class FailureAnalysisResult:
    """Deterministic, rule-based explanation of an agent's outcome.

    Every field is derived from facts collected during the simulation. There is
    no scoring, no probability, and no subjective labeling.
    """

    agent_id: str
    status: str
    summary: str
    primary_failure_reason: str | None
    risk_flags: List[str] = field(default_factory=list)
    recommended_fix: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def analyze_agent(report: Dict[str, Any], risk: RiskConfig) -> FailureAnalysisResult:
    """Analyze a single agent report (portfolio fields + behavior_counters)."""
    agent_id = report.get("agent_id", "")
    status = report.get("status", ACTIVE)
    max_drawdown = float(report.get("max_drawdown", 0.0))
    equity = float(report.get("equity", 0.0))
    initial_cash = float(report.get("initial_cash", 0.0))

    behavior = report.get("behavior_counters", {}) or {}
    exposure_increase_count = int(behavior.get("exposure_increase_count", 0))
    exposure_reduction_count = int(behavior.get("exposure_reduction_count", 0))
    reduce_exposure_count = int(behavior.get("reduce_exposure_count", 0))

    risk_flags = _build_risk_flags(
        status=status,
        max_drawdown=max_drawdown,
        equity=equity,
        initial_cash=initial_cash,
        exposure_increase_count=exposure_increase_count,
        exposure_reduction_count=exposure_reduction_count,
        risk=risk,
    )
    summary, primary_failure_reason = _build_summary(status)
    recommended_fix = _build_recommendations(status, risk_flags, reduce_exposure_count)

    return FailureAnalysisResult(
        agent_id=agent_id,
        status=status,
        summary=summary,
        primary_failure_reason=primary_failure_reason,
        risk_flags=risk_flags,
        recommended_fix=recommended_fix,
    )


def _build_risk_flags(
    *,
    status: str,
    max_drawdown: float,
    equity: float,
    initial_cash: float,
    exposure_increase_count: int,
    exposure_reduction_count: int,
    risk: RiskConfig,
) -> List[str]:
    flags: List[str] = []

    liquidation_level = initial_cash * risk.liquidation_equity_ratio
    if status == LIQUIDATED or (initial_cash > 0 and equity <= liquidation_level):
        flags.append("liquidation_threshold_breach")

    if status == FAILED or max_drawdown >= risk.failure_drawdown_ratio:
        flags.append("failure_threshold_breach")

    if max_drawdown >= risk.failure_drawdown_ratio * HIGH_DRAWDOWN_FRACTION_OF_FAILURE:
        flags.append("high_drawdown")

    if exposure_increase_count >= REPEATED_ACTION_THRESHOLD:
        flags.append("repeated_exposure_increase")

    if exposure_reduction_count >= REPEATED_ACTION_THRESHOLD:
        flags.append("repeated_exposure_reduction")

    return list(dict.fromkeys(flags))


def _build_summary(status: str) -> tuple[str, str | None]:
    if status == LIQUIDATED:
        return (
            "Agent was liquidated after equity fell below the configured liquidation threshold.",
            "Equity fell below liquidation threshold.",
        )
    if status == FAILED:
        return (
            "Agent failed after drawdown exceeded the configured failure threshold.",
            "Drawdown exceeded configured threshold.",
        )
    return (
        "Agent maintained capital above configured risk thresholds.",
        None,
    )


def _build_recommendations(
    status: str, risk_flags: List[str], reduce_exposure_count: int
) -> List[str]:
    recommendations: List[str] = []

    if "liquidation_threshold_breach" in risk_flags:
        recommendations.append("Lower maximum exposure.")
    if "failure_threshold_breach" in risk_flags or "high_drawdown" in risk_flags:
        recommendations.append("Improve drawdown control.")
    if "repeated_exposure_increase" in risk_flags:
        recommendations.append("Limit position growth.")
    if status in (FAILED, LIQUIDATED) and reduce_exposure_count == 0:
        recommendations.append("Reduce exposure earlier.")

    return list(dict.fromkeys(recommendations))
