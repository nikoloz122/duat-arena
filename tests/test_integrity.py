"""Tests for the decision-boundary violation categorizer.

Deterministic and offline: synthetic replay events carry exactly the
normalization-note phrasing the engine/normalizer emit, so categorization is
exercised against real wording without running a simulation.
"""

from simulation import integrity


def test_categorize_note_maps_known_phrases():
    cases = {
        "agent returned no decision; defaulted to safe hold": integrity.TIMEOUT_FALLBACK,
        "agent.decide raised ValueError: boom; defaulted to safe hold": integrity.TIMEOUT_FALLBACK,
        "agent returned unsupported type list; defaulted to safe hold": integrity.MALFORMED_OUTPUT,
        "metadata [1] is not a mapping; dropped": integrity.MALFORMED_OUTPUT,
        "reason 5 is not a string; defaulted to empty string": integrity.MALFORMED_OUTPUT,
        "action 'yolo' is not allowed; coerced to 'hold'": integrity.INVALID_ACTION,
        "size nan is not finite; defaulted to 1.0": integrity.NON_FINITE_VALUE,
        "size 5000.0 exceeds max; clamped to 1000.0": integrity.OVERSIZED_POSITION,
        "size 'big' is not numeric; defaulted to 1.0": integrity.MALFORMED_OUTPUT,
        "size missing; defaulted to 1.0": integrity.MISSING_FIELD,
        "confidence 1.5 above 1.0; clamped": integrity.OTHER_NORMALIZATION,
    }
    for note, expected in cases.items():
        assert integrity.categorize_note(note) == expected, note


def test_categorize_note_handles_empty():
    assert integrity.categorize_note("") == integrity.OTHER_NORMALIZATION
    assert integrity.categorize_note(None) == integrity.OTHER_NORMALIZATION  # type: ignore[arg-type]


def test_categorize_events_counts_and_timeline():
    events = [
        {"tick": 0, "agent": "a", "normalization_notes": []},
        {
            "tick": 1,
            "agent": "a",
            "normalization_notes": [
                "action 'yolo' is not allowed; coerced to 'hold'",
                "size nan is not finite; defaulted to 1.0",
            ],
        },
        {
            "tick": 2,
            "agent": "b",
            "normalization_notes": ["agent returned no decision; defaulted to safe hold"],
        },
    ]

    result = integrity.categorize_events(events)

    # Two notes on tick 1 + one note on tick 2 = 3 reasons total.
    assert result["total"] == 3
    # Distinct intercepted decisions: (a,1) and (b,2) = 2.
    assert result["intervention_ticks"] == 2
    assert result["by_category"][integrity.INVALID_ACTION] == 1
    assert result["by_category"][integrity.NON_FINITE_VALUE] == 1
    assert result["by_category"][integrity.TIMEOUT_FALLBACK] == 1
    assert result["by_agent"] == {"a": 2, "b": 1}
    assert len(result["timeline"]) == 3
    # Categories list only includes present buckets, high-severity ordered first.
    present_keys = [c["key"] for c in result["categories"]]
    assert set(present_keys) == {
        integrity.INVALID_ACTION,
        integrity.NON_FINITE_VALUE,
        integrity.TIMEOUT_FALLBACK,
    }


def test_categorize_events_empty_is_zeroed():
    result = integrity.categorize_events([])
    assert result["total"] == 0
    assert result["intervention_ticks"] == 0
    assert result["categories"] == []
    assert result["timeline"] == []


def test_categorize_events_is_deterministic():
    events = [
        {"tick": 1, "agent": "a", "normalization_notes": ["size missing; defaulted to 1.0"]},
    ]
    assert integrity.categorize_events(events) == integrity.categorize_events(events)
