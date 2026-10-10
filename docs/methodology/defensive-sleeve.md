# Defensive sleeve: what 20% in bonds or cash buys and costs

Status: spec written 2026-10-10, owner-approved design 2026-10-10. Not yet run.
Extends [decision-helper.md](decision-helper.md) and [longrun.md](longrun.md).

## Question

The owner withdraws for income. Next to the 80% core (A: `core_trend`,
QQQ/GLD, 200-day), how much does a 20% defensive sleeve cut drawdowns and
stress losses, and improve withdrawal survival? And what does it cost in
return?

## A comparison, not a pass/fail test

- The combined rule (Sharpe gain >= 0.05, CAGR shortfall <= 1%) and
  validation (deflated Sharpe of combined minus core) reward added return,
  not lower drawdown. A defensive sleeve fails them by design.
- It is not blind. `core_compare` (G: SPY/TLT/GLD/SHY, the lowest drawdown
  2005-2018) and `research/decision.md` already show how these assets
  behaved.
- So the result is a decision aid, not evidence of an edge. It adds no
  trials to any search run. Run 7 (RSP) passed research but failed
  validation; RSP appears here only as a reference row.

## Variants

Each is 80% A + 20% sleeve, a blend in `config/decision.yaml`. GLD is
excluded: it is already the core's risk-off asset.

| id | sleeve | role |
|---|---|---|
| A80-CASH20 | CASH (100% SHY) | baseline: what an empty sleeve holds |
| A80-IEF20 | IEF | intermediate Treasuries |
| A80-TLT20 | TLT | long Treasuries |
| A80-BONDS20 | BONDS (1/3 each SHY / IEF / TLT) | bond ladder |
| A80-RSP20 | RSP | reference (run 7's sleeve) |

How cash is modelled. The decision helper has no true cash: its `CASH`
portfolio is 100% SHY, and the scenarios treat SHY as cash-like. The
long-run report adds one assumption row, "CASH +1% real", for `CASH` only.
The stress module proxies an unpriced bond or gold fund by true cash (0%).
This spec uses the existing `CASH` static (SHY) for the baseline, so all
variants share one price-based method. No new cash assumption row is added
for the blends; the report states that SHY's near-zero 2009-2015 yields
make the baseline look worse than cash at today's rates.

Blends can only combine A-G and statics, so four statics are added. Each
also appears as its own 100% portfolio row; those rows are by-products, not
part of the question.

```yaml
# Amendment 2026-10-10 (owner-approved design, spec
# docs/methodology/defensive-sleeve.md): statics IEF, TLT, RSP, BONDS and
# blends A80-*20 added for the defensive-sleeve comparison. Existing
# entries unchanged; candidates_sha256 unchanged.
static:
  # ... CASH, G-EW unchanged ...
  - {id: IEF, label: "100% IEF", mix: {IEF: 1.0}}
  - {id: TLT, label: "100% TLT", mix: {TLT: 1.0}}
  - {id: RSP, label: "100% RSP", mix: {RSP: 1.0}}
  - {id: BONDS, label: "1/3 each SHY / IEF / TLT", mix: {SHY: 0.3333333333333333, IEF: 0.3333333333333333, TLT: 0.3333333333333333}}
blends:
  # ... AG, G-CASH, A-CASH unchanged ...
  - {id: A80-CASH20, label: "80% A + 20% CASH", parts: {A: 0.8, CASH: 0.2}}
  - {id: A80-IEF20, label: "80% A + 20% IEF", parts: {A: 0.8, IEF: 0.2}}
  - {id: A80-TLT20, label: "80% A + 20% TLT", parts: {A: 0.8, TLT: 0.2}}
  - {id: A80-BONDS20, label: "80% A + 20% BONDS", parts: {A: 0.8, BONDS: 0.2}}
  - {id: A80-RSP20, label: "80% A + 20% RSP", parts: {A: 0.8, RSP: 0.2}}
```

The BONDS weights sum to 1 within the loader's 1e-9 tolerance. Every held
fund (SHY, IEF, TLT, RSP) is already in each judgement-based scenario, so
no scenario changes. The report's multiple-comparison count rises from 12
to 21 portfolios; the report computes it.

## Measures

Existing, unchanged:

- Historical windows from `config/stress.yaml`: `dotcom_2000` (frozen) and
  `gfc_2008` (replay and frozen). In `dotcom_2000` the bond sleeves and A's
  risk-off GLD are proxied by cash, so those cells are indicative only.
- The three judgement-based shocks, both states of A, nominal and real.
- CPI-indexed withdrawals at 2%, 3.3%, 4% and 5%, start years 2005-2014.
- Long-run 30-year block-bootstrap survival (`pixi run longrun`), which
  reads the same portfolios from `decision.yaml`.

New: one research-period return line per portfolio, 2005-2018 with no
withdrawals: CAGR, max drawdown, and CAGR minus A's CAGR ("lost return").

- `src/qrl/decision.py`: new `return_rows(cfg, data, criteria)`. It calls
  the existing `portfolio_returns` from the first 2005 start date to
  2018-12-31 at `criteria.yaml`'s `cost_bps`, and reads `cagr` and
  `max_drawdown` from `qrl.metrics.compute_metrics` (read, not edited).
  `run_decision` adds its rows under a new `returns` key.
- `src/qrl/decision_report.py`: new `_return_section`, rendered after the
  portfolio section as "## Research-period return (2005-2018, no
  withdrawals)". The dashboard picks it up unchanged (`site_core` renders
  every `## ` section).
- The dot-com proxy note in `_window_section` names its portfolios in a
  fixed string; it gains the new blends and statics.

## Periods

Research period 2005-2018 only, as in the existing tools. Validation
(2019-2022) and the holdout (2023 on) are not touched. `stress.yaml` also
has 2020 and 2022 windows; they lie past 2018-12-31 and are deliberately
not used (the loader refuses them anyway).

## Config bookkeeping

- `config/decision.yaml`: the entries above, with the dated amendment
  comment. Its `candidates_sha256` pin of `core_candidates.yaml` is
  unchanged.
- `config/longrun.yaml`: `decision_sha256` updated to the new hash of
  `decision.yaml`, with a comment: "Amendment 2026-10-10: decision_sha256
  re-pinned after the defensive-sleeve blends were added
  (docs/methodology/defensive-sleeve.md). No other key changed."

## Outputs

- Regenerate `research/decision.md` (`pixi run decision`) and
  `research/longrun.md` (`pixi run longrun`). The public dashboard shows them
  as before.
- No separate `research/defensive_sleeve.md`. The comparison lives in the two
  reports; the PR description gives a short summary of the A80 rows.

## Tests

- New: the shipped `decision.yaml` loads; each A80 blend's states sum to 1
  and hold 0.8 of A's branch plus 0.2 of the sleeve; BONDS holds 1/3 each.
- New: `return_rows` on synthetic prices matches `compute_metrics`, and the
  rendered section shows CAGR, max drawdown and the gap to A.
- Existing tests keep every assertion. Two are tripwires on the shipped
  `decision.yaml`: `test_decision_shipped_config_loads` (exact id list) and
  `test_decision_shipped_config_matches_test_fixture` (shipped file equals
  `tests/decision_helpers.py`'s `GOOD`). Both fail on any edit by design.
  Proposed, for owner approval: append the nine new ids to the expected list,
  and compare the shipped file to `GOOD` plus the new entries (a new helper
  constant), leaving `GOOD` and the fixture-driven tests unchanged.
- Full suite run in the background before the PR.

## Not changed

AGENTS.md-protected files (`criteria.yaml`, `combined.yaml`,
`combined_null.yaml`, `paper.yaml`, `factor.yaml`, `engine.py`,
`metrics.py`, `periods.py`, `checks.py`), `profile.yaml`'s `capital_split`,
`portfolio.yaml`'s core, `core_candidates.yaml`, `stress.yaml`, and existing
test assertions.
