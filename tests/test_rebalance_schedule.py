"""The shipped systemd units for the paper rebalance: weekdays 18:00 Chicago,
never replayed after a missed run, and running the broker environment."""

from __future__ import annotations

import configparser
from pathlib import Path

UNITS = Path(__file__).resolve().parents[1] / "deploy" / "systemd"


def _read(name: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str  # type: ignore[assignment,method-assign]  # keep key case
    parser.read(UNITS / name)
    return parser


def test_timer_fires_weekdays_at_18_chicago_and_never_replays():
    timer = _read("qrl-rebalance.timer")["Timer"]
    assert timer["OnCalendar"] == "Mon..Fri 18:00 America/Chicago"
    assert timer["Persistent"] == "false"


def test_service_runs_the_broker_rebalance_once():
    service = _read("qrl-rebalance.service")["Service"]
    assert service["Type"] == "oneshot"
    assert "-e broker rebalance" in service["ExecStart"]
    assert "--flatten" not in service["ExecStart"]
