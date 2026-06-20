"""Safe execution boundary between agent decisions and the simulation.

`normalize_decision` takes whatever an agent returns and produces a canonical
`AgentDecision`. It is pure, deterministic, and never raises on bad input. For a
valid decision it is a no-op (no notes, identical values), so deterministic
preset behavior is preserved.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List

from agents.base import AgentDecision

ALLOWED_ACTIONS = ("buy", "sell", "hold", "reduce_exposure")
DEFAULT_ACTION = "hold"
DEFAULT_SIZE = 1.0
MAX_SIZE = 1000.0
DEFAULT_CONFIDENCE = 0.5
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0


@dataclass
class NormalizationResult:
    """Canonical decision plus a record of every change that was applied."""

    decision: AgentDecision
    notes: List[str] = field(default_factory=list)


def _get(raw: Any, key: str) -> Any:
    """Read a field from either an object (attribute) or a mapping (key)."""
    if isinstance(raw, dict):
        return raw.get(key)
    return getattr(raw, key, None)


def _normalize_action(raw_action: Any, notes: List[str]) -> str:
    if isinstance(raw_action, str) and raw_action in ALLOWED_ACTIONS:
        return raw_action
    notes.append(
        f"action {raw_action!r} is not allowed; coerced to {DEFAULT_ACTION!r}"
    )
    return DEFAULT_ACTION


def _normalize_size(raw_size: Any, notes: List[str]) -> float:
    if raw_size is None:
        notes.append(f"size missing; defaulted to {DEFAULT_SIZE}")
        return DEFAULT_SIZE

    try:
        size = float(raw_size)
    except (TypeError, ValueError):
        notes.append(f"size {raw_size!r} is not numeric; defaulted to {DEFAULT_SIZE}")
        return DEFAULT_SIZE

    if math.isnan(size) or math.isinf(size):
        notes.append(f"size {raw_size!r} is not finite; defaulted to {DEFAULT_SIZE}")
        return DEFAULT_SIZE

    if size < 0:
        notes.append(f"size {size} is negative; defaulted to {DEFAULT_SIZE}")
        return DEFAULT_SIZE

    if size == 0:
        notes.append(f"size is zero; defaulted to {DEFAULT_SIZE}")
        return DEFAULT_SIZE

    if size > MAX_SIZE:
        notes.append(f"size {size} exceeds max; clamped to {MAX_SIZE}")
        return MAX_SIZE

    return size


def _normalize_confidence(raw_confidence: Any, notes: List[str]) -> float:
    if raw_confidence is None:
        notes.append(f"confidence missing; defaulted to {DEFAULT_CONFIDENCE}")
        return DEFAULT_CONFIDENCE

    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        notes.append(
            f"confidence {raw_confidence!r} is not numeric; defaulted to {DEFAULT_CONFIDENCE}"
        )
        return DEFAULT_CONFIDENCE

    if math.isnan(confidence) or math.isinf(confidence):
        notes.append(
            f"confidence {raw_confidence!r} is not finite; defaulted to {DEFAULT_CONFIDENCE}"
        )
        return DEFAULT_CONFIDENCE

    if confidence < MIN_CONFIDENCE:
        notes.append(f"confidence {confidence} below {MIN_CONFIDENCE}; clamped")
        return MIN_CONFIDENCE

    if confidence > MAX_CONFIDENCE:
        notes.append(f"confidence {confidence} above {MAX_CONFIDENCE}; clamped")
        return MAX_CONFIDENCE

    return confidence


def _normalize_reason(raw_reason: Any, notes: List[str]) -> str:
    if raw_reason is None:
        notes.append("reason missing; defaulted to empty string")
        return ""
    if not isinstance(raw_reason, str):
        notes.append(f"reason {raw_reason!r} is not a string; defaulted to empty string")
        return ""
    return raw_reason


def _normalize_metadata(raw_metadata: Any, notes: List[str]) -> Dict[str, Any]:
    if raw_metadata is None:
        return {}
    if not isinstance(raw_metadata, dict):
        notes.append(f"metadata {raw_metadata!r} is not a mapping; dropped")
        return {}
    return raw_metadata


def normalize_decision(raw: Any) -> NormalizationResult:
    """Return a canonical AgentDecision and the notes describing any changes."""
    notes: List[str] = []

    if raw is None:
        notes.append("agent returned no decision; defaulted to safe hold")
        return NormalizationResult(
            decision=AgentDecision(
                action=DEFAULT_ACTION,
                size=DEFAULT_SIZE,
                reason="",
                confidence=DEFAULT_CONFIDENCE,
                metadata={},
            ),
            notes=notes,
        )

    if not isinstance(raw, (AgentDecision, dict)):
        notes.append(
            f"agent returned unsupported type {type(raw).__name__}; defaulted to safe hold"
        )
        return NormalizationResult(
            decision=AgentDecision(
                action=DEFAULT_ACTION,
                size=DEFAULT_SIZE,
                reason="",
                confidence=DEFAULT_CONFIDENCE,
                metadata={},
            ),
            notes=notes,
        )

    decision = AgentDecision(
        action=_normalize_action(_get(raw, "action"), notes),
        size=_normalize_size(_get(raw, "size"), notes),
        reason=_normalize_reason(_get(raw, "reason"), notes),
        confidence=_normalize_confidence(_get(raw, "confidence"), notes),
        metadata=_normalize_metadata(_get(raw, "metadata"), notes),
    )
    return NormalizationResult(decision=decision, notes=notes)
