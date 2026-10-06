"""Tests for the core shortlist reveal (qrl.core_reveal, scripts/core_reveal.py).
Offline; synthetic prices and a temporary ledger only.
Spec: docs/methodology/core-reveal.md.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from qrl import core_reveal
from qrl.core_compare import load_core_candidates, stress_portfolios
from qrl.core_reveal import (
    guard,
    load_core_shortlist,
    render_markdown,
    run_core_reveal,
)
from qrl.criteria import load_criteria
from qrl.data import synthetic_prices
from qrl.ledger import Ledger
from qrl.stress import StressConfig, Window, load_stress_config

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = pd.Timestamp("2023-01-01")
SPLIT = {"core": 0.8, "sleeve": 0.2}
TICKERS = ["SPY", "GLD", "IEF", "TLT", "SHY"]
LAST_END = pd.Timestamp("2022-10-31")
SHIPPED = (ROOT / "config" / "core_shortlist.yaml").read_text()


def _criteria() -> dict:
    return load_criteria(ROOT / "config" / "criteria.yaml")[0]


def _data(end: str = "2023-06-30") -> dict[str, pd.DataFrame]:
    open_, close = synthetic_prices(TICKERS, start="2017-01-01", end=end)
    return {"open": open_, "close": close}


def _env():
    cands, cand_hash = load_core_candidates(ROOT / "config" / "core_candidates.yaml")
    cfg, _ = load_stress_config(ROOT / "config" / "stress.yaml", HOLDOUT)
    return cands, cand_hash, cfg


def _load(tmp_path: Path, text: str, cfg=None):
    cands, cand_hash, real_cfg = _env()
    p = tmp_path / "core_shortlist.yaml"
    p.write_text(text)
    return load_core_shortlist(p, cands, cand_hash, cfg or real_cfg, _criteria())


def test_shipped_shortlist_loads():
    cands, cand_hash, cfg = _env()
    sl, digest = load_core_shortlist(
        ROOT / "config" / "core_shortlist.yaml", cands, cand_hash, cfg, _criteria()
    )
    assert sl.ids == ["E", "F", "G"]
    assert sl.windows == ["covid_2020", "inflation_2022"]
    assert sl.decided_by == "owner"
    assert len(digest) == 64


def test_shortlist_rejects_wrong_version(tmp_path):
    with pytest.raises(ValueError, match="version"):
        _load(tmp_path, SHIPPED.replace("version: 1", "version: 2"))


@pytest.mark.parametrize("ids", ["[]", "[E, E]"])
def test_shortlist_rejects_empty_or_duplicate_ids(tmp_path, ids):
    with pytest.raises(ValueError, match="ids"):
        _load(tmp_path, SHIPPED.replace("ids: [E, F, G]", f"ids: {ids}"))


def test_shortlist_rejects_unknown_id(tmp_path):
    with pytest.raises(ValueError, match="not in the candidates"):
        _load(tmp_path, SHIPPED.replace("[E, F, G]", "[E, F, Z]"))


def test_shortlist_rejects_stale_candidates_hash(tmp_path):
    with pytest.raises(ValueError, match="candidates_sha256"):
        _load(tmp_path, SHIPPED.replace("1a84847e", "00000000"))


@pytest.mark.parametrize("windows", ["[]", "[covid_2020, covid_2020]"])
def test_shortlist_rejects_empty_or_duplicate_windows(tmp_path, windows):
    text = SHIPPED.replace("[covid_2020, inflation_2022]", windows)
    with pytest.raises(ValueError, match="windows"):
        _load(tmp_path, text)


def test_shortlist_rejects_window_not_in_stress_yaml(tmp_path):
    with pytest.raises(ValueError, match="not in stress.yaml"):
        _load(tmp_path, SHIPPED.replace("covid_2020", "nope_2020"))


def test_shortlist_rejects_window_before_validation(tmp_path):
    with pytest.raises(ValueError, match="nothing to reveal"):
        _load(tmp_path, SHIPPED.replace("covid_2020", "gfc_2008"))


def test_shortlist_rejects_window_reaching_holdout(tmp_path):
    _, _, cfg = _env()
    late = Window("late", pd.Timestamp("2022-12-01"), pd.Timestamp("2023-02-01"), True)
    bad = StressConfig([*cfg.windows, late], cfg.hypotheticals, cfg.max_report_age_days)
    with pytest.raises(ValueError, match="holdout"):
        _load(tmp_path, SHIPPED.replace("covid_2020", "late"), cfg=bad)


def _run(data=None):
    cands, cand_hash, cfg = _env()
    sl, _ = load_core_shortlist(
        ROOT / "config" / "core_shortlist.yaml", cands, cand_hash, cfg, _criteria()
    )
    return run_core_reveal(sl, cands, cfg, data or _data(), _criteria(), SPLIT, 0.35)


def test_only_shortlisted_ids_and_named_windows_no_hypotheticals():
    out = _run()
    assert [c["id"] for c in out["candidates"]] == ["E", "F", "G"]
    cells = [cell for c in out["candidates"] for cell in c["cells"]]
    assert cells
    assert {c["scenario"] for c in cells} == {"covid_2020", "inflation_2022"}
    assert "hypothetical" not in {c["mode"] for c in cells}
    assert {c["portfolio"].split("[")[0] for c in cells} == {"E", "F", "G"}


def test_switching_candidate_is_split_into_replay_and_branches():
    out = _run()
    f = next(c for c in out["candidates"] if c["id"] == "F")
    by_portfolio: dict[str, set[str]] = {}
    for cell in f["cells"]:
        by_portfolio.setdefault(cell["portfolio"], set()).add(cell["mode"])
    assert by_portfolio == {
        "F": {"replay"},
        "F[risk_on]": {"frozen"},
        "F[risk_off]": {"frozen"},
    }
    e = next(c for c in out["candidates"] if c["id"] == "E")
    assert {c["mode"] for c in e["cells"]} == {"replay", "frozen"}


def test_no_frame_row_after_last_window_end_reaches_run_stress(monkeypatch):
    seen: list[pd.Timestamp] = []
    real = core_reveal.run_stress

    def spy(cfg, portfolios, data, max_drawdown, criteria):
        seen.extend(v.index.max() for v in data.values())
        assert cfg.hypotheticals == []
        assert {w.name for w in cfg.windows} == {"covid_2020", "inflation_2022"}
        return real(cfg, portfolios, data, max_drawdown, criteria)

    monkeypatch.setattr(core_reveal, "run_stress", spy)
    data = _data()
    assert data["close"].index.max() > LAST_END
    _run(data)
    assert seen
    assert all(ts <= LAST_END for ts in seen)


def test_guard_passes_for_static_mixes_and_branches():
    cands, _, _ = _env()
    chosen = [c for c in cands if c.id in {"E", "F", "G"}]
    portfolios, modes = stress_portfolios(chosen, SPLIT)
    guard(portfolios, modes, _data())  # must not raise


def test_guard_ignores_zero_filled_rows_before_a_late_ticker_exists():
    cands, _, _ = _env()
    chosen = [c for c in cands if c.id in {"E", "G"}]
    portfolios, modes = stress_portfolios(chosen, SPLIT)
    data = _data()
    data["close"].loc[data["close"].index[:300], "GLD"] = float("nan")
    # build zero-fills the unpriced rows: they are all-zero, not NaN
    assert (portfolios[0].build(data, ["SPY"]).iloc[:300].sum(axis=1) == 0).all()
    guard(portfolios, modes, data)  # must not raise


def test_guard_still_raises_for_switching_rule_with_late_ticker():
    cands, _, _ = _env()
    f = [c for c in cands if c.id == "F"]
    portfolios, modes = stress_portfolios(f, SPLIT)
    modes["F"] = frozenset({"frozen"})
    data = _data("2022-10-31")
    data["close"].loc[data["close"].index[:300], "GLD"] = float("nan")
    with pytest.raises(ValueError, match="look-ahead"):
        guard(portfolios, modes, data)


def test_guard_raises_for_switching_rule_in_frozen_mode():
    cands, _, _ = _env()
    f = [c for c in cands if c.id == "F"]
    portfolios, modes = stress_portfolios(f, SPLIT)
    modes["F"] = frozenset({"frozen"})  # a switching rule wrongly given frozen cells
    with pytest.raises(ValueError, match="look-ahead"):
        guard(portfolios, modes, _data("2022-10-31"))


def test_run_core_reveal_refuses_switching_rule_in_frozen_mode(monkeypatch):
    real = core_reveal.stress_portfolios

    def wrong(cands, split):
        portfolios, modes = real(cands, split)
        modes["F"] = frozenset({"frozen"})
        return portfolios, modes

    monkeypatch.setattr(core_reveal, "stress_portfolios", wrong)
    with pytest.raises(ValueError, match="look-ahead"):
        _run()


def test_markdown_has_banner_and_hashes():
    out = _run()
    report = {
        "event_id": 7,
        "shortlist_sha256": "a" * 64,
        "candidates_sha256": "b" * 64,
        "stress_sha256": "c" * 64,
        "max_drawdown": 0.35,
        "trial_count": 7,
        "shortlist_size": 3,
        **out,
    }
    md = render_markdown(report)
    assert (
        "VALIDATION-SEEN: these cells use validation-period data (2020, 2022). One look, "
        "recorded in the ledger (event id 7)."
    ) in md
    for h in ("a" * 64, "b" * 64, "c" * 64):
        assert h in md
    assert "35%" in md
    assert "trial count of the original comparison: 7" in md
    assert "shortlist size: 3" in md
    assert "covid_2020" in md
    assert "inflation_2022" in md


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "core_reveal_cli", ROOT / "scripts" / "core_reveal.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()


def _fake_ohlcv(nan_ticker: str | None = None):
    def fake(tickers, refresh=False):
        open_, close = synthetic_prices(tickers, start="2017-01-01", end="2023-06-30")
        if nan_ticker:
            close.loc[close.loc[:LAST_END].index[-1], nan_ticker] = float("nan")
        return {"open": open_, "close": close}

    return fake


def _args(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "--ledger",
        str(tmp_path / "ledger.sqlite"),
        "--out-json",
        str(tmp_path / "r.json"),
        "--out-md",
        str(tmp_path / "r.md"),
        *extra,
    ]


def _events(tmp_path: Path) -> list[dict]:
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        return ledger.list_reveal_events("core_reveal")


def test_ledger_reveal_events_roundtrip(tmp_path):
    with Ledger(tmp_path / "l.sqlite") as ledger:
        eid = ledger.record_reveal_event("k", "s", "c", "t", ["E"], ["w"])
        assert ledger.list_reveal_events("k")[0]["status"] == "started"
        ledger.finish_reveal_event(eid)
        (ev,) = ledger.list_reveal_events("k")
        assert ev["event_id"] == eid
        assert ev["status"] == "done"
        assert ev["ids"] == ["E"]
        assert ledger.list_reveal_events("other") == []


def test_cli_requires_confirm(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    assert cli.main(_args(tmp_path)) == 2
    assert not (tmp_path / "r.json").exists()
    assert _events(tmp_path) == []


def test_cli_first_run_records_started_then_done(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    assert cli.main(_args(tmp_path, "--confirm")) == 0
    (ev,) = _events(tmp_path)
    assert ev["status"] == "done"
    assert not ev["forced"]
    report = json.loads((tmp_path / "r.json").read_text())
    assert report["event_id"] == ev["event_id"]
    assert report["trial_count"] == 7
    assert report["shortlist_size"] == 3
    assert f"event id {ev['event_id']}" in (tmp_path / "r.md").read_text()


def test_cli_started_event_exists_before_compute(tmp_path, monkeypatch):
    seen: list[str] = []

    def spy(*a, **k):
        seen.extend(e["status"] for e in _events(tmp_path))
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    monkeypatch.setattr(cli, "run_core_reveal", spy)
    with pytest.raises(RuntimeError):
        cli.main(_args(tmp_path, "--confirm"))
    assert seen == ["started"]


def test_cli_second_run_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    assert cli.main(_args(tmp_path, "--confirm")) == 0
    (tmp_path / "r.json").unlink()
    assert cli.main(_args(tmp_path, "--confirm")) == 1
    assert not (tmp_path / "r.json").exists()
    assert len(_events(tmp_path)) == 1


def test_cli_force_without_reason_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    assert cli.main(_args(tmp_path, "--confirm")) == 0
    assert cli.main(_args(tmp_path, "--confirm", "--force")) == 2
    assert cli.main(_args(tmp_path, "--confirm", "--force", "--reason", "  ")) == 2
    assert len(_events(tmp_path)) == 1


def test_cli_force_with_reason_records_forced_event(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    assert cli.main(_args(tmp_path, "--confirm")) == 0
    assert cli.main(_args(tmp_path, "--confirm", "--force", "--reason", "re-check data")) == 0
    first, second = _events(tmp_path)
    assert not first["forced"]
    assert second["forced"]
    assert second["reason"] == "re-check data"
    assert second["status"] == "done"


def test_cli_crash_leaves_started_and_blocks_next_run(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    monkeypatch.setattr(cli, "run_core_reveal", boom)
    with pytest.raises(RuntimeError):
        cli.main(_args(tmp_path, "--confirm"))
    (ev,) = _events(tmp_path)
    assert ev["status"] == "started"
    monkeypatch.undo()
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    assert cli.main(_args(tmp_path, "--confirm")) == 1
    assert len(_events(tmp_path)) == 1


def test_cli_guard_failure_returns_nonzero_and_spends_no_look(tmp_path, monkeypatch, capsys):
    real = core_reveal.stress_portfolios

    def wrong(cands, split):
        portfolios, modes = real(cands, split)
        modes["F"] = frozenset({"frozen"})
        return portfolios, modes

    def boom(*a, **k):
        raise AssertionError("run_core_reveal must not be called")

    monkeypatch.setattr(core_reveal, "stress_portfolios", wrong)
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    monkeypatch.setattr(cli, "run_core_reveal", boom)
    assert cli.main(_args(tmp_path, "--confirm")) == 1
    assert "look-ahead" in capsys.readouterr().out
    assert not (tmp_path / "r.json").exists()
    assert _events(tmp_path) == []


def test_cli_fails_loudly_on_unpriced_ticker_before_lock(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("run_core_reveal must not be called")

    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv(nan_ticker="IEF"))
    monkeypatch.setattr(cli, "run_core_reveal", boom)
    assert cli.main(_args(tmp_path, "--confirm")) == 1
    assert "IEF" in capsys.readouterr().out
    assert not (tmp_path / "r.json").exists()
    assert _events(tmp_path) == []  # a data failure does not spend the look
