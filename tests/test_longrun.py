import hashlib

import numpy as np
import pandas as pd
import pytest

from qrl.longrun import LongrunConfig, load_longrun_config

DEC_SHA = "d" * 64


def _write(tmp_path, text):
    p = tmp_path / "longrun.yaml"
    p.write_text(text, encoding="utf-8")
    return p


GOOD = f"""version: 1
decision_sha256: "{DEC_SHA}"
seed: 7
n_paths: 50
block_months: 12
horizon_years: 30
real_floor: 0.5
withdrawal_rates: [0.02, 0.05]
cash_real_yield: 0.01
"""


def test_load_longrun_config_reads_every_key_and_hashes_the_file(tmp_path):
    path = _write(tmp_path, GOOD)
    cfg = load_longrun_config(path, DEC_SHA)
    assert cfg == LongrunConfig(
        seed=7,
        n_paths=50,
        block_months=12,
        horizon_years=30,
        real_floor=0.5,
        rates=[0.02, 0.05],
        cash_real_yield=0.01,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_load_longrun_config_refuses_a_changed_decision_yaml(tmp_path):
    with pytest.raises(ValueError, match="decision.yaml"):
        load_longrun_config(_write(tmp_path, GOOD), "e" * 64)


def test_load_longrun_config_refuses_a_missing_key(tmp_path):
    with pytest.raises(ValueError, match="seed"):
        load_longrun_config(_write(tmp_path, GOOD.replace("seed: 7\n", "")), DEC_SHA)


def test_load_longrun_config_refuses_a_horizon_not_made_of_whole_blocks(tmp_path):
    text = GOOD.replace("block_months: 12", "block_months: 7")
    with pytest.raises(ValueError, match="block"):
        load_longrun_config(_write(tmp_path, text), DEC_SHA)


def test_load_longrun_config_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="cannot be loaded"):
        load_longrun_config(tmp_path / "nope.yaml", DEC_SHA)


def test_load_longrun_config_refuses_malformed_yaml(tmp_path):
    with pytest.raises(ValueError, match="cannot be loaded"):
        load_longrun_config(_write(tmp_path, "version: [1\n"), DEC_SHA)
