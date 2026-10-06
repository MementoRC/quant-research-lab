# Core shortlist reveal (exploration only)

> VALIDATION-SEEN: these cells use validation-period data (2020, 2022). One look, recorded in the ledger (event id 1).

Diagnostic of the shortlisted cores; it selects nothing. Spec: docs/methodology/core-reveal.md.

- shortlist sha256: `2176e90a095a11ed555d4879472bd9f9a43f12d9897d0df849cfc2ef90f53cfa`
- candidates file sha256: `1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3`
- stress.yaml sha256: `edd4b0853cc1b9a832111e74690e0c408ef89632002e1cbcfca7594c081cc682`
- max drawdown cap: 35% (config/profile.yaml)
- trial count of the original comparison: 7
- shortlist size: 3
- windows revealed: covid_2020, inflation_2022 (data cut at 2022-10-31)

## Stress cells

| id | portfolio | scenario | mode | loss | proxied to cash | flag |
|---|---|---|---|---|---|---|
| E | E | covid_2020 | replay | 16.9% |  |  |
| E | E | covid_2020 | frozen | 15.8% |  |  |
| E | E | inflation_2022 | replay | 15.7% |  |  |
| E | E | inflation_2022 | frozen | 15.8% |  |  |
| F | F | covid_2020 | replay | 14.0% |  |  |
| F | F | inflation_2022 | replay | 18.4% |  |  |
| F | F[risk_on] | covid_2020 | frozen | 14.1% |  |  |
| F | F[risk_on] | inflation_2022 | frozen | 16.8% |  |  |
| F | F[risk_off] | covid_2020 | frozen | 6.8% |  |  |
| F | F[risk_off] | inflation_2022 | frozen | 15.1% |  |  |
| G | G | covid_2020 | replay | 8.5% |  |  |
| G | G | covid_2020 | frozen | 8.6% |  |  |
| G | G | inflation_2022 | replay | 15.1% |  |  |
| G | G | inflation_2022 | frozen | 14.2% |  |  |

## Breaches

| id | breaches over revealed cells |
|---|---|
| E | 0 |
| F | 0 |
| G | 0 |

Note: for the switching candidate the replay cell is the rule itself; frozen cells are the static branches (`[risk_on]`, `[risk_off]`).
