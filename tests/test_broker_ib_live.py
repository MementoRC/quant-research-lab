"""Live IB PAPER check, skipped unless IB_GATEWAY_HOST is set. Read-only: no
orders. Run: IB_GATEWAY_HOST=127.0.0.1 pixi run -e broker pytest tests/test_broker_ib_live.py -q

The account id comes from IB_ACCOUNT_ID if set, else config/broker.yaml. The
port comes from IB_GATEWAY_PORT if set, else config/broker.yaml."""

from __future__ import annotations

import math
import os
from dataclasses import replace
from pathlib import Path

import pytest

from qrl.broker_config import load_broker_config
from qrl.broker_gate import paper_refusal

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not os.environ.get("IB_GATEWAY_HOST"),
    reason="needs a running IB paper gateway (IB_GATEWAY_HOST)",
)


def test_paper_gateway_read_only_round_trip():
    pytest.importorskip("market_connector")
    from qrl.broker_ib import IbBroker

    cfg = load_broker_config(ROOT / "config" / "broker.yaml")
    gateway_port = os.environ.get("IB_GATEWAY_PORT")
    cfg = replace(
        cfg,
        host=os.environ["IB_GATEWAY_HOST"],
        port=int(gateway_port) if gateway_port else cfg.port,
        account_id=os.environ.get("IB_ACCOUNT_ID") or cfg.account_id,
    )
    with IbBroker(cfg) as broker:
        info = broker.account()
        assert info.paper is True
        assert info.account_id == cfg.account_id
        assert paper_refusal(info) is None
        # The USD summary carries NetLiquidation only because USD is the base currency.
        assert info.base_currency == "USD"
        assert math.isfinite(broker.cash())
        assert all(h.symbol for h in broker.holdings())
        assert isinstance(broker.open_orders(), list)
