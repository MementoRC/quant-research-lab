"""Tests for scripts/overlay.py: one run per step, hash binding,
validate/holdout gating and the one-time holdout. Offline; synthetic prices,
synthetic CPI and a temporary ledger. The verdict is forced via
qrl.overlay_eval.evaluate_pass so gating can be tested on random data.
Spec: docs/methodology/macro-overlay.md.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qrl import overlay_eval
from qrl.data import synthetic_prices
from qrl.ledger import Ledger
from qrl.macro import lag_to_availability, load_macro_config

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = (ROOT / "config" / "overlay.yaml").read_text()
CPI_LAG = load_macro_config(ROOT / "config" / "macro.yaml")["series"]["CPIAUCNS"]["lag"]


def _load_cli():
    spec = importlib.util.spec_from_file_location("overlay_cli", ROOT / "scripts" / "overlay.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()


def _fake_prices(tickers, refresh=False, cache_dir=None):
    return synthetic_prices(sorted(tickers), start="1999-01-01", end="2024-06-28")


def _fake_macro(ids=None, refresh=False, cache_dir=None, config_path=None):
    obs = pd.date_range("1990-01-01", "2024-04-01", freq="MS")
    s = pd.Series(100 * 1.02 ** (np.arange(len(obs)) / 12), index=obs)
    return pd.DataFrame({"CPIAUCNS": lag_to_availability(s, CPI_LAG)})


def _env(tmp_path: Path, monkeypatch, verdict: bool = True) -> None:
    (tmp_path / "overlay.yaml").write_text(SHIPPED.replace("n_draws: 1000", "n_draws: 3"))
    monkeypatch.setattr(cli, "load_prices", _fake_prices)
    monkeypatch.setattr(cli, "load_macro", _fake_macro)
    forced = [{"rule": "forced", "value": 0, "threshold": "-", "passed": verdict}]
    monkeypatch.setattr(overlay_eval, "evaluate_pass", lambda *a, **k: forced)


def _args(tmp_path: Path, step: str, *extra: str) -> list[str]:
    return [
        step,
        "--config",
        str(tmp_path / "overlay.yaml"),
        "--ledger",
        str(tmp_path / "ledger.sqlite"),
        "--out-md",
        str(tmp_path / "overlay.md"),
        *extra,
    ]


def _events(tmp_path: Path, kind: str) -> list[dict]:
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        return ledger.list_overlay_events(kind)


HOLDOUT = ("--unseal-holdout-once", "--reason", "owner go-ahead 2026-10-20")


def test_research_records_done_event_with_verdict_and_writes_report(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    assert cli.main(_args(tmp_path, "research")) == 0
    (ev,) = _events(tmp_path, "research")
    assert ev["status"] == "done"
    assert ev["passed"] is True
    assert ev["result"]["null"]["draws"] == 3
    assert f"event {ev['event_id']}" in (tmp_path / "overlay.md").read_text()


def test_second_research_run_is_refused(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, verdict=False)
    assert cli.main(_args(tmp_path, "research")) == 0
    assert cli.main(_args(tmp_path, "research")) == 1
    assert len(_events(tmp_path, "research")) == 1


def test_research_error_is_recorded_as_a_failure(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)

    def boom(*a, **k):
        raise ValueError("boom")

    monkeypatch.setattr(cli, "research_result", boom)
    assert cli.main(_args(tmp_path, "research")) == 1
    (ev,) = _events(tmp_path, "research")
    assert ev["status"] == "done"
    assert ev["passed"] is False
    assert ev["result"] == {"error": "boom"}


def test_crash_leaves_an_error_row_and_allows_a_rerun(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    real = cli.research_result

    def crash(*a, **k):
        raise KeyError("unexpected")

    monkeypatch.setattr(cli, "research_result", crash)
    with pytest.raises(KeyError):
        cli.main(_args(tmp_path, "research"))
    (ev,) = _events(tmp_path, "research")
    assert ev["status"] == "error"
    assert ev["result"] is None
    assert "unexpected" in ev["error"]

    monkeypatch.setattr(cli, "research_result", real)
    assert cli.main(_args(tmp_path, "research")) == 0
    assert [e["status"] for e in _events(tmp_path, "research")] == ["error", "done"]
    assert cli.main(_args(tmp_path, "research")) == 1  # a recorded result blocks reruns
    assert len(_events(tmp_path, "research")) == 2


def test_validate_works_after_a_research_rerun(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    real = cli.research_result
    monkeypatch.setattr(cli, "research_result", lambda *a, **k: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        cli.main(_args(tmp_path, "research"))
    monkeypatch.setattr(cli, "research_result", real)
    assert cli.main(_args(tmp_path, "research")) == 0
    assert cli.main(_args(tmp_path, "validate")) == 0


def _prices_between(start: str, end: str):
    def load(tickers, refresh=False, cache_dir=None):
        return synthetic_prices(sorted(tickers), start=start, end=end)

    return load


def test_research_refuses_stale_data(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "load_prices", _prices_between("1999-01-01", "2018-06-01"))
    assert cli.main(_args(tmp_path, "research")) == 1
    assert "2018-12-31" in capsys.readouterr().out
    assert _events(tmp_path, "research") == []


def test_research_refuses_data_that_starts_late(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "load_prices", _prices_between("2006-01-01", "2024-06-28"))
    assert cli.main(_args(tmp_path, "research")) == 1
    assert "2005-01-01" in capsys.readouterr().out
    assert _events(tmp_path, "research") == []


def test_validate_refuses_stale_data(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch)
    assert cli.main(_args(tmp_path, "research")) == 0
    monkeypatch.setattr(cli, "load_prices", _prices_between("1999-01-01", "2022-06-30"))
    assert cli.main(_args(tmp_path, "validate")) == 1
    assert "2022-12-31" in capsys.readouterr().out
    assert _events(tmp_path, "validate") == []


def test_validate_requires_research(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    assert cli.main(_args(tmp_path, "validate")) == 1
    assert _events(tmp_path, "validate") == []


def test_validate_requires_a_research_pass(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch, verdict=False)
    assert cli.main(_args(tmp_path, "research")) == 0
    assert cli.main(_args(tmp_path, "validate")) == 1
    assert "research failed" in capsys.readouterr().out
    assert _events(tmp_path, "validate") == []


def test_hash_change_is_refused(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch)
    assert cli.main(_args(tmp_path, "research")) == 0
    cfg = tmp_path / "overlay.yaml"
    cfg.write_text(cfg.read_text() + "\n# edited after research\n")
    assert cli.main(_args(tmp_path, "validate")) == 1
    assert "changed since research" in capsys.readouterr().out
    assert _events(tmp_path, "validate") == []


def test_validate_after_pass_is_stamped_validation_seen_and_runs_once(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    assert cli.main(_args(tmp_path, "research")) == 0
    assert cli.main(_args(tmp_path, "validate")) == 0
    assert "VALIDATION-SEEN" in (tmp_path / "overlay.md").read_text()
    assert cli.main(_args(tmp_path, "validate")) == 1
    assert len(_events(tmp_path, "validate")) == 1


def test_holdout_needs_flag_and_reason(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    assert cli.main(_args(tmp_path, "research")) == 0
    assert cli.main(_args(tmp_path, "holdout")) == 2
    assert cli.main(_args(tmp_path, "holdout", "--unseal-holdout-once")) == 2
    assert cli.main(_args(tmp_path, "holdout", "--reason", "go")) == 2
    assert _events(tmp_path, "holdout") == []


def test_holdout_requires_a_research_pass(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, verdict=False)
    assert cli.main(_args(tmp_path, "research")) == 0
    assert cli.main(_args(tmp_path, "holdout", *HOLDOUT)) == 1
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        assert ledger.list_holdout_events() == []


def test_second_holdout_run_is_refused(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    assert cli.main(_args(tmp_path, "research")) == 0
    assert cli.main(_args(tmp_path, "holdout", *HOLDOUT)) == 0
    (ev,) = _events(tmp_path, "holdout")
    assert ev["status"] == "done"
    assert ev["result"]["window"][0] >= "2023-01-01"
    assert cli.main(_args(tmp_path, "holdout", *HOLDOUT)) == 1
    assert len(_events(tmp_path, "holdout")) == 1
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        assert len(ledger.list_holdout_events()) == 1


def test_holdout_refused_if_anything_else_unsealed_it(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    assert cli.main(_args(tmp_path, "research")) == 0
    with Ledger(tmp_path / "ledger.sqlite") as ledger:
        ledger.record_holdout_event("an earlier process", "earlier reason")
    assert cli.main(_args(tmp_path, "holdout", *HOLDOUT)) == 1
    assert _events(tmp_path, "holdout") == []
