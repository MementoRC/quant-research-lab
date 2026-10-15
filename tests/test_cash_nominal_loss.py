"""True-cash deflation disclosure (spec: docs/methodology/report-wording.md,
"5. True-cash disclosure"): the helper and the sentence in both reports."""

from __future__ import annotations

import pandas as pd
import pytest
from test_decision_report import _hand_report
from test_true_cash import (  # noqa: F401
    CA,
    NAMES_22,
    TCASH_KEYS,
    _longrun_hand,
    _sleeve_report,
    treport,
    tsmall,
)
from test_true_cash_all_cores import _report, _rows_of

from qrl.decision_report import _header
from qrl.longrun_report import render_markdown as render_longrun
from qrl.true_cash import nominal_loss_stats

STATS = {"n": 3, "N": 168, "worst": 0.0298, "start": "2009-02", "end": "2009-03"}
SENTENCE = (
    "It follows unadjusted CPI, so it loses money in deflation months: 3 of 168 months "
    "here, worst 3.0% from 2009-02 to 2009-03. A 0% floor would make true cash look "
    "better in the crash windows."
)
ZERO = {"n": 0, "N": 168, "worst": 0.0, "start": None, "end": None}
ZERO_SENTENCE = (
    "It follows unadjusted CPI, so it would lose money in a deflation month: 0 of 168 months here."
)


def _months(values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.period_range("2020-01", periods=len(values), freq="M"))


def test_three_negative_months_give_the_worst_consecutive_run():
    got = nominal_loss_stats(_months([0.01, -0.01, -0.02, 0.005, -0.001]))
    assert got["n"] == 3
    assert got["N"] == 5
    assert got["worst"] == pytest.approx(1 - 0.99 * 0.98)
    assert (got["start"], got["end"]) == ("2020-02", "2020-03")


def test_worst_is_the_peak_to_trough_drawdown_not_a_consecutive_run():
    got = nominal_loss_stats(_months([0.01, -0.02, -0.01, 0.001, -0.015, 0.03]))
    assert got["n"] == 3
    assert got["worst"] == pytest.approx(1 - 0.98 * 0.99 * 1.001 * 0.985)
    assert got["worst"] > 1 - 0.98 * 0.99  # the longest consecutive run is smaller
    assert (got["start"], got["end"]) == ("2020-02", "2020-05")


def test_no_negative_month_gives_zero_and_no_dates():
    got = nominal_loss_stats(_months([0.0, 0.01, 0.002]))
    assert got == {"n": 0, "N": 3, "worst": 0.0, "start": None, "end": None}


def test_daily_returns_are_compounded_to_calendar_months():
    days = pd.bdate_range("2020-01-01", "2020-03-31")
    month = days.to_period("M")
    daily = pd.Series(0.0, index=days)
    daily[month == pd.Period("2020-02")] = (0.98) ** (1 / (month == pd.Period("2020-02")).sum()) - 1
    got = nominal_loss_stats(daily)
    assert got["n"] == 1
    assert got["N"] == 3
    assert got["worst"] == pytest.approx(0.02)
    assert (got["start"], got["end"]) == ("2020-02", "2020-02")


def test_decision_single_bullet_carries_the_sentence_after_the_description():
    lines = _header(_sleeve_report(cash_assumption=CA, cash_nominal_loss=STATS))
    (bullet,) = [ln for ln in lines if ln.startswith("- A80-TCASH20 (")]
    assert bullet.endswith(f"free in both rows. {SENTENCE}")
    assert "\n".join(lines).count(SENTENCE) == 1


def test_decision_multi_bullet_carries_the_sentence_once():
    text = "\n".join(_header(_report(_rows_of("A", "G"), None) | {"cash_nominal_loss": STATS}))
    assert text.count(SENTENCE) == 1
    assert f"free in both rows. {SENTENCE}" in text


def test_decision_zero_months_uses_the_would_lose_wording():
    text = "\n".join(_header(_sleeve_report(cash_assumption=CA, cash_nominal_loss=ZERO)))
    assert ZERO_SENTENCE in text
    assert "worst" not in ZERO_SENTENCE
    assert "0% floor" not in text


def test_decision_without_stats_or_row_is_unchanged():
    assert _header(_sleeve_report(cash_assumption=CA, cash_nominal_loss=None)) == _header(
        _sleeve_report(cash_assumption=CA)
    )
    plain = _hand_report()
    assert _header(plain | {"cash_nominal_loss": STATS}) == _header(plain)


def test_longrun_single_note_carries_the_sentence_once():
    rep = _longrun_hand([*NAMES_22, "A80-TCASH20"], cash_nominal_loss=STATS, **TCASH_KEYS)
    text = render_longrun(rep)
    assert text.count(SENTENCE) == 1
    line = next(ln for ln in text.splitlines() if ln.startswith("- A80-TCASH20:"))
    assert line.endswith(f"free in both rows. {SENTENCE}")


def test_longrun_without_an_assumption_row_puts_it_on_the_cash_line():
    text = render_longrun(_longrun_hand(NAMES_22, cash_nominal_loss=STATS))
    line = next(ln for ln in text.splitlines() if ln.startswith("- CASH +1% real (assumption):"))
    assert line.endswith(f"a year. {SENTENCE}")
    assert text.count(SENTENCE) == 1


def test_longrun_multi_note_carries_the_sentence_once():
    rows = _rows_of("A", "G")
    names = ["A", "A80-CASH20", "A80-IEF20", "IEF", "CASH", *[r["id"] for r in rows]]
    keys = {
        "cash_assumptions": [
            {"id": r["id"], "base": r["base"], "share": 0.2, "pair": r["pair"]} for r in rows
        ],
        "cash_assumption_id": None,
    }
    text = render_longrun(_longrun_hand(names, cash_nominal_loss=STATS, **keys))
    assert text.count(SENTENCE) == 1


def test_longrun_without_stats_is_unchanged():
    plain = render_longrun(_longrun_hand(NAMES_22))
    assert render_longrun(_longrun_hand(NAMES_22, cash_nominal_loss=None)) == plain
    assert "unadjusted CPI" not in plain


def test_run_decision_stats_come_from_the_cash_leg_used(treport):  # noqa: F811
    s = treport["cash_nominal_loss"]
    assert s["N"] == 168
    assert set(s) == {"n", "N", "worst", "start", "end"}


def test_run_longrun_stats_come_from_the_monthly_cash_leg(tsmall):  # noqa: F811
    from test_true_cash import _lcfg, criteria, prices, uneven_cpi

    from qrl.longrun import run_longrun

    report = run_longrun(_lcfg(), tsmall, prices(), uneven_cpi(), criteria())
    assert report["cash_nominal_loss"]["N"] == 168
    assert report["cash_nominal_loss"]["n"] == 0  # the synthetic CPI only rises
