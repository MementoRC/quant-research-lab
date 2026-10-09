"""run_longrun end to end on the offline decision-helper fixtures: row layout,
repeatability, pairing, report header, and sealing (nothing after 2018-12-31
is read)."""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from decision_helpers import END, GOOD, ROOT, cpi, criteria, load, prices, write

from qrl.longrun import CASH_ASSUMPTION, LongrunConfig, block_starts, run_longrun

RATES = [0.04, 0.05]


def _lcfg() -> LongrunConfig:
    return LongrunConfig(
        seed=7,
        n_paths=50,
        block_months=12,
        horizon_years=30,
        real_floor=0.5,
        rates=RATES,
        cash_real_yield=0.01,
        sha256="ab" * 32,
    )


def _run(dcfg, data=None, index=None) -> dict:
    return run_longrun(
        _lcfg(),
        dcfg,
        prices() if data is None else data,
        cpi() if index is None else index,
        criteria(),
    )


def _by_portfolio(report: dict, rate: float) -> dict[str, dict]:
    return {r["portfolio"]: r for r in report["rows"] if r["rate"] == rate}


def test_run_longrun_one_row_per_rate_and_portfolio_cash_assumption_after_cash(tmp_path):
    dcfg = load(tmp_path)
    report = _run(dcfg)
    ids = [p.id for p in dcfg.portfolios]
    expected = []
    for pid in ids:
        expected.append(pid)
        if pid == "CASH":
            expected.append(CASH_ASSUMPTION)
    assert "CASH" in ids
    assert [r["portfolio"] for r in report["rows"]] == expected * len(RATES)
    assert [r["rate"] for r in report["rows"]] == [x for x in RATES for _ in expected]


def test_run_longrun_is_repeatable(tmp_path):
    dcfg = load(tmp_path)
    assert _run(dcfg) == _run(dcfg)


def test_run_longrun_report_header_carries_the_run_settings(tmp_path):
    dcfg = load(tmp_path)
    report = _run(dcfg)
    assert report["seed"] == 7
    assert report["n_paths"] == 50
    assert report["block_months"] == 12
    assert report["horizon_years"] == 30
    assert report["longrun_sha256"] == "ab" * 32
    assert report["decision_sha256"] == dcfg.sha256
    assert report["data_end"] == "2018-12-31"
    months = pd.period_range(report["first_month"], report["last_month"], freq="M")
    assert report["n_months"] == len(months) == 168


def test_run_longrun_is_paired_identical_holdings_give_identical_rows(tmp_path):
    full = load(tmp_path)
    by_id = {p.id: p for p in full.portfolios}
    twin = replace(by_id["G-EW"], id="G-EW-TWIN")
    dcfg = replace(full, portfolios=[by_id["G-EW"], twin, by_id["CASH"]])
    report = _run(dcfg)
    for rate in RATES:
        rows = _by_portfolio(report, rate)
        a = {k: v for k, v in rows["G-EW"].items() if k != "portfolio"}
        b = {k: v for k, v in rows["G-EW-TWIN"].items() if k != "portfolio"}
        c = {k: v for k, v in rows["CASH"].items() if k != "portfolio"}
        assert a == b
        assert a != c  # different holdings give different rows: the check is not vacuous


def test_run_longrun_draws_block_starts_once_for_all_portfolios(tmp_path):
    dcfg = load(tmp_path)
    assert len(dcfg.portfolios) > 1
    with patch("qrl.longrun.block_starts", wraps=block_starts) as spy:
        _run(dcfg)
    assert spy.call_count == 1


def test_run_longrun_refuses_partial_months(tmp_path):
    dcfg = load(tmp_path)
    data = prices()
    short = {k: v.loc[: END - pd.offsets.MonthEnd(1)] for k, v in data.items()}
    with pytest.raises(ValueError, match="months must run"):
        _run(dcfg, short)


def test_run_longrun_refuses_paths_not_horizon_years_times_twelve_months_long(tmp_path):
    dcfg = load(tmp_path)
    lcfg = replace(_lcfg(), block_months=7)  # 360 // 7 blocks of 7 = 357 months
    with pytest.raises(ValueError, match="357 months"):
        run_longrun(lcfg, dcfg, prices(), cpi(), criteria())


def _scaled(frame, mask, rng):
    factors = np.where(mask[:, None], rng.uniform(0.2, 5.0, frame.shape), 1.0)
    return frame * factors


def test_run_longrun_ignores_data_after_2018(tmp_path):
    dcfg = load(tmp_path)
    data, index = prices(), cpi()
    rng = np.random.default_rng(3)
    after = np.asarray(data["close"].index > END)
    poisoned = {k: _scaled(v, after, rng) for k, v in data.items()}
    poisoned_cpi = index * np.where(
        np.asarray(index.index > END), rng.uniform(0.2, 5.0, len(index)), 1.0
    )
    assert not poisoned["close"].equals(data["close"])
    assert not poisoned_cpi.equals(index)
    assert _run(dcfg, data, index) == _run(dcfg, poisoned, poisoned_cpi)


def test_run_longrun_detects_data_on_or_before_2018(tmp_path):
    dcfg = load(tmp_path)
    data, index = prices(), cpi()
    base = _run(dcfg, data, index)
    altered = {k: v.copy() for k, v in data.items()}
    altered["close"].loc[END, :] *= 0.5
    assert _run(dcfg, altered, index) != base


def test_run_longrun_refuses_a_missing_cpi(tmp_path):
    dcfg = load(tmp_path)
    with pytest.raises(ValueError, match="CPI"):
        _run(dcfg, index=cpi(start="2010-01-01"))


def _load_cli():
    spec = importlib.util.spec_from_file_location("longrun_cli", ROOT / "scripts" / "longrun.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()

LONGRUN_YAML = """\
version: 1
decision_sha256: "{sha}"
seed: 7
n_paths: 50
block_months: 12
horizon_years: 30
real_floor: 0.5
withdrawal_rates: [0.04]
cash_real_yield: 0.01
"""


def test_longrun_main_refuses_a_mismatched_decision_sha_and_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    def no_access(*args, **kwargs):
        raise AssertionError("data must not be loaded before the config pin is checked")

    monkeypatch.setattr(cli, "load_ohlcv", no_access)
    monkeypatch.setattr(cli, "load_macro", no_access)
    decision = write(tmp_path, GOOD)
    pinned = tmp_path / "longrun.yaml"
    pinned.write_text(LONGRUN_YAML.format(sha="00" * 32))
    out = tmp_path / "longrun.md"
    argv = ["--config", str(decision), "--longrun-config", str(pinned), "--out-md", str(out)]
    assert cli.main(argv) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("refused: ")
    assert "sha256" in printed
    assert not out.exists()
