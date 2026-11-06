"""scripts/rebalance.py wiring (IO only) and its pixi task/environment."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from contextlib import nullcontext
from pathlib import Path

import pytest

from qrl.broker import FakeBroker
from qrl.broker_config import BrokerConfig

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "rebalance_cli", ROOT / "scripts" / "rebalance.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()


def test_rebalance_task_lives_in_the_broker_environment_only():
    config = tomllib.loads((ROOT / "pixi.toml").read_text(encoding="utf-8"))
    assert config["feature"]["broker"]["tasks"]["rebalance"] == "python scripts/rebalance.py"
    assert "rebalance" not in config["tasks"]
    envs = config["environments"]
    assert "broker" in envs["broker"]["features"]
    for name in ("default", "dev", "ci"):
        assert "broker" not in envs[name].get("features", [])


def test_flatten_and_accept_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        cli._build_arg_parser().parse_args(["--flatten", "--accept-positions"])


def test_missing_adapter_exits_with_a_clear_message(monkeypatch):
    monkeypatch.setitem(sys.modules, "qrl.broker_ib", None)
    with pytest.raises(SystemExit, match="IB adapter unavailable"):
        cli._open_broker(BrokerConfig(True, "h", 4002, 1, "DU1"))


def test_main_wires_a_run_and_returns_its_exit_code(tmp_path, monkeypatch, capsys):
    disabled = BrokerConfig(False, "127.0.0.1", 4002, 17, "DU123")
    monkeypatch.setattr(cli, "load_broker_config", lambda path: disabled)
    monkeypatch.setattr(cli, "_open_broker", lambda cfg: nullcontext(FakeBroker()))
    assert cli.main(["--journal-dir", str(tmp_path)]) == 1
    (event,) = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert "disabled" in event["detail"]
    assert "refused: disabled" in capsys.readouterr().out


class _RefusingBroker:
    def __enter__(self):
        raise ConnectionRefusedError("refused")

    def __exit__(self, *exc_info):
        raise AssertionError("never entered")


def test_main_records_a_gateway_connection_failure_and_exits_1(tmp_path, monkeypatch, capsys):
    config = BrokerConfig(True, "10.0.0.5", 4002, 17, "DU123")
    monkeypatch.setattr(cli, "load_broker_config", lambda path: config)
    monkeypatch.setattr(cli, "_open_broker", lambda cfg: _RefusingBroker())
    assert cli.main(["--journal-dir", str(tmp_path)]) == 1
    (event,) = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert event["status"] == "error"
    assert "could not connect to IB gateway at 10.0.0.5:4002" in event["detail"]
    assert "refused" in event["detail"]
    assert "could not connect" in capsys.readouterr().out


def _events(tmp_path):
    return [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]


def test_a_config_load_failure_is_an_error_event_not_a_traceback(tmp_path, monkeypatch, capsys):
    def boom(path):
        raise ValueError("port 4001 is a live port")

    monkeypatch.setattr(cli, "load_broker_config", boom)
    monkeypatch.setattr(cli, "_open_broker", lambda cfg: pytest.fail("must not connect"))
    assert cli.main(["--journal-dir", str(tmp_path)]) == 1
    (event,) = _events(tmp_path)
    assert event["status"] == "error"
    assert "could not load the configuration" in event["detail"]
    assert "live port" in event["detail"]
    assert "could not load" in capsys.readouterr().out


def test_a_disabled_evening_run_never_builds_the_broker(tmp_path, monkeypatch, capsys):
    disabled = BrokerConfig(False, "127.0.0.1", 4002, 17, "DU123")
    monkeypatch.setattr(cli, "load_broker_config", lambda path: disabled)
    monkeypatch.setattr(cli, "_open_broker", lambda cfg: pytest.fail("must not connect"))
    assert cli.main(["--journal-dir", str(tmp_path)]) == 1
    (event,) = _events(tmp_path)
    assert (event["status"], "disabled" in event["detail"]) == ("refused", True)
    assert "refused: disabled" in capsys.readouterr().out


def test_the_adapters_paper_only_refusal_is_logged_as_a_refusal(tmp_path, monkeypatch, capsys):
    config = BrokerConfig(True, "127.0.0.1", 4002, 17, "DU123")

    def refuse(cfg):
        raise ValueError("IbBroker is paper only: port 4001 refused")

    monkeypatch.setattr(cli, "load_broker_config", lambda path: config)
    monkeypatch.setattr(cli, "_open_broker", refuse)
    assert cli.main(["--journal-dir", str(tmp_path)]) == 1
    (event,) = _events(tmp_path)
    assert event["status"] == "refused"
    assert "paper only" in event["detail"]
    assert "could not connect" not in event["detail"]
    assert "refused: IbBroker is paper only" in capsys.readouterr().out


def test_main_flatten_works_while_disabled(tmp_path, monkeypatch):
    # FakeBroker reports account DU123 on port 4002, which the connection check compares.
    disabled = BrokerConfig(False, "127.0.0.1", 4002, 17, "DU123")
    monkeypatch.setattr(cli, "load_broker_config", lambda path: disabled)
    monkeypatch.setattr(cli, "_open_broker", lambda cfg: nullcontext(FakeBroker()))
    assert cli.main(["--flatten", "--journal-dir", str(tmp_path)]) == 0


def test_main_dispatches_accept_positions_and_journals_it(tmp_path, monkeypatch):
    config = BrokerConfig(True, "127.0.0.1", 4002, 17, "DU123")
    monkeypatch.setattr(cli, "load_broker_config", lambda path: config)
    monkeypatch.setattr(cli, "_open_broker", lambda cfg: nullcontext(FakeBroker()))
    assert cli.main(["--accept-positions", "--journal-dir", str(tmp_path)]) == 0
    (journal,) = tmp_path.glob("*-accept-*.json")
    assert json.loads(journal.read_text())["kind"] == "accept"
