"""Categorize the real decision-boundary interceptions a run already records.

The simulation engine writes `normalization_notes` on every replay entry where
the `DecisionNormalizer` (or the engine's exception guard) had to correct unsafe
or malformed agent output. This module groups those notes into stable, named
categories so the dashboard can show *how* DUAT intervened.

It never fabricates events: every category here is derived from a note the
system actually produced. It is pure and deterministic — the same replay events
always yield the same categorization.
"""

from typing import Any, Dict, List

# Stable category keys (safe to serialize / key UI off of).
MALFORMED_OUTPUT = "malformed_output"
INVALID_ACTION = "invalid_action"
NON_FINITE_VALUE = "non_finite_value"
OVERSIZED_POSITION = "oversized_position"
MISSING_FIELD = "missing_field"
TIMEOUT_FALLBACK = "timeout_fallback"
OTHER_NORMALIZATION = "other_normalization"

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"

CATEGORY_LABELS = {
    MALFORMED_OUTPUT: "Malformed / unsupported output",
    INVALID_ACTION: "Invalid action rejected",
    NON_FINITE_VALUE: "Non-finite (NaN/inf) value prevented",
    OVERSIZED_POSITION: "Oversized position clamped",
    MISSING_FIELD: "Missing field defaulted",
    TIMEOUT_FALLBACK: "Timeout / no-decision fallback",
    OTHER_NORMALIZATION: "Other normalization",
}

CATEGORY_SEVERITY = {
    MALFORMED_OUTPUT: SEVERITY_HIGH,
    INVALID_ACTION: SEVERITY_HIGH,
    NON_FINITE_VALUE: SEVERITY_HIGH,
    TIMEOUT_FALLBACK: SEVERITY_HIGH,
    OVERSIZED_POSITION: SEVERITY_MEDIUM,
    MISSING_FIELD: SEVERITY_MEDIUM,
    OTHER_NORMALIZATION: SEVERITY_MEDIUM,
}

# Display order: high-severity, most alarming buckets first.
CATEGORY_ORDER = (
    MALFORMED_OUTPUT,
    INVALID_ACTION,
    NON_FINITE_VALUE,
    TIMEOUT_FALLBACK,
    OVERSIZED_POSITION,
    MISSING_FIELD,
    OTHER_NORMALIZATION,
)


def categorize_note(note: str) -> str:
    """Map a single normalization note string to a stable category key.

    Matching is keyed off the phrases the normalizer/engine actually emit. The
    catch-all keeps any unrecognized real note visible rather than dropped.
    """
    text = (note or "").lower()

    # No decision at all (agent returned None) or a recovered decide() crash.
    if "no decision" in text or "raised" in text:
        return TIMEOUT_FALLBACK
    if "unsupported type" in text or "not a mapping" in text or "not a string" in text:
        return MALFORMED_OUTPUT
    if "not allowed" in text:
        return INVALID_ACTION
    if "not finite" in text:
        return NON_FINITE_VALUE
    if "exceeds max" in text:
        return OVERSIZED_POSITION
    if "not numeric" in text:
        return MALFORMED_OUTPUT
    if "missing" in text:
        return MISSING_FIELD
    return OTHER_NORMALIZATION


def categorize_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize all decision-boundary interceptions across replay events.

    Returns counts per category, a per-(agent, tick) intervention count, and a
    flat per-tick timeline. `intervention_ticks` counts distinct intercepted
    decisions (one per agent-tick), matching the engine's integrity-event count;
    `total` counts individual reasons (a single decision can trip several).
    """
    timeline: List[Dict[str, Any]] = []
    by_category: Dict[str, int] = {key: 0 for key in CATEGORY_ORDER}
    by_agent: Dict[str, int] = {}
    intervened_decisions = set()
    total = 0

    for event in events or []:
        notes = event.get("normalization_notes") or []
        if not notes:
            continue
        tick = event.get("tick")
        agent = event.get("agent")
        intervened_decisions.add((agent, tick))
        for note in notes:
            category = categorize_note(note)
            by_category[category] += 1
            by_agent[agent] = by_agent.get(agent, 0) + 1
            total += 1
            timeline.append(
                {
                    "tick": tick,
                    "agent": agent,
                    "category": category,
                    "label": CATEGORY_LABELS[category],
                    "severity": CATEGORY_SEVERITY[category],
                    "note": note,
                }
            )

    categories = [
        {
            "key": key,
            "label": CATEGORY_LABELS[key],
            "severity": CATEGORY_SEVERITY[key],
            "count": by_category[key],
        }
        for key in CATEGORY_ORDER
        if by_category[key] > 0
    ]

    return {
        "total": total,
        "intervention_ticks": len(intervened_decisions),
        "by_category": by_category,
        "by_agent": by_agent,
        "categories": categories,
        "timeline": timeline,
    }
