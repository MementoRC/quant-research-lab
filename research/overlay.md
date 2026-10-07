# Macro overlay on core G

Spec: docs/methodology/macro-overlay.md (pre-registered 2026-10-07). One fixed spec, one trial, no tuning.

Trials: 1

- overlay.yaml sha256: `fdb60fb5af6cc009b9996eaa45d48da3df814f3fbde076040de38db4a3de79c7`
- core_candidates.yaml sha256: `1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3`
- criteria.yaml hash: `2f8f59b620a7`

## Research 2005-2018 (decides the track)

Ledger overlay event 1 (2026-10-07T21:04:00.629931+00:00).

Window 2005-01-03 to 2018-12-31. Verdict: **PASS**.

| metric | overlay-G | static G |
|---|---|---|
| Sharpe | 1.054 | 0.956 |
| CAGR | 6.41% | 6.56% |
| Max drawdown | 10.36% | 14.11% |
| Volatility | 6.06% | 6.90% |

| rule | value | threshold | passed |
|---|---|---|---|
| Sharpe vs G | 1.054 | >= 1.006 | yes |
| Max drawdown vs G | 0.1036 | <= 0.1411 | yes |
| CAGR vs G | 0.0641 | >= 0.0556 | yes |
| Sharpe gain vs null 95th percentile (linear interpolation) | 0.099 | > 0.093 | yes |

Null: 1000 spell-shuffle draws (seed 20261007); 95th percentile (linear interpolation) Sharpe gain 0.093, mean 0.019.

First month end each signal is on (off before): inflation 2005-10-31, trend_GLD 2008-08-29, trend_SPY 2000-09-29, trend_TLT 2003-07-31, vol 2007-08-31.

## Validation 2019-2022 (VALIDATION-SEEN, not decisive)

Ledger overlay event 2 (2026-10-07T21:04:36.205993+00:00).

> VALIDATION-SEEN: the 2020 and 2022 windows were already seen once (research/core_reveal.md, ledger event 1), including G's 2022 loss. Weak evidence, reported only.

Window 2019-01-02 to 2022-12-30. Verdict: **FAIL**.

| metric | overlay-G | static G |
|---|---|---|
| Sharpe | 0.710 | 0.691 |
| CAGR | 4.91% | 5.61% |
| Max drawdown | 15.11% | 18.53% |
| Volatility | 7.10% | 8.42% |

| rule | value | threshold | passed |
|---|---|---|---|
| Sharpe vs G | 0.71 | >= 0.741 | no |
| Max drawdown vs G | 0.1511 | <= 0.1853 | yes |
| CAGR vs G | 0.0491 | >= 0.0461 | yes |
