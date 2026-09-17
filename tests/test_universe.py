import copy
from pathlib import Path

import pytest
import yaml

from qrl.universe import load_universe

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example_universe() -> dict:
    return load_universe(ROOT / "config" / "universe.yaml")


def test_example_universe_loads_and_is_labeled_biased(example_universe):
    assert example_universe["survivorship_biased"] is True
    assert len(example_universe["tickers"]) > 50
    assert len(set(example_universe["tickers"])) == len(example_universe["tickers"])


def test_missing_survivorship_flag_raises(example_universe, tmp_path):
    universe = copy.deepcopy(example_universe)
    del universe["survivorship_biased"]
    path = tmp_path / "universe.yaml"
    path.write_text(yaml.safe_dump(universe))
    with pytest.raises(ValueError, match="survivorship_biased"):
        load_universe(path)


def test_non_bool_survivorship_flag_raises(example_universe, tmp_path):
    universe = copy.deepcopy(example_universe)
    universe["survivorship_biased"] = "true"
    path = tmp_path / "universe.yaml"
    path.write_text(yaml.safe_dump(universe))
    with pytest.raises(ValueError, match="survivorship_biased"):
        load_universe(path)


def test_empty_tickers_raises(example_universe, tmp_path):
    universe = copy.deepcopy(example_universe)
    universe["tickers"] = []
    path = tmp_path / "universe.yaml"
    path.write_text(yaml.safe_dump(universe))
    with pytest.raises(ValueError, match="no tickers"):
        load_universe(path)


def test_duplicate_tickers_raises(example_universe, tmp_path):
    universe = copy.deepcopy(example_universe)
    universe["tickers"] = [*universe["tickers"], universe["tickers"][0]]
    path = tmp_path / "universe.yaml"
    path.write_text(yaml.safe_dump(universe))
    with pytest.raises(ValueError, match="duplicate"):
        load_universe(path)
