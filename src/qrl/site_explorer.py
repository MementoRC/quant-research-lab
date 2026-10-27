"""The income explorer block: a lookup over the withdrawal-rules and
staged-entry reports for the dashboard's what-if panel.

Spec: docs/methodology/income-explorer.md. Pure: it takes the blocks that
`site_core.build_withdrawal_rules` and `build_staged_entry` return and
computes nothing new except the rule-minus-fixed differences.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_EVEN, Decimal

_PCT = re.compile(r"-?\d+(\.\d+)?%")


def difference(rule_cell: str, fixed_cell: str) -> str:
    """`rule - fixed` in signed percentage points, or "" unless both are single percentages."""
    if not (_PCT.fullmatch(rule_cell) and _PCT.fullmatch(fixed_cell)):
        return ""
    d = (Decimal(rule_cell[:-1]) - Decimal(fixed_cell[:-1])).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_EVEN
    )
    if d == 0:
        d = Decimal("0.0")  # drop the sign of a negative zero
    return f"{d:+.1f} pp"
