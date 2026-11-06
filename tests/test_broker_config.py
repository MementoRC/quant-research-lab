"""Tests for qrl.broker_config (spec: broker-rebalancer.md, "Components")."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from qrl.broker_config import BrokerConfig, is_paper_account_id, load_broker_config

ROOT = Path(__file__).resolve().parents[1]
BASE = {
    "enabled": True,
    "host": "127.0.0.1",
    "port": 4002,
    "client_id": 17,
    "account_id": "DU123",
}


def _write(tmp_path: Path, **changes: object) -> Path:
    doc = {**BASE, **changes}
    doc = {k: v for k, v in doc.items() if v is not None}
    path = tmp_path / "broker.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("value", "expected"),
    [("DU123", True), ("DU1", True), ("DU", False), ("du123", False), (" DU1", False)]
    + [("U1234567", False), ("", False), (None, False), (123, False)],
)
def test_is_paper_account_id(value, expected):
    assert is_paper_account_id(value) is expected


def test_shipped_config_loads_disabled_with_defaults():
    cfg = load_broker_config(ROOT / "config" / "broker.yaml")
    assert cfg.enabled is False
    assert cfg.port == 4002
    assert cfg.account_id.startswith("DU")
    assert (cfg.cash_buffer, cfg.deadband) == (0.01, 0.005)


def test_defaults_apply_when_omitted(tmp_path):
    assert load_broker_config(_write(tmp_path)) == BrokerConfig(
        True, "127.0.0.1", 4002, 17, "DU123", 0.01, 0.005
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [("cash_buffer", 0.0), ("cash_buffer", 0.10), ("deadband", 0), ("deadband", 0.05)],
)
def test_range_bounds_are_inclusive(tmp_path, key, value):
    assert getattr(load_broker_config(_write(tmp_path, **{key: value})), key) == value


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("cash_buffer", 0.11),
        ("cash_buffer", -0.01),
        ("deadband", 0.051),
        ("deadband", -0.001),
        ("client_id", -1),
        ("port", 0),
    ],
)
def test_out_of_range_is_refused(tmp_path, key, value):
    with pytest.raises(ValueError, match=key):
        load_broker_config(_write(tmp_path, **{key: value}))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("enabled", "yes"),
        ("host", 5),
        ("port", "4002"),
        ("client_id", 1.5),
        ("client_id", True),
        ("account_id", ""),
        ("cash_buffer", True),
        ("deadband", "0.005"),
    ],
)
def test_wrong_types_are_refused(tmp_path, key, value):
    with pytest.raises(ValueError, match=key):
        load_broker_config(_write(tmp_path, **{key: value}))


@pytest.mark.parametrize(
    ("key", "value"),
    [("port", 4001), ("port", 7496), ("account_id", "U1234567"), ("account_id", "du123")],
)
def test_live_port_and_non_paper_account_are_refused(tmp_path, key, value):
    with pytest.raises(ValueError, match=key):
        load_broker_config(_write(tmp_path, **{key: value}))


def test_unknown_key_is_refused(tmp_path):
    with pytest.raises(ValueError, match=r"unknown key.*'live'"):
        load_broker_config(_write(tmp_path, live=True))


@pytest.mark.parametrize("key", sorted(BASE))
def test_missing_key_is_refused(tmp_path, key):
    doc = {k: v for k, v in BASE.items() if k != key}
    path = tmp_path / "broker.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(ValueError, match=rf"missing key.*'{key}'"):
        load_broker_config(path)


def test_non_mapping_is_refused(tmp_path):
    path = tmp_path / "broker.yaml"
    path.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_broker_config(path)
