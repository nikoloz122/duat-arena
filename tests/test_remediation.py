"""Tests for deterministic remediation guidance.

Pure and offline. Asserts the issue/fix/reason rows are derived only from the
existing integrity categories and failure-analysis flags, are deterministically
ordered, and never fabricate guidance.
"""

import unittest

from simulation import integrity
from simulation.remediation import (
    FAILURE_FLAG_GUIDANCE,
    INTEGRITY_GUIDANCE,
    build_remediation,
)


class BuildRemediationTests(unittest.TestCase):
    def test_empty_inputs_yield_no_rows(self) -> None:
        self.assertEqual(build_remediation(), [])
        self.assertEqual(build_remediation({}, {}), [])

    def test_zero_count_is_skipped(self) -> None:
        rows = build_remediation({"by_category": {integrity.OVERSIZED_POSITION: 0}})
        self.assertEqual(rows, [])

    def test_oversized_position_reason_includes_real_count(self) -> None:
        rows = build_remediation({"by_category": {integrity.OVERSIZED_POSITION: 7}})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["issue"], "Oversized Position")
        self.assertIn("Clamp position size", row["suggested_fix"])
        self.assertIn("7 time(s)", row["reason"])

    def test_integrity_rows_follow_category_order(self) -> None:
        rows = build_remediation(
            {
                "by_category": {
                    integrity.TIMEOUT_FALLBACK: 3,
                    integrity.MALFORMED_OUTPUT: 2,
                    integrity.INVALID_ACTION: 1,
                }
            }
        )
        issues = [r["issue"] for r in rows]
        # integrity.CATEGORY_ORDER: malformed -> invalid -> timeout.
        self.assertEqual(
            issues, ["Malformed Output", "Invalid Action", "Timeout / No Decision"]
        )

    def test_every_integrity_category_has_guidance(self) -> None:
        for key in integrity.CATEGORY_ORDER:
            self.assertIn(key, INTEGRITY_GUIDANCE)
            rows = build_remediation({"by_category": {key: 1}})
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["issue"])
            self.assertTrue(rows[0]["suggested_fix"])
            self.assertIn("1 time(s)", rows[0]["reason"])

    def test_failure_flags_appended_with_structured_guidance(self) -> None:
        failure = {"risk_flags": ["liquidation_threshold_breach", "high_drawdown"]}
        rows = build_remediation({}, failure)
        issues = [r["issue"] for r in rows]
        self.assertEqual(issues, ["Liquidation Breach", "High Drawdown"])
        self.assertTrue(all(r["reason"] and r["suggested_fix"] for r in rows))

    def test_unknown_failure_flag_is_ignored(self) -> None:
        rows = build_remediation({}, {"risk_flags": ["something_unmapped"]})
        self.assertEqual(rows, [])

    def test_integrity_then_failure_combined_order(self) -> None:
        rows = build_remediation(
            {"by_category": {integrity.OVERSIZED_POSITION: 1}},
            {"risk_flags": ["liquidation_threshold_breach"]},
        )
        self.assertEqual(
            [r["issue"] for r in rows], ["Oversized Position", "Liquidation Breach"]
        )

    def test_every_known_failure_flag_has_complete_guidance(self) -> None:
        for flag, guidance in FAILURE_FLAG_GUIDANCE.items():
            self.assertTrue(guidance["issue"])
            self.assertTrue(guidance["suggested_fix"])
            self.assertTrue(guidance["reason"])

    def test_is_deterministic(self) -> None:
        summary = {"by_category": {integrity.MALFORMED_OUTPUT: 2}}
        failure = {"risk_flags": ["high_drawdown"]}
        self.assertEqual(
            build_remediation(summary, failure), build_remediation(summary, failure)
        )


if __name__ == "__main__":
    unittest.main()
