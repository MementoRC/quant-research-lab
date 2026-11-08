"""`config/broker.yaml`: settings of the IB paper rebalancer (spec:
docs/methodology/broker-rebalancer.md, "Components"). Not hash-locked;
strictly validated: unknown or missing keys, wrong types and out-of-range
values raise ValueError naming the key.

A gitignored `config/broker.local.yaml` overrides it when present: it holds the
owner's real account, while the committed file keeps placeholders."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

_REQUIRED = frozenset({"enabled", "host", "port", "client_id", "account_id"})
_DEFAULTS: dict[str, float] = {"cash_buffer": 0.01, "deadband": 0.005}
_MAXIMA: dict[str, float] = {"cash_buffer": 0.10, "deadband": 0.05}
LIVE_PORTS = frozenset({4001, 7496})  # IB Gateway and TWS live; paper is 4002 / 7497


def is_paper_account_id(value: object) -> bool:
    """IB paper account ids are "DU" plus digits; exact, case-sensitive, no stripping."""
    return isinstance(value, str) and value.startswith("DU") and len(value) > 2


@dataclass(frozen=True)
class BrokerConfig:
    enabled: bool
    host: str
    port: int
    client_id: int
    account_id: str
    cash_buffer: float = 0.01
    deadband: float = 0.005


def _check_keys(doc: dict[str, object]) -> None:
    missing = sorted(_REQUIRED - doc.keys())
    if missing:
        raise ValueError(f"broker config is missing key(s) {missing}")
    unknown = sorted(str(k) for k in doc.keys() - _REQUIRED - _DEFAULTS.keys())
    if unknown:
        raise ValueError(f"broker config has unknown key(s) {unknown}")


def _text(doc: dict[str, object], key: str) -> str:
    value = doc[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"broker config `{key}` must be a non-empty string, got {value!r}")
    return value


def _int(doc: dict[str, object], key: str, minimum: int) -> int:
    value = doc[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"broker config `{key}` must be an integer, got {value!r}")
    if value < minimum:
        raise ValueError(f"broker config `{key}` must be >= {minimum}, got {value}")
    return value


def _fraction(doc: dict[str, object], key: str) -> float:
    value = doc.get(key, _DEFAULTS[key])
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"broker config `{key}` must be a number, got {value!r}")
    if not 0 <= value <= _MAXIMA[key]:
        raise ValueError(f"broker config `{key}` must be in [0, {_MAXIMA[key]}], got {value}")
    return float(value)


def broker_config_path(root: str | Path) -> Path:
    """`config/broker.local.yaml` under `root` if it exists, else `config/broker.yaml`."""
    local = Path(root) / "config" / "broker.local.yaml"
    return local if local.exists() else Path(root) / "config" / "broker.yaml"


def load_broker_config(path: str | Path) -> BrokerConfig:
    """Parse and validate `config/broker.yaml`."""
    try:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"broker config is not valid YAML ({exc})") from exc
    if not isinstance(doc, dict):
        raise ValueError("broker config must be a mapping")
    _check_keys(doc)
    enabled = doc["enabled"]
    if not isinstance(enabled, bool):
        raise ValueError(f"broker config `enabled` must be true or false, got {enabled!r}")
    port = _int(doc, "port", 1)
    if port in LIVE_PORTS:
        raise ValueError(f"broker config `port` {port} is a live IB port; paper only")
    account_id = _text(doc, "account_id")
    if not is_paper_account_id(account_id):
        raise ValueError(
            f"broker config `account_id` must start with DU (paper), got {account_id!r}"
        )
    return BrokerConfig(
        enabled=enabled,
        host=_text(doc, "host"),
        port=port,
        client_id=_int(doc, "client_id", 0),
        account_id=account_id,
        cash_buffer=_fraction(doc, "cash_buffer"),
        deadband=_fraction(doc, "deadband"),
    )
