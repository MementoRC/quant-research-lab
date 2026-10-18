"""What-if shock (spec: docs/methodology/whatif-shock.md): qrl.shock and its three
public aliases. Offline: the shipped config/decision.yaml plus synthetic prices
and CPI. Existing tests are untouched."""

from __future__ import annotations

import pytest

from qrl import decision, decision_config, decision_report
from qrl.shock import Shock, load_shock


def test_shock_public_aliases_are_the_private_objects():
    assert decision.first_years is decision._first_years
    assert decision_config.ID_PATTERN is decision_config._ID
    assert decision_report.below_peak is decision_report._below_peak


Y1 = {"stocks": -0.30, "gold": 0.20, "long_bonds": -0.15, "short_bonds": 0.01, "inflation": 0.09}
Y2 = {"stocks": -0.10, "gold": 0.10, "long_bonds": -0.10, "short_bonds": 0.02, "inflation": 0.08}


def _year_text(year=None, **override):
    """One YAML flow mapping; an override of None drops that key, a string is
    written raw (so "true", "'x'", ".nan" reach YAML as such)."""
    values = {**(year or Y1), **override}
    return "{" + ", ".join(f"{k}: {v}" for k, v in values.items() if v is not None) + "}"


def _shock_text(*years, name="stagflation-5y"):
    return f"name: {name}\nyears:\n" + "".join(f"  - {y}\n" for y in years)


GOOD_SHOCK = _shock_text(_year_text(Y1), _year_text(Y2))


def _shock_file(tmp_path, text=GOOD_SHOCK):
    path = tmp_path / "shock.yaml"
    path.write_text(text)
    return path


def test_load_shock_reads_a_valid_file(tmp_path):
    shock = load_shock(_shock_file(tmp_path))
    assert shock == Shock("stagflation-5y", (Y1, Y2))
    assert all(isinstance(v, float) for year in shock.years for v in year.values())


def test_load_shock_accepts_the_bounds_and_ten_years(tmp_path):
    text = _shock_text(
        _year_text(stocks=2, gold=-0.999, inflation=-0.1), _year_text(inflation=0.3), name="A_b-9"
    )
    shock = load_shock(_shock_file(tmp_path, text))
    assert shock.years[0]["stocks"] == 2.0
    assert shock.years[1]["inflation"] == 0.3
    ten = _shock_text(*[_year_text()] * 10)
    assert len(load_shock(_shock_file(tmp_path, ten)).years) == 10


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("name: [unclosed\n", "not valid YAML"),
        ("", "must be a mapping"),
        ("- a\n- b\n", "must be a mapping"),
        ("name: x\n", "missing key"),
        (GOOD_SHOCK + "extra: 1\n", "unknown key"),
        (_shock_text(_year_text(), name="bad/name"), "must match"),
        (_shock_text(_year_text(), name="'../x'"), "must match"),
        (_shock_text(_year_text(), name="123"), "must match"),
        ("name: x\nyears: []\n", "1 to 10"),
        ("name: x\nyears: {a: 1}\n", "1 to 10"),
        (_shock_text(*[_year_text()] * 11), "1 to 10"),
        ("name: x\nyears:\n  - [1, 2]\n", "must be a mapping"),
        (_shock_text(_year_text(inflation=None)), "missing key"),
        (_shock_text(_year_text(cash=0.0)), "unknown key"),
        (_shock_text(_year_text(stocks="true")), "not a finite number"),
        (_shock_text(_year_text(stocks="'x'")), "not a finite number"),
        (_shock_text(_year_text(stocks=".nan")), "not a finite number"),
        (_shock_text(_year_text(gold=".inf")), "not a finite number"),
        (_shock_text(_year_text(stocks=-1)), "above -1"),
        (_shock_text(_year_text(short_bonds=-1.5)), "above -1"),
        (_shock_text(_year_text(gold=2.01)), "at most 2"),
        (_shock_text(_year_text(inflation=0.31)), "inflation"),
        (_shock_text(_year_text(inflation=-0.11)), "inflation"),
    ],
)
def test_load_shock_refuses(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        load_shock(_shock_file(tmp_path, text))


def test_load_shock_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="cannot be read"):
        load_shock(tmp_path / "nope.yaml")


def test_load_shock_refuses_an_unreadable_path(tmp_path):
    with pytest.raises(ValueError, match="cannot be read"):
        load_shock(tmp_path)  # a directory
