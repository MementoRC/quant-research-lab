# RSP sleeve: 80% core + 20% RSP vs 100% core

One fixed candidate (buy-and-hold RSP), no search. Spec: docs/methodology/rsp-sleeve.md.

- run: 7
- attempts: 1
- verdict: Research period (2005-2018): PASSED
- combined_fixed.yaml config hash: `6f453f1f2c90`

## Result

Research period 2005-01-01 to 2018-12-31, costs from criteria.yaml.

| portfolio | CAGR | Sharpe | max drawdown |
|---|---|---|---|
| core alone (100%) | 7.3% | 0.48 | 29.9% |
| core 80% + RSP 20% | 7.8% | 0.53 | 29.8% |

- Sharpe gain, combined minus core (the pass rule's check, minimum 0.05): 0.06
- Sharpe of the daily (combined - core) return difference (improvement_sharpe, used for ranking): 0.04
- RSP alone: CAGR 7.9%, Sharpe 0.48, max drawdown 59.9%, 1 trade day(s)

## Validation

validate funnel: 1 survivor, passed neighbourhood, evaluated on validation; failed deflated Sharpe (0.495 < required 0.95); accepted 0

## Notes

- The holdout (2023 onward) stays sealed.
- Nothing was tuned or rerun. A retry needs a new dated, owner-approved amendment.
