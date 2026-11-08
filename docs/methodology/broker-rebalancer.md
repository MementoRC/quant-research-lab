# Broker rebalancer: daily automatic trading of the combined portfolio on an IB paper account

Status: Implemented 2026-11-05 (PR #102); connector pinned at 5829aa1.
Implements PLAN.md milestone 3.4, amendment 2026-11-05.
The forward paper track (`config/paper.yaml`, `src/qrl/paper.py`) is
unaffected.

## Purpose

A daily, fully automatic rebalancer. It trades qrl's combined portfolio on an
Interactive Brokers PAPER account through hb-market-connector. The combined
portfolio is the one `scripts/daily_check.py` builds: the `portfolio.yaml`
core times the core share of `profile.yaml`'s `capital_split`. The sleeve is
currently empty, so its share stays cash.

## Not a test

Execution only. No strategy, metric, period, criteria or ledger rule changes,
and no locked file is edited. It adds no trials to any search run.

## Owner decisions (2026-11-05)

- Trade the combined portfolio.
- Fully automatic: no human confirm step.
- Evening run after the close. Orders are market-on-open (MOO: a MARKET
  order with time in force `OPG`, `outside_rth=False`), which IB holds for
  the next opening auction. This matches the engine's timing contract:
  weights from the close of day t execute at the open of day t+1. The
  connector sets no local cut-off; IB rejects a late MOO order. The
  exchanges' MOO cut-off is about 09:28 ET (an exchange rule, not stated
  by the connector), long after the 18:30 ET run.
- Market-on-open since hb-market-connector #180 landed (#184).
- Install the connector from a pinned git commit.
- Paper only.

## Components

- `src/qrl/broker.py`: the `Broker` Protocol, fully typed:
  - `account() -> AccountInfo`
  - `holdings() -> list[Holding]`
  - `cash() -> float`
  - `open_orders() -> list[OpenOrder]`
  - `submit(orders: list[Order]) -> list[SubmittedOrder]`
  - `flatten() -> list[SubmittedOrder]`

  Dataclasses: `AccountInfo(account_id, base_currency, paper, port)` (the
  connection spec's paper flag and port, for the paper check);
  `Holding(symbol, sec_type, currency, quantity: Decimal)` (a position as IB
  reports it, for the USD/STK/whole-share check); `Position(symbol, shares:
  int)`, built by `to_positions(holdings)` once the Gate has passed;
  `Order(symbol, side BUY/SELL, shares: int > 0)`; `OpenOrder(symbol, side,
  shares, order_id)`; `SubmittedOrder(order: Order, order_id: int, status:
  str)`. `FakeBroker` is an in-memory implementation for tests.
- `src/qrl/rebalance.py`: a pure planner,
  `plan(target_weights, closes, positions, cash, cfg, limits) -> Plan(orders,
  skipped with reasons, refusals)` (limits: the `config/profile.yaml` `risk:`
  caps, see Refusals). All sizing and safety rules live here.
  `scripts/` is not covered by `pytest --cov`, so logic stays in `src/qrl`.
- `src/qrl/broker_ib.py`: the IB adapter over
  `market_connector.exchanges.interactive_brokers.factory.build_ib_gateway(IbConnectionSpec(host,
  port, client_id, account_id, paper=True, fetch_all_open_orders=True))`. The
  connector is async-only (`await gateway.start()` / `stop()`,
  `get_positions`, `place_order(InstrumentRef(symbol, STOCK,
  quote_currency="USD"), HBOrder(order_type=MARKET, side, amount=Decimal,
  time_in_force=OPG, outside_rth=False))`, `cancel_order(handle)`,
  `cancel_all()`). `cash()` reads `get_account_summary("USD").total_cash_value`
  (#181, landed as #185). Open orders come from the sync
  `gateway.get_open_orders()`, after the adapter repeats the all-open-orders
  request itself (the connector only logs a failed sync at connect); a
  failure raises. `account()` reports IB's own facts: the connector echoes the
  configured account id in its summary, so the adapter reads IB's
  managed-accounts list (the connector's ib_async `IB` instance, reached
  through the transport's private `_ib`; there is no public accessor). An
  empty or unreadable list refuses the run. If the configured id is not in
  the list the first managed account is reported, so the Gate refuses as "not
  the configured account". `paper` is true only if the reported id and every
  managed account are DU-prefixed (a mixed live and paper login is refused).
  The adapter also refuses a live port or non-DU account in its own config.
  The adapter is a context manager holding one
  event loop and one connected gateway for the whole run; `__exit__` stops
  the gateway and closes the loop. It is importable only in the `broker` pixi environment (lazy import).
- `scripts/rebalance.py` and a pixi task `rebalance` in environment `broker`.
  IO only.
- `config/broker.yaml` (new, not hash-locked, strictly validated, unknown keys
  rejected):

  | key | rule |
  |---|---|
  | `enabled` | bool |
  | `host` | string |
  | `port` | int |
  | `client_id` | int >= 0, fixed in the file |
  | `account_id` | string |
  | `cash_buffer` | default 0.01, in [0, 0.10] |
  | `deadband` | default 0.005 (of equity), in [0, 0.05] |

  The committed file keeps placeholders. The owner keeps real settings in a
  gitignored `config/broker.local.yaml`, same keys; when it exists the script
  and the live test read it instead of `config/broker.yaml`
  (`broker_config_path`).

## Delivery

Two parts. The first PR ships the broker protocol, `FakeBroker`, the planner,
the journal and reconcile logic, config loading and the script, all tested
against `FakeBroker`. The IB adapter and the `broker` pixi environment follow
in a second PR once the connector exposes TotalCashValue. The plan's first
task proves the dependency by reading the connector source at the pinned
commit for an account-summary / TotalCashValue accessor. If it is there, both
parts go in one PR. A gated live test confirms it later.

## Cash and equity

The connector's `get_balance("USD")` returns AvailableFunds. That is
margin-based, not cash. The adapter's `cash()` must return the USD
TotalCashValue. It comes from `get_account_summary("USD")` (hb-market-connector
#181, landed as #185); an unreported value refuses the run. The summary's
`currency` is the requested code ("BASE" when none is given), not the base
currency's name, so the base is taken to be USD exactly when the USD summary
has a NetLiquidation, which IB reports only in the base currency; otherwise
the run refuses. Never fall back to AvailableFunds.

Refuse when the account base currency is not USD, or when any position is not
STK or not USD.

## Universe

The universe is the columns of the combined weight frame: all core tickers
(both risk_on and risk_off) plus sleeve tickers. There is no CASH ticker;
unallocated weight simply stays as cash. A held universe symbol with weight 0
is fully exited. A held symbol outside the universe means refuse.

## Evening run

In order:

1. **Gate.** The first step after connecting to IB. It keeps only checks that
   need just the connection, in this order: (1) `enabled`; (2) the 3-part
   paper check, then the reported account must equal `account_id` in
   `config/broker.yaml`; (3) the account base currency is USD, every position
   is STK in USD, and every quantity is a whole number; (4) no open orders. Every
   refusal sends no orders, appends an events line and exits non-zero.
2. **Data and session.** Run the `qrl.health` daily checks. Build the
   combined weights frame and the closes, then compute the session date: the
   date of the latest bar for all held and non-zero-target symbols (not the
   wall-clock date). Only then, in order: (a) the "no new session" exit: if the
   session date is earlier than today's date in America/New_York, exit 0 with
   status "no new session": no reconcile, no orders; (b) the same-session
   rerun check (see Journal); (c) the unknown-position check (universe = the
   frame's columns). Checking "no new session" first means late data on the
   evening after a submitted run exits 0 instead of counting as a rerun. This
   covers weekends, holidays and late data. A stale symbol with a zero target
   that is not held is ignored (stated explicitly). The separate daily health
   check (one-business-day tolerance, exits non-zero) catches a persistent
   vendor lag, not the rebalancer. Data-dependent refusals (a missing or NaN
   close, NaN or negative weights, risk caps) are checked during sizing.
3. **Reconcile.** `expected = pre-trade positions + submitted deltas` from the
   previous journal. Reconcile runs at the start of the next evening's run,
   after the open fills. Positions must match exactly, symbol by symbol, in
   shares. The journal records each order's status as seen at submit time;
   rejected or cancelled orders count as delta 0 in `expected`. "Previous
   journal" is the file with the greatest `recorded_at` among submitted-run,
   flatten and accept files; never order by filename. If there is none, skip reconcile and say so in
   the journal; the unknown-position rule still applies.
   On a mismatch: record it, send no orders, exit non-zero. Trading stays
   halted until a human runs `rebalance --accept-positions`, which writes
   `reports/broker/<NY-date>-accept-<HHMMSS>.json`; its recorded IB positions
   become the expected positions. That run trades nothing, and refuses while
   any order is open ("N open order(s); wait for them to fill or cancel").
4. **Size.** Any held or non-zero-target symbol with a missing or NaN latest
   close: refuse the whole run. Never value it at 0.
   `equity = IB cash + sum(shares x our close)`. Cash is TotalCashValue (see
   above). `target_shares = floor(w x equity x (1 - cash_buffer) / close)` as
   a Python int.
5. **Orders.** `delta = target - held`. Skip if `|delta x close| < deadband x
   equity`, unless the target is 0 (full exits always go). There is no minimum
   order size beyond the deadband. Sells are listed before buys, but that is
   best effort only: queued market orders all hit the same open. Sells that
   the deadband skips leave shares unsold, so buys are capped: they are scaled
   down, rounding down, until their cost at our closes is no more than cash
   plus the surviving sells' proceeds minus the cash buffer (no cash after the
   buffer means no buys; sells are never touched, and the plan records a note).
   The buffer itself stays for open-versus-close price moves.
6. **Submit** market-on-open orders (MARKET, time in force `OPG`),
   `outside_rth=False`.
7. **Journal** to `reports/broker/<session-date>.json` (private, gitignored,
   never under `site/`): inputs, weights, equity, plan, pre-trade and expected
   positions, order ids and status, skips. Only a run that submits orders
   writes this dated file. Flatten and accept-positions keep their
   timestamped files. Every other outcome (refusals at any step, reconcile
   mismatches, "no new session") appends one line to
   `reports/broker/events.jsonl` and never writes or overwrites a dated
   journal, so a rerun of a session that already submitted cannot damage that
   session's journal. The same-session rerun refusal fires if the dated file
   exists. Every journal file and events line records `recorded_at` as a UTC
   ISO timestamp. Journal writes are atomic and never overwrite: a crash can
   leave a stray `.tmp` file but never a truncated journal. A journal that
   cannot be read (bad JSON, or a missing or naive `recorded_at`) halts the
   run with an error naming the file; it is never skipped.

## Refusals (no orders sent)

- The connection is not paper. The paper check needs all of: `spec.paper` is
  True, the port is not 4001 or 7496, and the account id starts with "DU".
  The account the connection reports must also equal `account_id` in
  `config/broker.yaml`.
- The account base currency is not USD, or any position is not STK or not USD.
- The account holds a symbol outside the universe.
- Any open order exists for the account (the adapter sets
  `fetch_all_open_orders=True`). Never auto-cancel.
- The session's journal already records submitted orders, so a same-session
  rerun errors.
- Any held or non-zero-target symbol has a missing, NaN, infinite or
  non-positive latest close.
- A position quantity is not a whole number of shares, a symbol appears in two
  positions, or a position is short.
- Equity (IB cash plus held shares at our closes) is not a positive, finite
  number.
- The target weights fail the `qrl.risk` caps from `config/profile.yaml`
  `risk:` (long-only, gross <= 1.0; no leverage, per the owner decision). The
  planner builds a one-row combined frame and calls
  `qrl.risk.check_portfolio` with an empty sleeve. It also refuses explicitly
  on any NaN or negative weight, because `check_portfolio` passes NaN weights.
- `enabled: false`.

## Kill switch

`pixi run -e broker rebalance --flatten` (PLAN 3.4 kill switch).

- The only checks are the paper-only check and the USD/STK check. It works
  even when `enabled` is false and skips the data, reconcile, universe and
  session checks.
- It calls `cancel_all()` first, then sends one DAY market SELL for each long
  position (DAY, not MOO, so it also works during the session), unknown
  symbols included. Short positions mean refuse and report.
- It journals to `reports/broker/<NY-date>-flatten-<HHMMSS>.json`.
- A second `--flatten` is allowed and idempotent, because it calls
  `cancel_all()` first.
- Its queued sells leave open orders, so normal runs refuse until those fill.
  That is intended.
- The next normal run reconciles against the flatten's expected positions
  (all zero).

## Packaging

A new pixi feature and environment `broker` with the pypi dependency
`hb-market-connector`, a standalone repo, from git
`https://github.com/MementoRC/hb-market-connector.git` (no subdirectory) at
the pinned commit 5829aa1, plus `ib_async>=2.1,<3` (the connector declares no
extra for it). The broker feature caps `python-tzdata` below 2026, because
`ib_async` 2.x caps `tzdata` below 2026; the other environments are not
affected. The default, dev and ci environments are unchanged; CI never
installs the connector. The connector requires Python >= 3.12 and pulls four
MementoRC git dependencies (hb-logger, hb-data-type-primitives,
hb-event-bus, hb-rate-limit).

## Testing

- Planner unit tests: flooring, buffer, deadband, full exits, sell-before-buy,
  NaN and negative weights, and each refusal.
- Config tests: defaults, ranges, unknown keys, types.
- The America/New_York date across a DST change and around midnight (session
  date vs wall clock).
- Each of the three paper-check parts failing on its own.
- A fractional position quantity refused; a non-USD base currency refused; a
  non-STK or non-USD position refused.
- The order of the Gate checks, and of the step 2 checks ("no new session",
  rerun, unknown position), including late data on the evening after a
  submitted run (exit 0, not a rerun).
- `events.jsonl` written on "no new session", and no dated journal touched.
- The reconcile baseline chosen by `recorded_at`, not filename.
- A test that importing `qrl.broker` or `qrl.rebalance` never imports
  `market_connector`.
- `FakeBroker` end-to-end evening run, including a reconcile mismatch and
  `--accept-positions`, a first run with no journal, "no new session", a
  rerun on the same date, open orders, and `--flatten`.
- Adapter tests with a mocked gateway (`AsyncMock`).
- One live paper test, marked and skipped unless `IB_GATEWAY_HOST` is set.

## Known differences from the backtest

- Whole shares plus the cash buffer leave a small cash drag.
- The deadband lets weights drift where the engine rebalances exactly daily.
- MOO orders fill in the opening auction, close to the engine's open price
  but not identical to the data vendor's open.
- IB paper fills and commissions differ from the criteria `cost_bps`.
- IB cash may earn interest while the engine assumes 0%.
- Paper market data is delayed. It is not used for sizing; sizing uses our
  closes.

## Out of scope

- Live trading. It needs a future PLAN amendment and a code change.
- Sleeve candidates on IB.
- Scheduling. Cron example only, Monday to Friday at 18:30 ET. The first line
  is a cronie/vixie extension:

  ```
  CRON_TZ=America/New_York
  30 18 * * 1-5 cd /path/to/repo && pixi run -e broker rebalance
  ```
- hb-market-connector #182 (fractional shares). #180 and #181 landed (#184,
  #185). Fill history (`get_fills(since)`, #185) is not used: reconcile stays
  position-based.

## Implementation notes (2026-11-05)

- Helpers: `qrl.live_weights` (combined weights, shared with
  `scripts/daily_check.py`), `qrl.broker_config`, `qrl.broker_session`,
  `qrl.broker_journal`, `qrl.broker_gate`, `qrl.broker_run`.
- A failing `qrl.health` report refuses the run (exit 1). A plan with no
  orders is "nothing to trade" (events line, exit 0). `--flatten` and
  `--accept-positions` also refuse fractional quantities.
- The rebalancer loads prices with `refresh=True`, like the paper track.
- `OrderHandle` has no symbol, side or quantity, so the IB adapter keeps its
  own order-id-to-order mapping; open orders it did not place are reported
  as UNKNOWN (the Gate only needs to know they exist).
