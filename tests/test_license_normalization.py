"""Tests for the license-number normalization fallback in app.database.

The fallback recovers leading-zero license numbers (e.g. "0552794" -> "552794")
without coercing non-CSLB identifiers into false-positive matches
(e.g. "0D808818" must NOT match the unrelated real license "808818").
"""

import pytest

from app.database import _normalize_license


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0552794", "552794"),      # true recovery (CoverPro)
        ("00552794", "552794"),     # multiple leading zeros
        ("  0552794 ", "552794"),   # surrounding whitespace + leading zero
        ("012", "12"),              # short numeric with leading zero
        ("0D808818", None),         # interior letter -> no fallback (false-positive guard)
        ("604558063", None),        # 9 digits -> exceeds 7
        ("14-5189", None),          # dash -> non-numeric
        ("17-6025", None),          # dash -> non-numeric
        ("OPR 11115", None),        # prefix + space -> non-numeric
        ("PR 7596", None),          # prefix -> non-numeric
        ("1105295", None),          # already clean -> no-op (no leading zero)
        ("1234567", None),          # clean 7-digit -> no-op
        ("0000000", None),          # all zeros -> empty after strip -> rejected
        ("0", None),                # single zero -> empty -> rejected
        ("", None),                 # empty -> rejected
    ],
)
def test_normalize_license(raw, expected):
    assert _normalize_license(raw) == expected
