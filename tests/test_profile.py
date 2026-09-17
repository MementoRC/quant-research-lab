import copy
import sys
from pathlib import Path

import pytest
import yaml

from qrl.criteria import load_criteria
from qrl.profile import analyze_profile, load_profile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from profile_check import main  # noqa: E402


@pytest.fixture
def example_profile() -> dict:
    return load_profile(ROOT / "config" / "profile.yaml")


@pytest.fixture
def criteria() -> dict:
    crit, _ = load_criteria(ROOT / "config" / "criteria.yaml")
    return crit


def test_example_profile_has_no_conflicts(example_profile, criteria):
    report = analyze_profile(example_profile, criteria)
    assert report.ok
    assert report.conflicts == []
    assert report.implications


def test_intraday_with_free_data_is_flagged(example_profile, criteria):
    profile = copy.deepcopy(example_profile)
    profile["overnight_holds"] = False
    report = analyze_profile(profile, criteria)
    assert not report.ok
    assert any("intraday" in c.lower() for c in report.conflicts)


def test_capital_split_not_summing_to_one_is_flagged(example_profile, criteria):
    profile = copy.deepcopy(example_profile)
    profile["capital_split"] = {"core": 0.80, "sleeve": 0.30}
    report = analyze_profile(profile, criteria)
    assert not report.ok
    assert any("sum to 1" in c for c in report.conflicts)


def test_max_drawdown_tighter_than_criteria_is_flagged(example_profile, criteria):
    profile = copy.deepcopy(example_profile)
    profile["max_drawdown"] = criteria["pass"]["max_drawdown"] - 0.10
    report = analyze_profile(profile, criteria)
    assert not report.ok
    assert any("tighter than criteria" in c for c in report.conflicts)


def test_holding_period_min_greater_than_max_is_flagged(example_profile, criteria):
    profile = copy.deepcopy(example_profile)
    profile["holding_period_days"] = {"min": 20, "max": 5}
    report = analyze_profile(profile, criteria)
    assert not report.ok
    assert any("min must be <=" in c for c in report.conflicts)


def test_bad_goal_enum_raises_value_error(example_profile, tmp_path):
    profile = copy.deepcopy(example_profile)
    profile["goal"] = "moonshot"
    bad_path = tmp_path / "profile.yaml"
    bad_path.write_text(yaml.safe_dump(profile))
    with pytest.raises(ValueError, match="goal"):
        load_profile(bad_path)


def test_cli_exits_nonzero_on_conflicting_profile(example_profile, tmp_path, capsys):
    profile = copy.deepcopy(example_profile)
    profile["capital_split"] = {"core": 0.80, "sleeve": 0.30}
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(yaml.safe_dump(profile))

    exit_code = main(
        [
            "--profile",
            str(profile_path),
            "--criteria",
            str(ROOT / "config" / "criteria.yaml"),
        ]
    )
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "Conflicts" in out


def test_cli_exits_zero_on_example_profile():
    exit_code = main(
        [
            "--profile",
            str(ROOT / "config" / "profile.yaml"),
            "--criteria",
            str(ROOT / "config" / "criteria.yaml"),
        ]
    )
    assert exit_code == 0
