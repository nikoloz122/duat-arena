"""BYOA agent HTTP contract: payload shape and strict response validation.

Remote agents must expose ``POST /decide`` (or any URL ending in the decide path
the user registers). DUAT sends ``{ tick, market, portfolio }`` and expects a
decision JSON object. Test Connection uses strict validation; the simulation
engine still normalizes malformed runtime responses to a safe hold.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Tuple

ALLOWED_ACTIONS = frozenset({"buy", "sell", "hold", "reduce_exposure"})
SLOW_LATENCY_MS = 2000.0

# Sample context used by Test Connection (does not affect simulations).
SAMPLE_MARKET: Dict[str, float] = {
    "current_price": 100.0,
    "liquidity": 900.0,
    "volatility": 0.08,
    "market_sentiment": 0.05,
    "total_volume": 120.0,
}

SAMPLE_PORTFOLIO: Dict[str, Any] = {
    "cash": 1000.0,
    "position": 0.0,
    "equity": 1000.0,
    "exposure": 0.0,
    "status": "active",
}


def build_decide_payload(
    tick: int,
    market: Mapping[str, Any],
    portfolio: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Canonical request body for ``POST /decide``."""
    return {
        "tick": tick,
        "market": dict(market),
        "portfolio": dict(portfolio) if portfolio is not None else None,
    }


def sample_test_payload() -> Dict[str, Any]:
    return build_decide_payload(tick=0, market=SAMPLE_MARKET, portfolio=SAMPLE_PORTFOLIO)


def validate_decide_response(raw: Any) -> Tuple[bool, List[str]]:
    """Strict schema check for Test Connection. Returns (ok, error_messages)."""
    errors: List[str] = []

    if not isinstance(raw, dict):
        return False, [f"Response must be a JSON object, got {type(raw).__name__}"]

    action = raw.get("action")
    if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
        errors.append(
            f"'action' must be one of {sorted(ALLOWED_ACTIONS)}, got {action!r}"
        )

    confidence = raw.get("confidence")
    if confidence is None:
        errors.append("'confidence' is required")
    else:
        try:
            confidence_value = float(confidence)
            if math.isnan(confidence_value) or math.isinf(confidence_value):
                errors.append(f"'confidence' must be a finite number, got {confidence!r}")
            elif not 0.0 <= confidence_value <= 1.0:
                errors.append(f"'confidence' must be between 0 and 1, got {confidence_value}")
        except (TypeError, ValueError):
            errors.append(f"'confidence' must be a number, got {confidence!r}")

    size = raw.get("size")
    if size is None:
        errors.append("'size' is required")
    else:
        try:
            size_value = float(size)
            if math.isnan(size_value) or math.isinf(size_value):
                errors.append(f"'size' must be a finite number, got {size!r}")
            elif not 0.0 <= size_value <= 1.0:
                errors.append(f"'size' must be between 0 and 1, got {size_value}")
        except (TypeError, ValueError):
            errors.append(f"'size' must be a number, got {size!r}")

    reason = raw.get("reason")
    if reason is None:
        errors.append("'reason' is required")
    elif not isinstance(reason, str):
        errors.append(f"'reason' must be a string, got {type(reason).__name__}")

    return len(errors) == 0, errors


def classify_connection_status(
    *,
    success: bool,
    latency_ms: Optional[float],
) -> str:
    """Map a probe result to online / slow / offline badges."""
    if not success:
        return "offline"
    if latency_ms is not None and latency_ms >= SLOW_LATENCY_MS:
        return "slow"
    return "online"
