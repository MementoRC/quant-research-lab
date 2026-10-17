"""What-if mix (spec: docs/methodology/whatif-mix.md). Offline: the shipped
config/decision.yaml plus synthetic prices and CPI. Existing tests are untouched."""

from __future__ import annotations

import importlib.util
import tomllib
from dataclasses import replace

import pytest
from decision_helpers import CANDIDATES, END, ROOT, cpi, criteria, prices, stress_cfg
from test_decision_cli import _fake_macro, _fake_ohlcv

from qrl import decision_config, decision_report
from qrl.decision import run_decision
from qrl.decision_config import load_decision_config, portfolio_states
from qrl.whatif import (
    merge_rate,
    mix_cash_row,
    mix_config,
    mix_portfolio,
    parse_mix,
    parse_rate,
    split_shares,
    valid_names,
)
from qrl.whatif_report import percent_text, render_whatif, report_path, slug, summary_lines


def test_whatif_public_aliases_are_the_private_objects():
    assert decision_config.blend_portfolio is decision_config._blend
    assert decision_config.check_full is decision_config._check_full
    assert decision_config.SUM_TOLERANCE == decision_config._EPS == 1e-9
    for name in (
        "pct",
        "signed",
        "portfolio_section",
        "return_section",
        "window_section",
        "scenario_section",
        "withdrawal_section",
        "year_one_section",
        "switching_note",
    ):
        assert getattr(decision_report, name) is getattr(decision_report, f"_{name}")
    for const in ("DOTCOM_PROXY_NOTE", "KNOWN_GAP_NOTE", "DRAWDOWN_NOTE"):
        assert isinstance(getattr(decision_report, const), str)


VALID = ["A", "B", "G", "CASH", "AG", "TCASH"]


def test_parse_mix_keeps_order_and_drops_zero_shares():
    assert parse_mix("G=0.5, A=0.5 ,CASH=0", VALID) == [("G", 0.5), ("A", 0.5)]


def test_parse_mix_accepts_a_sum_within_the_loader_tolerance():
    assert parse_mix("A=0.5,CASH=0.5000000005", VALID) == [("A", 0.5), ("CASH", 0.5000000005)]


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (None, "--mix is required"),
        ("", "--mix is required"),
        ("   ", "--mix is required"),
        ("A", "NAME=SHARE"),
        ("A=", "NAME=SHARE"),
        ("=1", "NAME=SHARE"),
        ("A=1,", "NAME=SHARE"),
        ("A=0.5=0.5", "NAME=SHARE"),
        ("A=abc,CASH=1", "not a number"),
        ("A=nan,CASH=1", "finite"),
        ("A=inf", "finite"),
        ("A=-0.5,CASH=1.5", "finite number >= 0"),
        ("A=0.5,A=0.5", "repeated"),
        ("A=1,A=0", "repeated"),
        ("A=0.5,Z=0.5", "unknown mix name"),
        ("Z=0,A=1", "unknown mix name"),
        ("A=0.5,CASH=0.4", "sum"),
        ("A=0.5,CASH=0.500000002", "sum"),
    ],
)
def test_parse_mix_refuses(text, match):
    with pytest.raises(ValueError, match=match):
        parse_mix(text, VALID)


def test_parse_mix_unknown_name_lists_the_valid_ones():
    with pytest.raises(ValueError, match="valid names: A, B, G, CASH, AG, TCASH"):
        parse_mix("Z=1", VALID)


def test_parse_rate():
    assert parse_rate(None) is None
    assert parse_rate("0.045") == 0.045
    assert parse_rate("0.1") == 0.1


@pytest.mark.parametrize("text", ["x", "0", "-0.01", "0.1000001", "nan", "inf"])
def test_parse_rate_refuses(text):
    with pytest.raises(ValueError, match="--rate"):
        parse_rate(text)


@pytest.fixture(scope="module")
def shipped():
    return load_decision_config(ROOT / "config" / "decision.yaml", CANDIDATES, stress_cfg(), END)


def _same_states(a, b):
    sa, sb = portfolio_states(a), portfolio_states(b)
    assert sa.keys() == sb.keys()
    for state in sa:
        assert sa[state] == pytest.approx(sb[state])


def test_split_shares_renormalises_the_non_cash_part():
    noncash, tcash = split_shares([("G", 0.5), ("A", 0.3), ("TCASH", 0.2)])
    assert tcash == 0.2
    assert [n for n, _ in noncash] == ["G", "A"]
    assert noncash[0][1] == pytest.approx(0.625)
    assert sum(s for _, s in noncash) == pytest.approx(1.0, abs=1e-15)


def test_split_shares_without_tcash_and_with_only_tcash():
    assert split_shares([("A", 0.8), ("CASH", 0.2)]) == ([("A", 0.8), ("CASH", 0.2)], 0.0)
    assert split_shares([("TCASH", 1.0)]) == ([], 1.0)


def test_split_shares_clamps_tcash_within_the_sum_tolerance():
    # parse_mix accepts a sum up to 1e-9 above 1; the cash row must still get share 1
    assert parse_mix("TCASH=1.0000000005", VALID) == [("TCASH", 1.0000000005)]
    assert split_shares([("TCASH", 1.0000000005)]) == ([], 1.0)


def test_mix_portfolio_is_the_loaders_blend(shipped):
    mix = mix_portfolio([("A", 0.8), ("CASH", 0.2)], shipped)
    ref = {p.id: p for p in shipped.portfolios}["A80-CASH20"]
    assert mix.id == "MIX"
    assert mix.parts == ref.parts


def test_mix_portfolio_flattens_a_blend_ingredient(shipped):
    mix = mix_portfolio([("AG", 1.0)], shipped)
    assert [(c.id, s) for c, s in mix.parts] == [("A", 0.5), ("G", 0.5)]


def test_mix_portfolio_merges_duplicate_candidates(shipped):
    merged = mix_portfolio([("A", 0.3), ("AG", 0.7)], shipped)
    alone = mix_portfolio([("A", 0.65), ("G", 0.35)], shipped)
    assert [c.id for c, _ in merged.parts] == ["A", "G"]
    assert len(portfolio_states(merged)) == 2  # no state pairs A with itself
    _same_states(merged, alone)


def test_two_switching_ingredients_give_four_states(shipped):
    assert len(portfolio_states(mix_portfolio([("A", 0.5), ("B", 0.5)], shipped))) == 4


def test_mix_portfolio_is_fully_invested_in_every_state(shipped):
    mix = mix_portfolio([("G", 0.5), ("A", 0.3), ("BONDS", 0.2)], shipped)
    for weights in portfolio_states(mix).values():
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)


def test_mix_portfolio_is_none_without_a_non_cash_part(shipped):
    assert mix_portfolio([], shipped) is None


IDS = {"A", "CASH", "MIX"}


def test_cash_row_over_the_mix(shipped):
    row = mix_cash_row(shipped, 0.2, "MIX", IDS)
    assert (row.id, row.base, row.cash_share, row.real_yield, row.pair) == (
        "MIX-TCASH",
        "MIX",
        0.2,
        0.01,
        None,
    )


def test_cash_row_allows_one_hundred_percent_over_cash(shipped):
    row = mix_cash_row(shipped, 1.0, "CASH", {"A", "CASH"})
    assert (row.base, row.cash_share) == ("CASH", 1.0)
    assert row.label == "100% true cash (assumption)"


def test_cash_row_label_over_the_mix(shipped):
    assert mix_cash_row(shipped, 0.2, "MIX", IDS).label == "80% MIX + 20% cash (assumption)"


def test_cash_row_is_none_without_tcash(shipped):
    assert mix_cash_row(shipped, 0.0, "MIX", IDS) is None


def _with_yields(cfg, second):
    rows = list(cfg.cash_assumptions)
    rows[1] = replace(rows[1], real_yield=second)
    return replace(cfg, cash_assumptions=tuple(rows))


@pytest.mark.parametrize("tcash", [0.0, 0.2])
def test_cash_row_refuses_rows_with_different_yields(shipped, tcash):
    with pytest.raises(ValueError, match="different real_yield"):
        mix_cash_row(_with_yields(shipped, 0.02), tcash, "MIX", IDS)


def test_cash_row_refuses_a_yield_beyond_the_bound(shipped):
    rows = tuple(replace(r, real_yield=0.06) for r in shipped.cash_assumptions)
    with pytest.raises(ValueError, match="real_yield"):
        mix_cash_row(replace(shipped, cash_assumptions=rows), 0.2, "MIX", IDS)


def test_cash_row_needs_a_yield_in_the_config(shipped):
    bare = replace(shipped, cash_assumptions=())
    assert mix_cash_row(bare, 0.0, "MIX", IDS) is None
    with pytest.raises(ValueError, match="no cash_assumptions"):
        mix_cash_row(bare, 0.2, "MIX", IDS)


def test_cash_row_checks_base_id_and_share(shipped):
    with pytest.raises(ValueError, match="base 'MIX'"):
        mix_cash_row(shipped, 0.2, "MIX", {"A", "CASH"})
    with pytest.raises(ValueError, match="already a portfolio id"):
        mix_cash_row(shipped, 0.2, "MIX", {*IDS, "MIX-TCASH"})
    with pytest.raises(ValueError, match="cash_share"):
        mix_cash_row(shipped, 1.5, "MIX", IDS)


def test_valid_names_are_the_portfolio_ids_plus_tcash(shipped):
    names = valid_names(shipped)
    assert names[:7] == list("ABCDEFG")
    assert "A80-CASH20" in names
    assert names[-1] == "TCASH"


def test_mix_config_holds_a_cash_mix_and_the_report_rates(shipped):
    cfg = mix_config(shipped, [("A", 0.8), ("CASH", 0.2)], None)
    assert [p.id for p in cfg.portfolios] == ["A", "CASH", "MIX"]
    assert cfg.cash_assumptions == ()
    assert cfg.rates == shipped.rates


def test_mix_config_with_tcash_adds_one_row_over_mix(shipped):
    cfg = mix_config(shipped, [("G", 0.5), ("A", 0.3), ("TCASH", 0.2)], None)
    assert [p.id for p in cfg.portfolios] == ["A", "CASH", "MIX"]
    (row,) = cfg.cash_assumptions
    assert (row.id, row.base, row.cash_share, row.real_yield) == ("MIX-TCASH", "MIX", 0.2, 0.01)


def test_mix_config_all_tcash_has_no_mix_portfolio(shipped):
    cfg = mix_config(shipped, [("TCASH", 1.0)], None)
    assert [p.id for p in cfg.portfolios] == ["A", "CASH"]
    (row,) = cfg.cash_assumptions
    assert (row.base, row.cash_share) == ("CASH", 1.0)


def test_mix_config_tcash_just_above_one_is_clamped(shipped):
    cfg = mix_config(shipped, [("TCASH", 1.0000000005)], None)
    assert cfg.cash_assumptions[0].cash_share == 1.0


def test_mix_config_keeps_everything_else_and_does_not_mutate(shipped):
    cfg = mix_config(shipped, [("A", 1.0)], None)
    for field in ("windows", "scenarios", "start_years", "proxied_threshold", "sha256"):
        assert getattr(cfg, field) == getattr(shipped, field)
    assert cfg.candidates_sha256 == shipped.candidates_sha256
    assert len(shipped.portfolios) == 27


def test_merge_rate_adds_once_and_sorted():
    assert merge_rate([0.02, 0.04], None) == [0.02, 0.04]
    assert merge_rate([0.02, 0.04], 0.04) == [0.02, 0.04]
    assert merge_rate([0.02, 0.04], 0.03) == [0.02, 0.03, 0.04]


def test_mix_config_merges_the_extra_rate(shipped):
    assert mix_config(shipped, [("A", 1.0)], 0.045).rates == [0.02, 0.033, 0.04, 0.045, 0.05]
    assert mix_config(shipped, [("A", 1.0)], 0.04).rates == shipped.rates


GIVEN = [("A", 0.8), ("TCASH", 0.2)]


@pytest.fixture(scope="module")
def report(shipped):
    cfg = replace(mix_config(shipped, GIVEN, None), start_years=[2005, 2006], rates=[0.04])
    return run_decision(cfg, prices(), cpi(), criteria(), "cd" * 32)


def test_slug_rule():
    assert slug([("G", 0.5), ("A", 0.3), ("TCASH", 0.2)]) == "G.50__A.30__TCASH.20"
    assert slug([("A", 1 / 3), ("CASH", 2 / 3)]) == "A.33p33__CASH.66p67"
    assert slug([("TCASH", 1.0)]) == "TCASH.100"
    assert percent_text(0.12345) == "12p35"


def test_report_path_stays_under_reports(tmp_path):
    reports = tmp_path / "reports"
    assert report_path(reports, "A.100") == (reports / "whatif-A.100.md").resolve()
    with pytest.raises(ValueError, match="outside"):
        report_path(reports, "/../../x")


def test_render_has_its_own_header_and_the_reused_sections(report):
    md = render_whatif(report, GIVEN)
    assert md.startswith("# What-if mix")
    assert "not from `config/decision.yaml`" in md
    assert "mix as given: A 80%, TCASH 20%" in md
    assert "MIX (the non-cash part, renormalised to 100%): A 100%" in md
    assert f"decision.yaml sha256: `{report['decision_sha256']}`" in md
    assert f"stress.yaml sha256: `{'cd' * 32}`" in md
    for heading in (
        "## Portfolios (100% of capital)",
        "## Research-period return",
        "## Historical windows",
        "## Judgement-based scenarios",
        "## Withdrawals",
        "## Year-one scenario hit",
    ):
        assert heading in md
    assert "| MIX-TCASH |" in md
    assert "multiple comparisons" not in md
    assert "A80-CASH20" not in md
    assert "SHY caveat above" not in md
    assert decision_report.DOTCOM_PROXY_NOTE in md
    assert decision_report.DRAWDOWN_NOTE in md
    assert decision_report.KNOWN_GAP_NOTE in md
    assert "$" not in md


def test_render_tcash_note_and_row_scope(report):
    md = render_whatif(report, GIVEN)
    assert "are the non-cash part at 100%" in md
    assert "only as `MIX-TCASH`" in md
    windows = md.split("## Historical windows")[1].split("## Judgement-based scenarios")[0]
    assert "MIX-TCASH" not in windows
    assert "It follows unadjusted CPI" in md


def test_render_without_tcash_has_no_tcash_note(report):
    md = render_whatif(report, [("A", 0.8), ("CASH", 0.2)])
    assert "only as `MIX-TCASH`" not in md
    assert "TCASH share" not in md


def test_render_is_deterministic(report):
    assert render_whatif(report, GIVEN) == render_whatif(report, GIVEN)


def test_summary_lines_print_only_rows_that_exist(report, tmp_path):
    lines = summary_lines(report, GIVEN, tmp_path / "x.md")
    assert lines[0] == "mix: A 80%, TCASH 20%"
    assert lines[1] == f"wrote: {tmp_path / 'x.md'}"
    assert [line.split(":")[0] for line in lines[2:]] == ["MIX", "MIX-TCASH", "A", "CASH"]
    assert all("CAGR" in line and "max drawdown" in line for line in lines[2:])


def test_whatif_pixi_task():
    tasks = tomllib.loads((ROOT / "pixi.toml").read_text())["tasks"]
    assert tasks["whatif"] == "python scripts/whatif.py"


def _load_whatif():
    spec = importlib.util.spec_from_file_location("whatif_cli", ROOT / "scripts" / "whatif.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def run(tmp_path, monkeypatch):
    """The CLI with synthetic data, two start years and reports under tmp_path.
    Loaded here, not at import, so collecting this file never needs the script."""
    cli = _load_whatif()
    real = cli.load_decision_config

    def quick(*args, **kwargs):
        return replace(real(*args, **kwargs), start_years=[2005, 2006])

    monkeypatch.setattr(cli, "load_decision_config", quick)
    monkeypatch.setattr(cli, "load_ohlcv", _fake_ohlcv())
    monkeypatch.setattr(cli, "load_macro", _fake_macro(cpi()))
    monkeypatch.setattr(cli, "REPORTS", tmp_path / "reports")
    return cli


def test_whatif_main_writes_only_under_reports(run, tmp_path, capsys):
    assert run.main(["--mix", "A=0.8,TCASH=0.2"]) == 0
    out = tmp_path / "reports" / "whatif-A.80__TCASH.20.md"
    assert list((tmp_path / "reports").iterdir()) == [out]
    md = out.read_text()
    assert "| MIX-TCASH |" in md
    printed = capsys.readouterr().out
    assert f"wrote: {out}" in printed
    assert "MIX-TCASH: CAGR" in printed
    assert "## Withdrawals" not in printed  # a summary, not the whole report


def test_whatif_main_extra_rate_is_in_the_report(run, tmp_path):
    assert run.main(["--mix", "A=0.8,CASH=0.2", "--rate", "0.045"]) == 0
    md = (tmp_path / "reports" / "whatif-A.80__CASH.20.md").read_text()
    assert "### Withdrawal rate 4.5% per year" in md


def test_whatif_main_tcash_zero_has_no_cash_row(run, capsys):
    assert run.main(["--mix", "A=0.8,CASH=0.2"]) == 0
    printed = capsys.readouterr().out
    assert "MIX: CAGR" in printed
    assert "MIX-TCASH" not in printed


@pytest.mark.parametrize(
    ("args", "match"),
    [
        ([], "--mix is required"),
        (["--mix", ""], "--mix is required"),
        (["--mix", "A"], "NAME=SHARE"),
        (["--mix", "A=x"], "not a number"),
        (["--mix", "A=-1,CASH=2"], "finite number"),
        (["--mix", "A=0.5,A=0.5"], "repeated"),
        (["--mix", "Z=1"], "unknown mix name"),
        (["--mix", "A=0.5,CASH=0.4"], "sum"),
        (["--mix", "A=1", "--rate", "x"], "not a number"),
        (["--mix", "A=1", "--rate", "0.11"], "--rate"),
        (["--mix", "A=1", "--rate", "0"], "--rate"),
    ],
)
def test_whatif_main_refuses_a_bad_input(run, tmp_path, capsys, args, match):
    assert run.main(args) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("refused: ")
    assert match in printed
    assert not (tmp_path / "reports").exists()


def test_whatif_main_refuses_cash_rows_with_different_yields(run, tmp_path, monkeypatch, capsys):
    real = run.load_decision_config

    def odd(*args, **kwargs):
        cfg = real(*args, **kwargs)
        rows = list(cfg.cash_assumptions)
        rows[1] = replace(rows[1], real_yield=0.02)
        return replace(cfg, cash_assumptions=tuple(rows))

    monkeypatch.setattr(run, "load_decision_config", odd)
    assert run.main(["--mix", "A=0.8,TCASH=0.2"]) == 1
    assert "different real_yield" in capsys.readouterr().out
    assert not (tmp_path / "reports").exists()


def test_whatif_main_refuses_a_failed_config_load(run, tmp_path, monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise ValueError("decision broken")

    monkeypatch.setattr(run, "load_decision_config", boom)
    assert run.main(["--mix", "A=1"]) == 1
    assert capsys.readouterr().out == "refused: decision broken\n"
    assert not (tmp_path / "reports").exists()


def test_whatif_main_refuses_a_missing_ticker(run, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run, "load_ohlcv", _fake_ohlcv(drop="RSP"))
    assert run.main(["--mix", "RSP=1"]) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("refused: ")
    assert "RSP" in printed
    assert not (tmp_path / "reports").exists()


def test_whatif_main_refuses_an_unpriced_held_fund(run, tmp_path, monkeypatch, capsys):
    fake = _fake_ohlcv()

    def holes(tickers, refresh=False, cache_dir=None):
        data = fake(tickers, refresh=refresh, cache_dir=cache_dir)
        close = data["close"]
        close.loc[close.index[close.index >= "2005-01-01"][0], "TLT"] = float("nan")
        return data

    monkeypatch.setattr(run, "load_ohlcv", holes)
    assert run.main(["--mix", "TLT=1"]) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("refused: ")
    assert "unpriced at the start" in printed
    assert not (tmp_path / "reports").exists()


def test_whatif_main_refuses_when_loading_criteria_fails(run, tmp_path, monkeypatch, capsys):
    def boom(path):
        raise ValueError("criteria broken")

    monkeypatch.setattr(run, "load_criteria", boom)
    assert run.main(["--mix", "A=1"]) == 1
    assert capsys.readouterr().out == "refused: criteria broken\n"
    assert not (tmp_path / "reports").exists()


def test_whatif_main_refuses_when_a_download_fails(run, tmp_path, monkeypatch, capsys):
    def boom(**kwargs):
        raise RuntimeError("Failed to fetch X")

    monkeypatch.setattr(run, "load_macro", boom)
    assert run.main(["--mix", "A=1"]) == 1
    assert capsys.readouterr().out.startswith("refused: ")
    assert not (tmp_path / "reports").exists()


def test_whatif_main_refuses_missing_cpi(run, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run, "load_macro", _fake_macro(cpi().loc[:"2005-06-30"]))
    assert run.main(["--mix", "A=0.8,TCASH=0.2"]) == 1
    printed = capsys.readouterr().out
    assert "refused" in printed
    assert "missing CPI" in printed
    assert not (tmp_path / "reports").exists()
