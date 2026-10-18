"""What-if shock (spec: docs/methodology/whatif-shock.md): qrl.shock_report and
scripts/whatif_shock.py. Offline: the shipped config/decision.yaml plus synthetic
prices and CPI. Existing tests are untouched."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import tomllib
from dataclasses import replace

import pandas as pd
import pytest
from decision_helpers import CANDIDATES, END, ROOT, cpi, criteria, prices, stress_cfg
from test_decision_cli import _fake_macro, _fake_ohlcv
from test_shock import GOOD_SHOCK, SHOCK2, _shock_text, _small, _year_text

from qrl.core_compare import Candidate
from qrl.decision_config import Portfolio, load_decision_config
from qrl.decision_report import pct
from qrl.shock import extend_config, run_shock
from qrl.shock_report import rate_text, render_shock, summary_lines
from qrl.whatif_report import report_path

GIVEN = [("A", 0.8), ("TCASH", 0.2)]


def _shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


@pytest.fixture(scope="module")
def report():
    base = _small(_shipped(), years=(2005, 2006), rates=(0.04,))
    cfg = extend_config(base, GIVEN, None)
    return run_shock(cfg, prices(), cpi(), criteria(), SHOCK2, "cd" * 32)


def test_render_header_shock_table_and_assumptions(report):
    md = render_shock(report, GIVEN)
    assert md.startswith("# What-if shock: t2")
    assert "came from a file, not from `config/decision.yaml`" in md
    assert "N = 2 year(s)" in md
    assert "| 1 | -30.0% | 20.0% | -15.0% | 1.0% | 9.0% |" in md
    assert "| 2 | -10.0% | 10.0% | -10.0% | 2.0% | 8.0% |" in md
    assert "mix as given: A 80%, TCASH 20%" in md
    assert f"decision.yaml sha256: `{report['decision_sha256']}`" in md
    assert f"core_candidates.yaml sha256: `{report['candidates_sha256']}`" in md
    assert f"stress.yaml sha256: `{'cd' * 32}`" in md
    assert "data: up to 2018-12-31 only" in md
    assert "2 year(s) longer than the report's" in md
    for phrase in (
        "QQQ is treated as SPY",
        "midpoint of the `long_bonds` and `short_bonds`",
        "rebalanced daily, with no costs",
        "`short_bonds` in the stretch and CPI plus +1% real after it",
        "made up",
        "rescaled",
        "purchase cost",
        "CASH here is SHY",
    ):
        assert phrase in md
    assert "### Withdrawal rate 4.0% per year" in md
    assert "below peak at end" not in md
    assert "$" not in md


def test_render_rows_show_shocked_then_no_shock(report):
    md = render_shock(report, GIVEN)
    lines = md.splitlines()
    rows = {r["portfolio"]: r for r in report["rows"]}
    a = rows["A"]
    line = next(x for x in lines if x.startswith(f"| A ({a['state']}) |"))
    s, b = a["shocked"], a["no_shock"]
    assert f"{pct(s['first']['end_real'])} (no shock: {pct(b['first']['end_real'])})" in line
    wy = s["worst_year"]
    assert f"{wy + 2}, {s['horizons'][wy]} y ({pct(s['worst_end_real'])})" in line
    assert f"{s['worst5_year'] + 2}, {s['horizon_years']} y" in line
    assert f"(no shock: {b['worst_year']}, {b['horizons'][b['worst_year']]} y" in line
    assert any(x.startswith("| D |") for x in lines)
    assert any(x.startswith(f"| MIX-TCASH ({rows['MIX-TCASH']['state']}) |") for x in lines)


def test_render_lists_every_state_of_a_switching_row(report):
    lines = render_shock(report, GIVEN).splitlines()
    a = next(r for r in report["rows"] if r["portfolio"] == "A")
    for state in ("risk_on", "risk_off"):
        assert any(x.startswith(f"| A | {state} |") for x in lines)
    headlined = next(x for x in lines if x.startswith(f"| A | {a['state']} |"))
    assert headlined.endswith("| yes |")


def test_render_is_deterministic_and_has_no_mix_lines_without_a_mix(report):
    assert render_shock(report, GIVEN) == render_shock(report, GIVEN)
    assert "mix as given" not in render_shock(report, None)


def test_summary_lines(report, tmp_path):
    path = tmp_path / "x.md"
    lines = summary_lines(report, path)
    assert lines[:2] == ["shock: t2, N = 2 year(s)", f"wrote: {path}"]
    assert [x.split(",")[0] for x in lines[2:]] == ["MIX", "MIX-TCASH", "A", "CASH"]
    assert all("(no shock: " in x for x in lines[2:])
    a = next(r for r in report["rows"] if r["portfolio"] == "A")
    assert f"(worse stretch state: {a['state']})" in lines[4]
    assert f"at 4.0%: {pct(a['shocked']['first']['end_real'])} (no shock: " in lines[4]
    assert "(worse stretch state: " not in lines[5]  # CASH is static


def test_render_explains_the_state_label(report):
    md = render_shock(report, GIVEN)
    note = (
        "For switching rows, the state shown is the fixed-weight state that ends lowest "
        "at its worst start year during the stretch; it is not the live rule's choice."
    )
    assert md.count(note) == len(report["rates"])
    assert (
        "A depleted date marked (stretch) falls in the made-up years before the start "
        "year, not in real history." in md
    )


def _depleted_row(report, pid, when):
    row = next(r for r in report["rows"] if r["portfolio"] == pid)
    row["shocked"]["first"]["depleted"] = when
    return row


def test_render_marks_a_depletion_inside_the_stretch(report):
    rep = copy.deepcopy(report)
    row = _depleted_row(rep, "D", "2003-05")  # first real start year is 2005
    assert row["shocked"]["first_year"] + rep["n"] == 2005
    _depleted_row(rep, "CASH", "2006-01")  # real history: no marker
    lines = render_shock(rep, GIVEN).splitlines()
    d = next(x for x in lines if x.startswith("| D |"))
    cash = next(x for x in lines if x.startswith("| CASH |"))
    assert "2003-05 (stretch)" in d
    assert "2006-01" in cash
    assert "2006-01 (stretch)" not in cash


def test_render_every_table_row_has_the_header_cell_count(report):
    lines = render_shock(report, GIVEN).splitlines()
    checked = 0
    for i, line in enumerate(lines):
        if line.startswith("|") and (i == 0 or not lines[i - 1].startswith("|")):
            width = line.count("|")
            block = []
            for x in lines[i:]:
                if not x.startswith("|"):
                    break
                block.append(x)
            assert all(x.count("|") == width for x in block), block[0]
            checked += 1
    assert checked >= 3  # the shock table and, per rate, the rows and the state tables


def test_rate_text_keeps_two_decimals_where_needed():
    assert rate_text(0.0425) == "4.25%"
    assert rate_text(0.04) == "4.0%"
    assert rate_text(0.033) == "3.3%"
    assert rate_text(-0.3) == "-30.0%"


def test_whatif_shock_pixi_task():
    tasks = tomllib.loads((ROOT / "pixi.toml").read_text())["tasks"]
    assert tasks["whatif-shock"] == "python scripts/whatif_shock.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "whatif_shock_cli", ROOT / "scripts" / "whatif_shock.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


QUICK_IDS = ("A", "B", "CASH", "D", "AG")


def _trimmed(cfg):
    """A few portfolios (two switching, a static, a blend holding TLT), the A and
    B cash rows, two start years, one rate: fast but every row kind."""
    by_id = {p.id: p for p in cfg.portfolios}
    return replace(
        cfg,
        portfolios=[by_id[i] for i in QUICK_IDS],
        cash_assumptions=cfg.cash_assumptions[:2],
        start_years=[2005, 2006],
        rates=[0.04],
    )


def _cli(tmp_path, monkeypatch, shape):
    """The CLI with synthetic data, the loaded config passed through `shape`,
    and reports under tmp_path. Loaded here, not at import."""
    cli = _load_cli()
    real = cli.load_decision_config
    monkeypatch.setattr(cli, "load_decision_config", lambda *a, **k: shape(real(*a, **k)))
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    monkeypatch.setattr(cli, "load_macro", _fake_macro(cpi()))
    monkeypatch.setattr(cli, "REPORTS", tmp_path / "reports")
    return cli


@pytest.fixture
def run(tmp_path, monkeypatch):
    return _cli(tmp_path, monkeypatch, _trimmed)


@pytest.fixture
def shock_file(tmp_path):
    path = tmp_path / "stagflation.yaml"
    path.write_text(GOOD_SHOCK)
    return path


def _out(tmp_path):
    return tmp_path / "reports" / "whatif-shock-stagflation-5y.md"


def _refused(cli, args, tmp_path, capsys):
    assert cli.main(args) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("refused: ")
    assert not (tmp_path / "reports").exists()  # nothing written
    return printed


def test_whatif_shock_main_writes_the_report(run, tmp_path, shock_file, capsys):
    assert run.main(["--shock", str(shock_file)]) == 0
    out = _out(tmp_path)
    assert list((tmp_path / "reports").iterdir()) == [out]
    printed = capsys.readouterr().out
    assert printed.splitlines()[:2] == [
        "shock: stagflation-5y, N = 2 year(s)",
        f"wrote: {out.resolve()}",
    ]
    assert "A, real ending value" in printed
    assert "CASH, real ending value" in printed
    assert "MIX" not in printed
    assert "## Withdrawals" not in printed  # a summary, not the whole report
    md = out.read_text()
    lines = md.splitlines()
    for pid in (*QUICK_IDS, "A80-TCASH20", "B80-TCASH20"):
        assert any(x.startswith((f"| {pid} |", f"| {pid} (")) for x in lines)
    assert "| MIX" not in md


def test_whatif_shock_main_mix_adds_mix_rows(run, tmp_path, shock_file, capsys):
    assert run.main(["--shock", str(shock_file), "--mix", "A=0.8,TCASH=0.2"]) == 0
    md = _out(tmp_path).read_text()
    assert "| MIX (" in md
    assert "| MIX-TCASH (" in md
    assert "mix as given: A 80%, TCASH 20%" in md
    printed = capsys.readouterr().out
    assert [x.split(",")[0] for x in printed.splitlines()[2:]] == ["MIX", "MIX-TCASH", "A", "CASH"]


def test_whatif_shock_main_tcash_one_has_only_mix_tcash(run, tmp_path, shock_file):
    assert run.main(["--shock", str(shock_file), "--mix", "TCASH=1"]) == 0
    md = _out(tmp_path).read_text()
    assert "| MIX-TCASH |" in md
    assert "| MIX |" not in md
    assert "| MIX (" not in md


def test_whatif_shock_main_extra_rate(run, tmp_path, shock_file):
    assert run.main(["--shock", str(shock_file), "--rate", "0.045"]) == 0
    assert "### Withdrawal rate 4.5% per year" in _out(tmp_path).read_text()


def test_whatif_shock_main_rate_heading_keeps_its_precision(run, tmp_path, shock_file, capsys):
    assert run.main(["--shock", str(shock_file), "--rate", "0.0425"]) == 0
    assert "### Withdrawal rate 4.25% per year" in _out(tmp_path).read_text()
    assert "at 4.25%: " in capsys.readouterr().out


def test_whatif_shock_main_resolves_a_relative_shock_path(run, tmp_path, shock_file, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run.main(["--shock", shock_file.name]) == 0
    assert _out(tmp_path).exists()


def test_whatif_shock_main_refuses_without_shock(run, tmp_path, capsys):
    assert "--shock is required" in _refused(run, [], tmp_path, capsys)


def test_whatif_shock_main_refuses_a_missing_shock_file(run, tmp_path, capsys):
    args = ["--shock", str(tmp_path / "nope.yaml")]
    assert "cannot be read" in _refused(run, args, tmp_path, capsys)


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("name: [unclosed\n", "not valid YAML"),
        (_shock_text(_year_text(), name="bad/name"), "must match"),
        (_shock_text(*[_year_text()] * 11), "1 to 10"),
        (_shock_text(_year_text(cash=0.0)), "unknown key"),
        (_shock_text(_year_text(stocks=-1)), "above -1"),
        (_shock_text(_year_text(inflation=0.31)), "inflation"),
    ],
)
def test_whatif_shock_main_refuses_a_bad_shock_file(run, tmp_path, capsys, text, match):
    path = tmp_path / "bad.yaml"
    path.write_text(text)
    assert match in _refused(run, ["--shock", str(path)], tmp_path, capsys)


@pytest.mark.parametrize(
    ("extra", "match"),
    [
        (["--mix", "A"], "NAME=SHARE"),
        (["--mix", "A=x"], "not a number"),
        (["--mix", "A=0.5,A=0.5"], "repeated"),
        (["--mix", "Z=1"], "unknown mix name"),
        (["--mix", "A=0.5,CASH=0.4"], "sum"),
        (["--rate", "x"], "not a number"),
        (["--rate", "0.11"], "--rate"),
        (["--rate", "0"], "--rate"),
    ],
)
def test_whatif_shock_main_refuses_a_bad_mix_or_rate(
    run, tmp_path, shock_file, capsys, extra, match
):
    args = ["--shock", str(shock_file), *extra]
    assert match in _refused(run, args, tmp_path, capsys)


def _odd(cfg):
    cfg = _trimmed(cfg)
    rows = list(cfg.cash_assumptions)
    rows[1] = replace(rows[1], real_yield=0.02)
    return replace(cfg, cash_assumptions=tuple(rows))


def test_whatif_shock_main_with_a_mix_refuses_cash_rows_with_different_yields(
    tmp_path, monkeypatch, shock_file, capsys
):
    cli = _cli(tmp_path, monkeypatch, _odd)
    args = ["--shock", str(shock_file), "--mix", "A=0.8,TCASH=0.2"]
    assert "different real_yield" in _refused(cli, args, tmp_path, capsys)


def test_whatif_shock_main_without_a_mix_runs_cash_rows_with_different_yields(
    tmp_path, monkeypatch, shock_file
):
    cli = _cli(tmp_path, monkeypatch, _odd)
    assert cli.main(["--shock", str(shock_file)]) == 0
    md = _out(tmp_path).read_text()
    assert "CPI plus A80-TCASH20 +1% / B80-TCASH20 +2% real after it" in md
    assert "| MIX" not in md


def test_whatif_shock_main_refuses_a_cpi_with_no_value_on_the_join_date(
    tmp_path, monkeypatch, shock_file, capsys
):
    # No cash rows: their strict monthly CPI check would refuse first, with its own
    # message. For the portfolios, 30 Nov 2004 keeps every no-shock figure
    # computable (usable within 45 days); only the strict join refuses.
    cli = _cli(tmp_path, monkeypatch, lambda cfg: replace(_trimmed(cfg), cash_assumptions=()))
    monkeypatch.setattr(cli, "load_macro", _fake_macro(cpi().drop(pd.Timestamp("2004-12-31"))))
    printed = _refused(cli, ["--shock", str(shock_file)], tmp_path, capsys)
    assert "missing CPI: no CPIAUCNS value dated 2004-12-31 for the join" in printed


def test_whatif_shock_main_refuses_a_held_fund_outside_the_map(
    tmp_path, monkeypatch, shock_file, capsys
):
    cand = Candidate("X", "x", "core_mix", {"risk_on": {"EFA": 1.0}})

    def foreign(cfg):
        cfg = _trimmed(cfg)
        return replace(cfg, portfolios=[*cfg.portfolios, Portfolio("X", "x", ((cand, 1.0),))])

    cli = _cli(tmp_path, monkeypatch, foreign)
    args = ["--shock", str(shock_file)]
    assert "no shock group" in _refused(cli, args, tmp_path, capsys)


def test_whatif_shock_main_refuses_missing_cpi(run, tmp_path, monkeypatch, shock_file, capsys):
    monkeypatch.setattr(run, "load_macro", _fake_macro(cpi().loc[:"2005-06-30"]))
    assert "missing CPI" in _refused(run, ["--shock", str(shock_file)], tmp_path, capsys)


def test_whatif_shock_main_refuses_an_unpriced_held_fund(
    run, tmp_path, monkeypatch, shock_file, capsys
):
    fake = _fake_ohlcv()

    def holes(tickers, refresh=False, cache_dir=None):
        data = fake(tickers, refresh=refresh, cache_dir=cache_dir)
        close = data["close"]
        close.loc[close.index[close.index >= "2005-01-01"][0], "TLT"] = float("nan")
        return data

    monkeypatch.setattr(run, "load_ohlcv", holes)
    printed = _refused(run, ["--shock", str(shock_file)], tmp_path, capsys)
    assert "unpriced at the start" in printed


def test_whatif_shock_main_refuses_a_missing_ticker(run, tmp_path, monkeypatch, shock_file, capsys):
    monkeypatch.setattr(run, "load_ohlcv", _fake_ohlcv(drop="TLT"))
    assert "TLT" in _refused(run, ["--shock", str(shock_file)], tmp_path, capsys)


def test_whatif_shock_main_refuses_when_loading_criteria_fails(
    run, tmp_path, monkeypatch, shock_file, capsys
):
    def boom(path):
        raise ValueError("criteria broken")

    monkeypatch.setattr(run, "load_criteria", boom)
    assert run.main(["--shock", str(shock_file)]) == 1
    assert capsys.readouterr().out == "refused: criteria broken\n"
    assert not (tmp_path / "reports").exists()


def test_whatif_shock_ignores_prices_and_cpi_after_the_data_end(
    run, tmp_path, monkeypatch, shock_file
):
    args = ["--shock", str(shock_file), "--mix", "A=0.8,TCASH=0.2"]
    assert run.main(args) == 0
    before = _out(tmp_path).read_text()

    fake = _fake_ohlcv()

    def tampered(tickers, refresh=False, cache_dir=None):
        data = fake(tickers, refresh=refresh, cache_dir=cache_dir)
        for frame in data.values():
            frame.loc[frame.index > END] = frame.loc[frame.index > END] * 7.0
        return data

    late_cpi = cpi()
    late_cpi.loc[late_cpi.index > END] = late_cpi.loc[late_cpi.index > END] * 5.0
    # not vacuous: the tampering really changes data after the data end
    cache = ROOT / "data" / "cache"  # `_fake_ohlcv` asserts this cache_dir
    assert not tampered(["SPY"], cache_dir=cache)["close"].equals(
        fake(["SPY"], cache_dir=cache)["close"]
    )
    monkeypatch.setattr(run, "load_ohlcv", tampered)
    monkeypatch.setattr(run, "load_macro", _fake_macro(late_cpi))
    assert run.main(args) == 0
    assert _out(tmp_path).read_text() == before


def _digest(path):
    data = path.read_bytes()
    return data, hashlib.sha256(data).hexdigest()


def test_whatif_shock_leaves_decision_yaml_and_the_shock_file_unchanged(run, shock_file):
    paths = [ROOT / "config" / "decision.yaml", shock_file]
    before = [_digest(p) for p in paths]
    assert run.main(["--shock", str(shock_file), "--mix", "A=0.8,TCASH=0.2"]) == 0
    assert [_digest(p) for p in paths] == before


def test_whatif_shock_output_path_is_under_reports(run, tmp_path, shock_file):
    reports = tmp_path / "reports"
    want = (reports / "whatif-shock-stagflation-5y.md").resolve()
    assert report_path(reports, "shock-stagflation-5y") == want
    assert run.main(["--shock", str(shock_file)]) == 0
    written = [p.resolve() for p in reports.rglob("*") if p.is_file()]
    assert written == [want]
    assert want.parent == reports.resolve()


def _mtimes(folder):
    if not folder.exists():
        return {}
    return {p: p.stat().st_mtime_ns for p in folder.rglob("*") if p.is_file()}


def test_whatif_shock_writes_nothing_under_research_or_site(run, shock_file):
    before = {d: _mtimes(ROOT / d) for d in ("research", "site")}
    assert run.main(["--shock", str(shock_file)]) == 0
    assert {d: _mtimes(ROOT / d) for d in ("research", "site")} == before


def test_whatif_shock_full_config_has_every_row(tmp_path, monkeypatch, shock_file):
    cli = _cli(tmp_path, monkeypatch, lambda cfg: replace(cfg, start_years=[2005], rates=[0.04]))
    assert cli.main(["--shock", str(shock_file)]) == 0
    lines = _out(tmp_path).read_text().splitlines()
    shipped = _shipped()
    ids = [p.id for p in shipped.portfolios] + [c.id for c in shipped.cash_assumptions]
    assert len(ids) == 27 + 7
    for pid in ids:
        assert any(x.startswith((f"| {pid} |", f"| {pid} (")) for x in lines), pid
