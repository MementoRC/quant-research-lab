"""End-to-end evening runs against FakeBroker (spec "Evening run",
"Refusals", "Testing"). Clock, market, broker and journal folder injected."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from qrl.broker import AccountInfo, FakeBroker, Holding, OpenOrder, Order
from qrl.broker_config import BrokerConfig
from qrl.broker_journal import read_journal, write_journal
from qrl.broker_run import RunContext, accept_positions_run, evening_run, flatten_run
from qrl.health import CheckResult, HealthReport
from qrl.live_weights import Market
from qrl.risk import RiskLimits

CFG = BrokerConfig(True, "127.0.0.1", 4002, 17, "DU123", 0.01, 0.005)
LIMITS = RiskLimits(1.0, 1.0, 0.0, 0.04, 30)
EVENING = datetime(2026, 11, 4, 23, 30, tzinfo=UTC)  # 18:30 EST, Wednesday
NEXT_EVENING = datetime(2026, 11, 5, 23, 30, tzinfo=UTC)


def _market(last_day: str = "2026-11-04", ok: bool = True, **weights: float) -> Market:
    index = pd.bdate_range(end=last_day, periods=3)
    close = pd.DataFrame({"QQQ": 500.0, "GLD": 200.0}, index=index)
    w = {"QQQ": 0.8, "GLD": 0.0, **weights}
    combined = pd.DataFrame(w, index=index)
    status = "ok" if ok else "fail"
    health = HealthReport(
        pd.Timestamp(last_day), (CheckResult("data_arrived", status, "stale GLD"),)
    )
    return Market(health, close, combined)


def _ctx(
    root: Path,
    broker: FakeBroker,
    market: Market,
    now: datetime = EVENING,
    cfg: BrokerConfig = CFG,
) -> RunContext:
    return RunContext(
        cfg=cfg,
        broker=broker,
        load_market=lambda today: market,
        limits=LIMITS,
        root=root,
        now=lambda: now,
    )


def _events(root: Path) -> list[dict]:
    path = root / "events.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def _journals(root: Path) -> list[str]:
    return sorted(p.name for p in root.glob("*.json"))


def test_first_run_with_no_journal_submits_and_says_reconcile_was_skipped(tmp_path):
    broker = FakeBroker(cash_usd=100_000.0)
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("submitted", 0)
    assert result.path == tmp_path / "2026-11-04.json"
    journal = json.loads(result.path.read_text())
    assert journal["kind"] == "rebalance"
    assert journal["recorded_at"] == "2026-11-04T23:30:00+00:00"
    assert journal["session_date"] == "2026-11-04"
    assert journal["reconcile"] == {"status": "skipped", "reason": "no previous journal"}
    assert journal["pre_trade_positions"] == {}
    assert journal["submitted"] == [
        {"symbol": "QQQ", "side": "BUY", "shares": 158, "order_id": 1, "status": "submitted"}
    ]
    assert journal["expected_positions"] == {"QQQ": 158}
    assert journal["equity"] == 100_000.0
    assert journal["plan"]["notes"] == []
    assert _events(tmp_path) == []


def test_plan_notes_reach_the_journal_and_the_nothing_to_trade_event(tmp_path, monkeypatch):
    """Buy-cap notes (`Plan.notes`) are recorded, not dropped. `plan` is stubbed."""
    from qrl import broker_run
    from qrl.rebalance import Plan

    note = "buys scaled by 0.9957 to stay within cash"
    buy = Plan((Order("QQQ", "BUY", 158),), equity=100_000.0, notes=(note,))
    monkeypatch.setattr(broker_run, "plan", lambda *args, **kwargs: buy)
    evening_run(_ctx(tmp_path, FakeBroker(cash_usd=100_000.0), _market()))
    assert read_journal(tmp_path / "2026-11-04.json")["plan"]["notes"] == [note]

    idle = Plan(equity=100_000.0, notes=(note,))
    monkeypatch.setattr(broker_run, "plan", lambda *args, **kwargs: idle)
    result = evening_run(_ctx(tmp_path / "idle", FakeBroker(cash_usd=100_000.0), _market()))
    assert result.status == "nothing to trade"
    assert note in _events(tmp_path / "idle")[-1]["detail"]


def _after_first_run(root: Path) -> FakeBroker:
    broker = FakeBroker(cash_usd=100_000.0)
    evening_run(_ctx(root, broker, _market()))
    return broker


def test_next_evening_reconciles_and_has_nothing_to_trade(tmp_path):
    broker = _after_first_run(tmp_path)
    broker.fill_all({"QQQ": 500.0})
    result = evening_run(_ctx(tmp_path, broker, _market("2026-11-05"), NEXT_EVENING))
    assert (result.status, result.exit_code) == ("nothing to trade", 0)
    assert _journals(tmp_path) == ["2026-11-04.json"]
    (event,) = _events(tmp_path)
    assert event["status"] == "nothing to trade"
    assert event["recorded_at"] == "2026-11-05T23:30:00+00:00"


def test_reconcile_mismatch_halts_without_orders(tmp_path):
    broker = _after_first_run(tmp_path)
    broker.pending.clear()
    broker.held = [Holding("QQQ", "STK", "USD", Decimal("150"))]
    for _ in range(2):  # stays halted until --accept-positions
        result = evening_run(_ctx(tmp_path, broker, _market("2026-11-05"), NEXT_EVENING))
        assert (result.status, result.exit_code) == ("reconcile mismatch", 1)
    assert len(broker.submitted) == 1
    assert _journals(tmp_path) == ["2026-11-04.json"]
    assert _events(tmp_path)[-1]["mismatches"] == ["QQQ: expected 158, IB holds 150"]


def test_unreadable_journal_halts_with_a_clear_message(tmp_path):
    broker = FakeBroker(cash_usd=1e5)
    (tmp_path / "2026-11-03.json").write_text("{not json")
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "unreadable journal" in result.detail
    assert _events(tmp_path)[-1]["detail"] == result.detail
    assert broker.submitted == []


def test_rerun_of_a_submitted_session_is_refused_and_leaves_its_journal(tmp_path):
    broker = _after_first_run(tmp_path)
    before = (tmp_path / "2026-11-04.json").read_bytes()
    broker.pending.clear()
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "rerun" in result.detail
    assert (tmp_path / "2026-11-04.json").read_bytes() == before
    assert len(broker.submitted) == 1


def test_open_orders_refuse_the_run(tmp_path):
    broker = _after_first_run(tmp_path)
    result = evening_run(_ctx(tmp_path, broker, _market("2026-11-05"), NEXT_EVENING))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "open order" in result.detail
    assert _events(tmp_path)[-1]["detail"] == result.detail


def test_no_new_session_writes_an_event_and_no_journal(tmp_path):
    earlier = tmp_path / "2026-11-02.json"
    write_journal(
        earlier,
        {"kind": "rebalance", "recorded_at": "2026-11-02T23:30:00+00:00", "expected_positions": {}},
    )
    before = earlier.read_bytes()
    broker = FakeBroker(cash_usd=100_000.0)
    result = evening_run(_ctx(tmp_path, broker, _market("2026-11-03")))
    assert (result.status, result.exit_code) == ("no new session", 0)
    assert _journals(tmp_path) == ["2026-11-02.json"]
    assert earlier.read_bytes() == before
    assert [e["status"] for e in _events(tmp_path)] == ["no new session"]
    assert broker.submitted == []


def test_a_session_after_todays_new_york_date_is_refused(tmp_path):
    broker = FakeBroker(cash_usd=1e5)
    result = evening_run(
        _ctx(tmp_path, broker, _market("2026-11-05"))
    )  # EVENING is 11-04 in New York
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "future bar or clock skew" in result.detail
    assert (broker.submitted, _journals(tmp_path)) == ([], [])


def test_late_evening_utc_next_day_still_trades_the_new_york_session(tmp_path):
    late = datetime(2026, 11, 5, 4, 30, tzinfo=UTC)  # 23:30 EST on 11-04
    result = evening_run(_ctx(tmp_path, FakeBroker(cash_usd=1e5), _market(), late))
    assert result.status == "submitted"


def test_just_after_new_york_midnight_is_no_new_session(tmp_path):
    after = datetime(2026, 11, 5, 5, 30, tzinfo=UTC)  # 00:30 EST on 11-05
    result = evening_run(_ctx(tmp_path, FakeBroker(cash_usd=1e5), _market(), after))
    assert result.status == "no new session"


def _stale_journal(root: Path, day: str) -> None:
    write_journal(
        root / f"{day}.json",
        {"kind": "rebalance", "recorded_at": f"{day}T23:30:00+00:00", "expected_positions": {}},
    )


XYZ = Holding("XYZ", "STK", "USD", Decimal("5"))


def test_step_two_order_rerun_before_unknown_position(tmp_path):
    _stale_journal(tmp_path, "2026-11-04")
    result = evening_run(_ctx(tmp_path, FakeBroker(held=[XYZ]), _market()))
    assert "rerun" in result.detail


def test_step_two_order_no_new_session_before_unknown_position(tmp_path):
    result = evening_run(_ctx(tmp_path, FakeBroker(held=[XYZ]), _market("2026-11-03")))
    assert (result.status, result.exit_code) == ("no new session", 0)


def test_step_two_order_no_new_session_before_rerun(tmp_path):
    _stale_journal(tmp_path, "2026-11-03")
    result = evening_run(_ctx(tmp_path, FakeBroker(), _market("2026-11-03")))
    assert (result.status, result.exit_code) == ("no new session", 0)


def test_late_data_the_evening_after_a_submitted_run_exits_zero_not_rerun(tmp_path):
    broker = _after_first_run(tmp_path)  # submitted for session 2026-11-04
    broker.fill_all({"QQQ": 500.0})
    before = (tmp_path / "2026-11-04.json").read_bytes()
    # Thursday evening, but the vendor still ends at Wednesday's bar.
    result = evening_run(_ctx(tmp_path, broker, _market("2026-11-04"), NEXT_EVENING))
    assert (result.status, result.exit_code) == ("no new session", 0)
    assert "rerun" not in result.detail
    assert (tmp_path / "2026-11-04.json").read_bytes() == before
    assert _journals(tmp_path) == ["2026-11-04.json"]
    assert [e["status"] for e in _events(tmp_path)] == ["no new session"]
    assert len(broker.submitted) == 1


def test_gate_refusal_writes_an_event_and_sends_nothing(tmp_path):
    broker = FakeBroker(cash_usd=1e5)
    result = evening_run(_ctx(tmp_path, broker, _market(), cfg=replace(CFG, enabled=False)))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "disabled" in _events(tmp_path)[0]["detail"]
    assert (broker.submitted, _journals(tmp_path)) == ([], [])


def test_failed_health_checks_refuse(tmp_path):
    result = evening_run(_ctx(tmp_path, FakeBroker(cash_usd=1e5), _market(ok=False)))
    assert result.exit_code == 1
    assert "health checks failed: data_arrived: stale GLD" in result.detail


def test_planner_refusal_sends_nothing(tmp_path):
    broker = FakeBroker(cash_usd=1e5)
    result = evening_run(_ctx(tmp_path, broker, _market(QQQ=0.7, GLD=0.4)))
    assert result.exit_code == 1
    assert "gross exposure" in result.detail
    assert broker.submitted == []


def test_rejected_order_counts_zero_in_expected_positions(tmp_path):
    broker = FakeBroker(cash_usd=1e5, reject=frozenset({"QQQ"}))
    result = evening_run(_ctx(tmp_path, broker, _market()))
    journal = json.loads(result.path.read_text())
    assert journal["submitted"][0]["status"] == "rejected"
    assert journal["expected_positions"] == {}
    assert broker.open_orders() == []
    assert broker.submitted[0].order == Order("QQQ", "BUY", 158)


def test_unknown_position_on_a_current_session_is_refused_without_orders(tmp_path):
    broker = FakeBroker(cash_usd=1e5, held=[XYZ])
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "outside the universe: XYZ" in result.detail
    assert (broker.submitted, _journals(tmp_path)) == ([], [])


def test_unknown_position_check_runs_before_reconcile(tmp_path):
    write_journal(
        tmp_path / "2026-11-03-accept-120000.json",
        {
            "kind": "accept",
            "recorded_at": "2026-11-03T17:00:00+00:00",
            "expected_positions": {"QQQ": 5},
        },
    )
    broker = FakeBroker(cash_usd=1e5, held=[XYZ])  # also mismatches the baseline
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert result.status == "refused"
    assert "outside the universe: XYZ" in result.detail
    assert "mismatches" not in _events(tmp_path)[-1]
    assert broker.submitted == []


def test_stale_unheld_zero_target_symbol_does_not_block_the_run(tmp_path):
    market = _market()  # weights QQQ 0.8, GLD 0.0
    market.close.loc[pd.Timestamp("2026-11-04"), "GLD"] = float("nan")  # GLD one bar behind
    result = evening_run(_ctx(tmp_path, FakeBroker(cash_usd=1e5), market))
    assert result.status == "submitted"
    journal = json.loads(result.path.read_text())
    assert journal["session_date"] == "2026-11-04"
    assert "GLD" not in journal["closes"]


def test_unexpected_exception_is_one_error_event_and_exit_1(tmp_path):
    def broken(today):
        raise RuntimeError("yahoo down")

    ctx = replace(_ctx(tmp_path, FakeBroker(cash_usd=1e5), _market()), load_market=broken)
    result = evening_run(ctx)
    assert (result.status, result.exit_code) == ("error", 1)
    (event,) = _events(tmp_path)
    assert (event["status"], event["detail"]) == ("error", "RuntimeError('yahoo down')")
    assert _journals(tmp_path) == []


def test_cash_lookup_error_is_a_refusal(tmp_path):
    def no_cash() -> float:
        raise LookupError("IB reports no TotalCashValue in USD")

    broker = FakeBroker(cash_usd=1e5)
    broker.cash = no_cash
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "cash unavailable: IB reports no TotalCashValue" in _events(tmp_path)[0]["detail"]
    assert broker.submitted == []


def _fail_submit_on(broker: FakeBroker, symbol: str) -> None:
    real = broker.submit

    def submit(orders: list[Order]):
        if orders[0].symbol == symbol:
            raise RuntimeError("socket closed")
        return real(orders)

    broker.submit = submit


def test_partial_submit_journals_what_was_sent_then_records_the_error(tmp_path):
    # Orders: SELL GLD 100 first, then BUY QQQ 158; the QQQ submit fails.
    broker = FakeBroker(cash_usd=80_000.0, held=[Holding("GLD", "STK", "USD", Decimal("100"))])
    _fail_submit_on(broker, "QQQ")
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("error", 1)
    journal = json.loads((tmp_path / "2026-11-04.json").read_text())
    assert [o["symbol"] for o in journal["submitted"]] == ["GLD"]
    assert journal["expected_positions"] == {}
    assert journal["submit_error"] == "submit of BUY QQQ failed: RuntimeError('socket closed')"
    event = _events(tmp_path)[-1]
    assert event["status"] == "error"
    assert "BUY QQQ" in event["detail"]
    assert [o["symbol"] for o in event["orders"]] == ["GLD"]


def test_submit_failing_on_the_first_order_writes_no_journal(tmp_path):
    broker = FakeBroker(cash_usd=1e5)
    _fail_submit_on(broker, "QQQ")
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("error", 1)
    assert _journals(tmp_path) == []
    assert "submit of BUY QQQ failed" in _events(tmp_path)[-1]["detail"]


def test_a_failed_journal_write_leaves_the_order_ids_in_the_error_event(tmp_path, monkeypatch):
    from qrl import broker_run

    def full_disk(path, record):
        raise OSError("disk full")

    monkeypatch.setattr(broker_run, "write_journal", full_disk)
    broker = FakeBroker(cash_usd=1e5)
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("error", 1)
    assert "journal write failed" in result.detail
    (event,) = _events(tmp_path)
    assert event["status"] == "error"
    assert event["orders"] == [
        {"symbol": "QQQ", "side": "BUY", "shares": 158, "order_id": 1, "status": "submitted"}
    ]
    assert _journals(tmp_path) == []


def test_keyboard_interrupt_mid_batch_journals_what_was_sent_then_propagates(tmp_path):
    broker = FakeBroker(cash_usd=80_000.0, held=[Holding("GLD", "STK", "USD", Decimal("100"))])
    real = broker.submit

    def submit(orders: list[Order]):
        if orders[0].symbol == "QQQ":
            raise KeyboardInterrupt
        return real(orders)

    broker.submit = submit
    with pytest.raises(KeyboardInterrupt):
        evening_run(_ctx(tmp_path, broker, _market()))
    journal = json.loads((tmp_path / "2026-11-04.json").read_text())
    assert [o["symbol"] for o in journal["submitted"]] == ["GLD"]
    assert "BUY QQQ" in journal["submit_error"]
    assert _events(tmp_path)[-1]["orders"][0]["symbol"] == "GLD"


def test_event_write_failure_falls_back_to_stderr_with_the_order_ids(tmp_path, monkeypatch, capsys):
    from qrl import broker_run

    def no_events(root, record):
        raise OSError("read-only")

    monkeypatch.setattr(broker_run, "append_event", no_events)
    monkeypatch.setattr(broker_run, "write_journal", lambda path, record: 1 / 0)
    result = evening_run(_ctx(tmp_path, FakeBroker(cash_usd=1e5), _market()))
    assert (result.status, result.exit_code) == ("error", 1)
    err = capsys.readouterr().err
    assert "order_id=1" in err
    assert "journal write failed" in err


def test_a_second_interrupt_during_the_journal_write_still_writes_the_event(tmp_path, monkeypatch):
    from qrl import broker_run

    def interrupted(path, record):
        raise KeyboardInterrupt

    monkeypatch.setattr(broker_run, "write_journal", interrupted)
    broker = FakeBroker(cash_usd=80_000.0, held=[Holding("GLD", "STK", "USD", Decimal("100"))])
    real = broker.submit

    def submit(orders: list[Order]):
        if orders[0].symbol == "QQQ":
            raise KeyboardInterrupt
        return real(orders)

    broker.submit = submit
    with pytest.raises(KeyboardInterrupt):
        evening_run(_ctx(tmp_path, broker, _market()))
    event = _events(tmp_path)[-1]
    assert "submit of BUY QQQ failed" in event["detail"]
    assert "journal write failed" in event["detail"]
    assert [o["symbol"] for o in event["orders"]] == ["GLD"]


def test_rerun_after_a_partial_submit_is_refused(tmp_path):
    broker = FakeBroker(cash_usd=80_000.0, held=[Holding("GLD", "STK", "USD", Decimal("100"))])
    _fail_submit_on(broker, "QQQ")
    evening_run(_ctx(tmp_path, broker, _market()))
    broker.pending.clear()
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "rerun" in result.detail


def test_all_orders_rejected_still_writes_the_journal_with_positions_unchanged(tmp_path):
    held = [Holding("QQQ", "STK", "USD", Decimal("100"))]
    broker = FakeBroker(cash_usd=50_000.0, held=held, reject=frozenset({"QQQ"}))
    result = evening_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("submitted", 0)
    journal = json.loads(result.path.read_text())
    assert journal["submitted"][0]["status"] == "rejected"
    assert journal["expected_positions"] == {"QQQ": 100}


def test_combined_frame_without_the_session_row_is_refused(tmp_path):
    market = _market()
    market = replace(market, combined=market.combined.iloc[:-1])  # ends 11-03; session is 11-04
    broker = FakeBroker(cash_usd=1e5)
    result = evening_run(_ctx(tmp_path, broker, market))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "no combined weights for session 2026-11-04" in result.detail
    assert (broker.submitted, _journals(tmp_path)) == ([], [])


def test_combined_frame_running_past_the_session_is_refused(tmp_path):
    market = _market()
    later = pd.DataFrame({"QQQ": 0.8, "GLD": 0.0}, index=[pd.Timestamp("2026-11-05")])
    market = replace(market, combined=pd.concat([market.combined, later]))
    broker = FakeBroker(cash_usd=1e5)
    result = evening_run(_ctx(tmp_path, broker, market))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "after session 2026-11-04" in result.detail
    assert broker.submitted == []


LONGS = [Holding("QQQ", "STK", "USD", Decimal("10")), Holding("XYZ", "STK", "USD", Decimal("5"))]


def test_flatten_works_while_disabled_and_sells_every_long_including_unknown(tmp_path):
    broker = FakeBroker(held=list(LONGS), pending=[OpenOrder("QQQ", "BUY", 3, 7)])
    result = flatten_run(_ctx(tmp_path, broker, _market(), cfg=replace(CFG, enabled=False)))
    assert (result.status, result.exit_code) == ("flattened", 0)
    assert result.path == tmp_path / "2026-11-04-flatten-183000.json"
    assert broker.cancel_all_calls == 1
    assert [o.order for o in broker.submitted] == [
        Order("QQQ", "SELL", 10),
        Order("XYZ", "SELL", 5),
    ]
    journal = json.loads(result.path.read_text())
    assert (journal["kind"], journal["expected_positions"]) == ("flatten", {})
    assert journal["pre_trade_positions"] == {"QQQ": 10, "XYZ": 5}
    assert journal["recorded_at"] == "2026-11-04T23:30:00+00:00"


def test_second_flatten_is_idempotent(tmp_path):
    broker = FakeBroker(held=list(LONGS))
    flatten_run(_ctx(tmp_path, broker, _market()))
    later = datetime(2026, 11, 4, 23, 30, 1, tzinfo=UTC)
    result = flatten_run(_ctx(tmp_path, broker, _market(), later))
    assert result.exit_code == 0
    assert broker.cancel_all_calls == 2
    assert [(o.symbol, o.shares) for o in broker.open_orders()] == [("QQQ", 10), ("XYZ", 5)]
    assert _journals(tmp_path) == [
        "2026-11-04-flatten-183000.json",
        "2026-11-04-flatten-183001.json",
    ]


def test_flatten_refuses_short_positions_before_cancelling(tmp_path):
    broker = FakeBroker(held=[Holding("QQQ", "STK", "USD", Decimal("-5"))])
    result = flatten_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "short" in result.detail
    assert broker.cancel_all_calls == 0
    assert _journals(tmp_path) == []


def test_flatten_still_runs_the_paper_and_usd_stk_checks(tmp_path):
    live = FakeBroker(info=AccountInfo("U1", "USD", True, 4002), held=list(LONGS))
    assert "DU" in flatten_run(_ctx(tmp_path, live, _market())).detail
    fut = FakeBroker(held=[Holding("ES", "FUT", "USD", Decimal("1"))])
    assert "not STK in USD" in flatten_run(_ctx(tmp_path, fut, _market())).detail
    other = FakeBroker(info=AccountInfo("DU999", "USD", True, 4002), held=list(LONGS))
    assert "not the configured account" in flatten_run(_ctx(tmp_path, other, _market())).detail
    assert (live.cancel_all_calls, fut.cancel_all_calls, other.cancel_all_calls) == (0, 0, 0)


def test_after_flatten_runs_refuse_until_filled_then_reconcile_to_zero(tmp_path):
    broker = FakeBroker(held=list(LONGS))
    flatten_run(_ctx(tmp_path, broker, _market()))
    blocked = evening_run(_ctx(tmp_path, broker, _market("2026-11-05"), NEXT_EVENING))
    assert "open order" in blocked.detail
    broker.fill_all({"QQQ": 500.0, "XYZ": 10.0})  # cash 5_050
    later = datetime(2026, 11, 5, 23, 45, tzinfo=UTC)
    result = evening_run(_ctx(tmp_path, broker, _market("2026-11-05"), later))
    assert result.status == "submitted"
    journal = json.loads(result.path.read_text())
    assert journal["reconcile"] == {"status": "ok", "baseline": "2026-11-04T23:30:00+00:00"}
    assert journal["submitted"][0]["shares"] == 7  # floor(0.8 * 4_999.5 / 500)


def test_a_failed_flatten_call_is_an_error_event_and_writes_no_baseline(tmp_path):
    broker = FakeBroker(held=list(LONGS))

    def broken() -> list:
        raise RuntimeError("socket closed")

    broker.flatten = broken
    result = flatten_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("error", 1)
    assert "flatten failed: RuntimeError('socket closed')" in _events(tmp_path)[-1]["detail"]
    assert _journals(tmp_path) == []


def test_a_failed_flatten_journal_write_leaves_the_order_ids_in_the_error_event(
    tmp_path, monkeypatch
):
    from qrl import broker_run

    def full_disk(path, record):
        raise OSError("disk full")

    monkeypatch.setattr(broker_run, "write_journal", full_disk)
    result = flatten_run(_ctx(tmp_path, FakeBroker(held=list(LONGS)), _market()))
    assert (result.status, result.exit_code) == ("error", 1)
    assert "journal write failed" in result.detail
    assert [o["symbol"] for o in _events(tmp_path)[-1]["orders"]] == ["QQQ", "XYZ"]


def test_keyboard_interrupt_during_flatten_is_recorded_then_propagates(tmp_path):
    broker = FakeBroker(held=list(LONGS))

    def interrupted() -> list:
        raise KeyboardInterrupt

    broker.flatten = interrupted
    with pytest.raises(KeyboardInterrupt):
        flatten_run(_ctx(tmp_path, broker, _market()))
    assert "flatten failed" in _events(tmp_path)[-1]["detail"]


def test_flatten_with_no_holdings_still_cancels_and_journals_an_empty_baseline(tmp_path):
    broker = FakeBroker(pending=[OpenOrder("QQQ", "BUY", 3, 7)])
    result = flatten_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("flattened", 0)
    assert "0 sell order(s)" in result.detail
    assert broker.cancel_all_calls == 1
    journal = json.loads(result.path.read_text())
    assert (journal["submitted"], journal["expected_positions"]) == ([], {})


def test_a_failed_flatten_event_keeps_the_positions_and_the_next_run_refuses(tmp_path):
    broker = FakeBroker(held=[Holding("QQQ", "STK", "USD", Decimal("10"))])
    real = broker.flatten

    def sells_then_drops() -> list:
        real()  # the sells reached IB, then the connection died
        raise RuntimeError("socket closed")

    broker.flatten = sells_then_drops
    assert flatten_run(_ctx(tmp_path, broker, _market())).status == "error"
    assert _events(tmp_path)[-1]["pre_trade_positions"] == {"QQQ": 10}
    assert _journals(tmp_path) == []
    blocked = evening_run(_ctx(tmp_path, broker, _market("2026-11-05"), NEXT_EVENING))
    assert (blocked.status, blocked.exit_code) == ("refused", 1)
    assert "open order" in blocked.detail


@pytest.mark.parametrize(
    ("broker", "message"),
    [
        (FakeBroker(info=AccountInfo("DU123", "USD", True, 4001)), "port 4001"),
        (FakeBroker(info=AccountInfo("DU999", "USD", True, 4002)), "not the configured account"),
        (FakeBroker(held=[Holding("ES", "FUT", "USD", Decimal("1"))]), "not STK in USD"),
        (FakeBroker(held=[Holding("QQQ", "STK", "USD", Decimal("1.5"))]), "whole number"),
    ],
)
def test_accept_runs_the_connection_and_account_checks(tmp_path, broker, message):
    result = accept_positions_run(_ctx(tmp_path, broker, _market()))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert message in result.detail
    assert _journals(tmp_path) == []


def test_accept_does_not_refuse_shorts(tmp_path):
    broker = FakeBroker(held=[Holding("QQQ", "STK", "USD", Decimal("-5"))])
    result = accept_positions_run(_ctx(tmp_path, broker, _market()))
    assert result.status == "accepted"
    assert json.loads(result.path.read_text())["expected_positions"] == {"QQQ": -5}


def test_accept_journal_write_failure_is_an_error_event(tmp_path, monkeypatch):
    from qrl import broker_run

    def full_disk(path, record):
        raise OSError("disk full")

    monkeypatch.setattr(broker_run, "write_journal", full_disk)
    result = accept_positions_run(_ctx(tmp_path, FakeBroker(held=list(LONGS)), _market()))
    assert (result.status, result.exit_code) == ("error", 1)
    assert "disk full" in _events(tmp_path)[-1]["detail"]
    assert _journals(tmp_path) == []


def test_accept_file_records_what_it_overrides(tmp_path):
    broker = _after_first_run(tmp_path)  # baseline QQQ 158, one open order
    broker.pending.clear()  # accept refuses while orders are open
    broker.held = [Holding("QQQ", "STK", "USD", Decimal("150"))]
    accept_at = datetime(2026, 11, 5, 23, 40, tzinfo=UTC)
    accepted = accept_positions_run(_ctx(tmp_path, broker, _market("2026-11-05"), accept_at))
    journal = json.loads(accepted.path.read_text())
    assert journal["previous_baseline"] == "2026-11-04T23:30:00+00:00"
    assert journal["overridden_mismatches"] == ["QQQ: expected 158, IB holds 150"]


def test_accept_refuses_while_orders_are_open(tmp_path):
    broker = _after_first_run(tmp_path)  # one open order
    accept_at = datetime(2026, 11, 5, 23, 40, tzinfo=UTC)
    result = accept_positions_run(_ctx(tmp_path, broker, _market("2026-11-05"), accept_at))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "1 open order(s); wait for them to fill or cancel" in result.detail
    assert not list(tmp_path.glob("*-accept-*.json"))


def test_first_accept_has_no_previous_baseline(tmp_path):
    result = accept_positions_run(_ctx(tmp_path, FakeBroker(held=list(LONGS)), _market()))
    journal = json.loads(result.path.read_text())
    assert (journal["previous_baseline"], journal["overridden_mismatches"]) == (None, [])


def test_accept_positions_records_ib_positions_trades_nothing_and_unblocks(tmp_path):
    broker = _after_first_run(tmp_path)
    broker.pending.clear()
    broker.held = [Holding("QQQ", "STK", "USD", Decimal("150"))]
    broker.cash_usd = 25_000.0
    assert evening_run(_ctx(tmp_path, broker, _market("2026-11-05"), NEXT_EVENING)).exit_code == 1

    accept_at = datetime(2026, 11, 5, 23, 40, tzinfo=UTC)
    accepted = accept_positions_run(_ctx(tmp_path, broker, _market("2026-11-05"), accept_at))
    assert (accepted.status, accepted.exit_code) == ("accepted", 0)
    assert accepted.path == tmp_path / "2026-11-05-accept-184000.json"
    assert json.loads(accepted.path.read_text())["expected_positions"] == {"QQQ": 150}
    assert len(broker.submitted) == 1

    rerun_at = datetime(2026, 11, 5, 23, 50, tzinfo=UTC)
    result = evening_run(_ctx(tmp_path, broker, _market("2026-11-05"), rerun_at))
    assert result.status == "submitted"
    journal = json.loads(result.path.read_text())
    assert journal["reconcile"]["baseline"] == "2026-11-05T23:40:00+00:00"
    assert journal["submitted"][0]["shares"] == 8  # target 158, held 150


def test_nan_close_on_the_session_row_is_refused(tmp_path):
    market = _market()
    market.close["QQQ"] = float("nan")
    broker = FakeBroker(cash_usd=1e5)
    result = evening_run(_ctx(tmp_path, broker, market))
    assert (result.status, result.exit_code) == ("refused", 1)
    assert "missing or NaN latest close: QQQ" in result.detail
    assert broker.submitted == []
