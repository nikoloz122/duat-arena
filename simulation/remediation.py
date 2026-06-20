"""Deterministic, developer-oriented remediation guidance.

This is a pure presentation layer over facts a run already produced: the
categorized decision-boundary interceptions (`simulation.integrity`) and the
rule-based failure analysis (`simulation.failure_analysis`). For each detected
issue it emits a structured row — issue, suggested fix, and a fact-derived
reason.

It is deterministic and replay-safe: it computes no scores, generates no text
with an LLM, repairs nothing, and modifies no agent. The same inputs always
yield the same guidance.
"""

from typing import Any, Dict, List, Optional

from simulation import integrity

# Per integrity category: a short developer-facing issue title and the concrete
# fix to apply in the agent's own code. Keyed off the stable category keys in
# `simulation.integrity`.
INTEGRITY_GUIDANCE: Dict[str, Dict[str, str]] = {
    integrity.OVERSIZED_POSITION: {
        "issue": "Oversized Position",
        "suggested_fix": "Clamp position size to the configured risk envelope before execution.",
    },
    integrity.MALFORMED_OUTPUT: {
        "issue": "Malformed Output",
        "suggested_fix": "Enforce structured JSON output that matches the decision schema.",
    },
    integrity.INVALID_ACTION: {
        "issue": "Invalid Action",
        "suggested_fix": "Restrict outputs to the supported action set (buy, sell, hold, reduce_exposure).",
    },
    integrity.NON_FINITE_VALUE: {
        "issue": "Non-Finite Value",
        "suggested_fix": "Reject NaN/inf and validate numeric fields before returning a decision.",
    },
    integrity.MISSING_FIELD: {
        "issue": "Missing Field",
        "suggested_fix": "Always populate required decision fields (action and size).",
    },
    integrity.TIMEOUT_FALLBACK: {
        "issue": "Timeout / No Decision",
        "suggested_fix": "Reduce latency or add fallback logic so a decision is always returned in time.",
    },
    integrity.OTHER_NORMALIZATION: {
        "issue": "Output Normalized",
        "suggested_fix": "Validate outputs against the decision schema before returning decisions.",
    },
}

# Fact-derived reason templates per integrity category. `{n}` is the real
# interception count for that category.
_INTEGRITY_REASON: Dict[str, str] = {
    integrity.OVERSIZED_POSITION: "Agent exceeded the configured risk envelope {n} time(s).",
    integrity.MALFORMED_OUTPUT: "Agent returned malformed or unsupported output {n} time(s).",
    integrity.INVALID_ACTION: "Agent requested an unsupported action {n} time(s).",
    integrity.NON_FINITE_VALUE: "Agent produced a non-finite (NaN/inf) value {n} time(s).",
    integrity.MISSING_FIELD: "Agent omitted a required field {n} time(s).",
    integrity.TIMEOUT_FALLBACK: "Agent failed to return a usable decision {n} time(s).",
    integrity.OTHER_NORMALIZATION: "Agent output required normalization {n} time(s).",
}

# Per failure-analysis risk flag: structured guidance reusing the deterministic
# flags `simulation.failure_analysis` already emits.
FAILURE_FLAG_GUIDANCE: Dict[str, Dict[str, str]] = {
    "liquidation_threshold_breach": {
        "issue": "Liquidation Breach",
        "suggested_fix": "Lower maximum exposure and add stop-loss logic before equity reaches the liquidation floor.",
        "reason": "Agent's equity fell below the configured liquidation threshold.",
    },
    "failure_threshold_breach": {
        "issue": "Drawdown Failure",
        "suggested_fix": "Add drawdown limits that de-risk before the failure threshold is hit.",
        "reason": "Drawdown exceeded the configured failure threshold.",
    },
    "high_drawdown": {
        "issue": "High Drawdown",
        "suggested_fix": "Improve drawdown control with tighter position sizing and earlier exits.",
        "reason": "Drawdown reached a high fraction of the failure threshold.",
    },
    "repeated_exposure_increase": {
        "issue": "Repeated Exposure Increase",
        "suggested_fix": "Cap consecutive position growth under stress.",
        "reason": "Agent repeatedly increased exposure during the run.",
    },
    "repeated_exposure_reduction": {
        "issue": "Repeated Exposure Reduction",
        "suggested_fix": "Smooth exposure changes to avoid thrashing reductions.",
        "reason": "Agent repeatedly reduced exposure during the run.",
    },
}


def build_remediation(
    integrity_summary: Optional[Dict[str, Any]] = None,
    failure_report: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Build structured remediation rows from a run's existing facts.

    `integrity_summary` is the per-agent integrity summary (with `by_category`);
    `failure_report` is the agent's `FailureAnalysisResult` dict. Both are
    optional. Returns an ordered, de-duplicated list of
    `{issue, suggested_fix, reason}`. Empty when there is nothing to fix.
    """
    rows: List[Dict[str, str]] = []

    by_category = (integrity_summary or {}).get("by_category", {}) or {}
    for key in integrity.CATEGORY_ORDER:
        count = int(by_category.get(key, 0) or 0)
        if count <= 0:
            continue
        guidance = INTEGRITY_GUIDANCE[key]
        rows.append(
            {
                "issue": guidance["issue"],
                "suggested_fix": guidance["suggested_fix"],
                "reason": _INTEGRITY_REASON[key].format(n=count),
            }
        )

    for flag in (failure_report or {}).get("risk_flags", []) or []:
        guidance = FAILURE_FLAG_GUIDANCE.get(flag)
        if guidance is None:
            continue
        rows.append(dict(guidance))

    return rows
