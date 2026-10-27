"""Tests for the income explorer block (docs/methodology/income-explorer.md)."""

from __future__ import annotations

import pytest

from qrl.site_explorer import difference


@pytest.mark.parametrize(
    ("rule", "fixed", "expected"),
    [
        ("155.3%", "148.5%", "+6.8 pp"),
        ("1247.9%", "1400.0%", "-152.1 pp"),
        ("1557.3%", "1400.0%", "+157.3 pp"),
        ("0.0%", "0.7%", "-0.7 pp"),
        ("299.8%", "299.8%", "+0.0 pp"),
        ("1.2%", "1.24%", "+0.0 pp"),  # -0.04 rounds to zero: never "-0.0"
        ("-1.5%", "2%", "-3.5 pp"),
        ("0.0%", "-", ""),
        ("-", "-", ""),
        ("2014", "2013", ""),
        ("-3.3 (-10.1, +8.8)", "1.0%", ""),
        ("1.0% ", "1.0%", ""),  # must fully match
    ],
)
def test_difference(rule, fixed, expected):
    assert difference(rule, fixed) == expected
