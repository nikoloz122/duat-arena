"""Fuzz the decision boundary: malformed agent output must never break it.

The `DecisionNormalizer` is the contract that lets DUAT run untrusted/LLM
agents safely. These tests throw deterministic, seeded garbage at it and assert
it always returns a canonical, finite, in-bounds decision and never raises.
"""

import math
import random

import pytest

from agents.base import AgentDecision
from simulation.decision_normalizer import (
    ALLOWED_ACTIONS,
    MAX_CONFIDENCE,
    MAX_SIZE,
    MIN_CONFIDENCE,
    normalize_decision,
)

FUZZ_ITERATIONS = 2000

_WEIRD_ACTIONS = [None, "buy", "sell", "hold", "reduce_exposure", "moon", "", 123, ["buy"], {"a": 1}, float("nan"), True]
_WEIRD_SIZES = [None, float("nan"), float("inf"), float("-inf"), -10, 0, 5, 99999.0, "big", [1], {"n": 2}, True]
_WEIRD_CONFIDENCES = [None, float("nan"), float("inf"), float("-inf"), -2, 0.5, 5, "x", [0.1], {"c": 1}]
_WEIRD_REASONS = [None, "ok", 123, ["nested"], {"deep": {"deeper": [float("nan")]}}]
_WEIRD_METADATA = [None, {"k": "v"}, [1, 2, 3], "notadict", {"nested": {"x": [1, {"y": float("inf")}]}}]


def _random_raw(rng: random.Random):
    """Produce one adversarial agent 'decision' of a randomly chosen shape."""
    kind = rng.choice(["none", "scalar", "list", "object", "dict", "decision"])

    if kind == "none":
        return None
    if kind == "scalar":
        return rng.choice([float("nan"), float("inf"), float("-inf"), 42, -1, "buy", "garbage", True])
    if kind == "list":
        return [rng.choice([1, "x", None, float("nan")]) for _ in range(rng.randint(0, 4))]
    if kind == "object":
        return object()

    fields = {}
    if rng.random() < 0.85:
        fields["action"] = rng.choice(_WEIRD_ACTIONS)
    if rng.random() < 0.85:
        fields["size"] = rng.choice(_WEIRD_SIZES)
    if rng.random() < 0.85:
        fields["confidence"] = rng.choice(_WEIRD_CONFIDENCES)
    if rng.random() < 0.5:
        fields["reason"] = rng.choice(_WEIRD_REASONS)
    if rng.random() < 0.5:
        fields["metadata"] = rng.choice(_WEIRD_METADATA)

    if kind == "decision":
        # The dataclass does not validate, so it can carry junk just like a
        # real agent's buggy return value would.
        return AgentDecision(
            action=fields.get("action", "hold"),
            size=fields.get("size", 1.0),
            reason=fields.get("reason", ""),
            confidence=fields.get("confidence", 0.5),
            metadata=fields.get("metadata"),
        )
    return fields


def _assert_safe(result) -> None:
    decision = result.decision
    assert isinstance(decision, AgentDecision)
    assert decision.action in ALLOWED_ACTIONS

    assert isinstance(decision.size, float)
    assert math.isfinite(decision.size)
    assert 0.0 <= decision.size <= MAX_SIZE

    assert isinstance(decision.confidence, float)
    assert math.isfinite(decision.confidence)
    assert MIN_CONFIDENCE <= decision.confidence <= MAX_CONFIDENCE

    assert isinstance(decision.reason, str)
    assert isinstance(decision.metadata, dict)
    assert isinstance(result.notes, list)


def test_fuzz_normalizer_never_breaks_invariants():
    """Seeded fuzzing: every adversarial input yields a safe canonical decision."""
    rng = random.Random(1337)
    for _ in range(FUZZ_ITERATIONS):
        raw = _random_raw(rng)
        # If this raised, the test would fail here — that is the contract.
        result = normalize_decision(raw)
        _assert_safe(result)


def test_fuzz_normalizer_is_deterministic_per_seed():
    """Same seed -> same sequence of normalized decisions (replay-safe)."""

    def run():
        rng = random.Random(7)
        return [
            (r.decision.action, r.decision.size, r.decision.confidence, tuple(r.notes))
            for r in (normalize_decision(_random_raw(rng)) for _ in range(200))
        ]

    assert run() == run()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        ["not", "a", "decision"],
        object(),
        {"action": "moon", "size": 5, "confidence": 0.5},
        {"action": "buy", "size": float("nan")},
        {"action": "buy", "size": float("inf")},
        {"action": "buy", "size": 99999.0},
        {"action": "buy", "confidence": 5.0},
        {"action": "buy"},  # missing size/confidence
        {"action": "buy", "metadata": "notadict"},
    ],
)
def test_normalizer_records_notes_on_bad_input(raw):
    """Any correction the normalizer applies is recorded in notes."""
    result = normalize_decision(raw)
    _assert_safe(result)
    assert result.notes, f"expected notes for bad input: {raw!r}"


def test_normalizer_is_noop_on_valid_decision():
    """A valid decision passes through unchanged with no notes (determinism)."""
    valid = AgentDecision(action="buy", size=2.0, reason="ok", confidence=0.7, metadata={"k": "v"})
    result = normalize_decision(valid)
    assert result.notes == []
    assert result.decision.action == "buy"
    assert result.decision.size == 2.0
    assert result.decision.confidence == 0.7
    assert result.decision.reason == "ok"
    assert result.decision.metadata == {"k": "v"}
