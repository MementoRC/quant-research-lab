# Core comparison (exploration only)

Diagnostic of the pre-registered cores; it selects nothing. Spec: docs/methodology/core-comparison.md.

- candidates file sha256: `1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3`
- trial count: 7
- stress.yaml sha256: `edd4b0853cc1b9a832111e74690e0c408ef89632002e1cbcfca7594c081cc682`
- research period: 2005-01-01 to 2018-12-31 (validation and holdout data never used (prices are downloaded in full; every computation is cut at the research end))
- capital split: core 80% / sleeve 20% (sleeve empty, held as cash)
- max drawdown cap: 35% (config/profile.yaml)
- windows not evaluated (overlap validation): covid_2020, inflation_2022

## Research period

| id | rule | CAGR | Sharpe | max drawdown | turnover/yr | breaches |
|---|---|---|---|---|---|---|
| A | current: QQQ/GLD 200d trend | 6.1% | 0.47 | 25.6% | 12.70 | 5 |
| B | SPY/GLD 200d trend | 6.0% | 0.52 | 30.5% | 10.64 | 5 |
| C | SPY/IEF 200d trend | 4.9% | 0.56 | 21.8% | 10.64 | 5 |
| D | static 60/40 SPY/IEF | 5.5% | 0.69 | 25.7% | 0.00 | 0 |
| E | static SPY 60 / IEF 20 / GLD 20 | 6.2% | 0.70 | 25.9% | 0.00 | 0 |
| F | switched mix, SPY 200d signal | 5.2% | 0.74 | 15.8% | 6.39 | 0 |
| G | static 25% each SPY/TLT/GLD/SHY | 5.3% | 0.96 | 11.4% | 0.00 | 0 |

## Benchmark (not a candidate; not counted in the trial count)

| id | rule | CAGR | Sharpe | max drawdown | turnover/yr | breaches |
|---|---|---|---|---|---|---|
| QQQ@split | QQQ buy-and-hold at core share (rest cash) | 9.1% | 0.62 | 45.1% | 0.00 | 1 |
| QQQ@100 | QQQ buy-and-hold, 100% | 11.1% | 0.62 | 53.4% | 0.00 | 1 |

Breaches: research-period drawdown vs the cap only (0/1). Stress cells for 80% QQQ equal candidate A's `A[risk_on]` rows above.

## Stress cells

| id | portfolio | scenario | mode | loss | proxied to cash | flag |
|---|---|---|---|---|---|---|
| A | A | gfc_2008 | replay | 22.5% |  |  |
| A | A[risk_on] | dotcom_2000 | frozen | 66.4% |  | BREACH |
| A | A[risk_on] | gfc_2008 | frozen | 43.0% |  | BREACH |
| A | A[risk_on] | no_safe_haven | hypothetical | 40.0% |  | BREACH |
| A | A[risk_on] | stagflation | hypothetical | 36.0% |  | BREACH |
| A | A[risk_on] | energy_shock_severe | hypothetical | 32.0% |  |  |
| A | A[risk_on] | tech_crash | hypothetical | 48.0% |  | BREACH |
| A | A[risk_off] | dotcom_2000 | frozen | 0.0% | gold 80% |  |
| A | A[risk_off] | gfc_2008 | frozen | 24.8% |  |  |
| A | A[risk_off] | no_safe_haven | hypothetical | 16.0% |  |  |
| A | A[risk_off] | stagflation | hypothetical | -8.0% |  |  |
| A | A[risk_off] | energy_shock_severe | hypothetical | 8.0% |  |  |
| A | A[risk_off] | tech_crash | hypothetical | 0.0% |  |  |
| B | B | gfc_2008 | replay | 29.0% |  |  |
| B | B[risk_on] | dotcom_2000 | frozen | 38.0% |  | BREACH |
| B | B[risk_on] | gfc_2008 | frozen | 44.2% |  | BREACH |
| B | B[risk_on] | no_safe_haven | hypothetical | 40.0% |  | BREACH |
| B | B[risk_on] | stagflation | hypothetical | 36.0% |  | BREACH |
| B | B[risk_on] | energy_shock_severe | hypothetical | 32.0% |  |  |
| B | B[risk_on] | tech_crash | hypothetical | 48.0% |  | BREACH |
| B | B[risk_off] | dotcom_2000 | frozen | 0.0% | gold 80% |  |
| B | B[risk_off] | gfc_2008 | frozen | 24.8% |  |  |
| B | B[risk_off] | no_safe_haven | hypothetical | 16.0% |  |  |
| B | B[risk_off] | stagflation | hypothetical | -8.0% |  |  |
| B | B[risk_off] | energy_shock_severe | hypothetical | 8.0% |  |  |
| B | B[risk_off] | tech_crash | hypothetical | 0.0% |  |  |
| C | C | gfc_2008 | replay | 11.2% |  |  |
| C | C[risk_on] | dotcom_2000 | frozen | 38.0% |  | BREACH |
| C | C[risk_on] | gfc_2008 | frozen | 44.2% |  | BREACH |
| C | C[risk_on] | no_safe_haven | hypothetical | 40.0% |  | BREACH |
| C | C[risk_on] | stagflation | hypothetical | 36.0% |  | BREACH |
| C | C[risk_on] | energy_shock_severe | hypothetical | 32.0% |  |  |
| C | C[risk_on] | tech_crash | hypothetical | 48.0% |  | BREACH |
| C | C[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 80% |  |
| C | C[risk_off] | gfc_2008 | frozen | 5.1% |  |  |
| C | C[risk_off] | no_safe_haven | hypothetical | 12.0% |  |  |
| C | C[risk_off] | stagflation | hypothetical | 16.0% |  |  |
| C | C[risk_off] | energy_shock_severe | hypothetical | 8.0% |  |  |
| C | C[risk_off] | tech_crash | hypothetical | -4.0% |  |  |
| D | D | dotcom_2000 | frozen | 22.8% | bonds 32% |  |
| D | D | gfc_2008 | replay | 25.7% |  |  |
| D | D | gfc_2008 | frozen | 20.0% |  |  |
| D | D | no_safe_haven | hypothetical | 28.8% |  |  |
| D | D | stagflation | hypothetical | 28.0% |  |  |
| D | D | energy_shock_severe | hypothetical | 22.4% |  |  |
| D | D | tech_crash | hypothetical | 27.2% |  |  |
| E | E | dotcom_2000 | frozen | 22.8% | bonds 16%, gold 16% |  |
| E | E | gfc_2008 | replay | 25.9% |  |  |
| E | E | gfc_2008 | frozen | 22.5% |  |  |
| E | E | no_safe_haven | hypothetical | 29.6% |  |  |
| E | E | stagflation | hypothetical | 23.2% |  |  |
| E | E | energy_shock_severe | hypothetical | 22.4% |  |  |
| E | E | tech_crash | hypothetical | 28.0% |  |  |
| F | F | gfc_2008 | replay | 15.8% |  |  |
| F | F[risk_on] | dotcom_2000 | frozen | 22.8% | bonds 32% |  |
| F | F[risk_on] | gfc_2008 | frozen | 20.0% |  |  |
| F | F[risk_on] | no_safe_haven | hypothetical | 28.8% |  |  |
| F | F[risk_on] | stagflation | hypothetical | 28.0% |  |  |
| F | F[risk_on] | energy_shock_severe | hypothetical | 22.4% |  |  |
| F | F[risk_on] | tech_crash | hypothetical | 27.2% |  |  |
| F | F[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 40%, gold 40% |  |
| F | F[risk_off] | gfc_2008 | frozen | 13.7% |  |  |
| F | F[risk_off] | no_safe_haven | hypothetical | 14.0% |  |  |
| F | F[risk_off] | stagflation | hypothetical | 4.0% |  |  |
| F | F[risk_off] | energy_shock_severe | hypothetical | 8.0% |  |  |
| F | F[risk_off] | tech_crash | hypothetical | -2.0% |  |  |
| G | G | dotcom_2000 | frozen | 9.5% | bonds 40%, gold 20% |  |
| G | G | gfc_2008 | replay | 11.4% |  |  |
| G | G | gfc_2008 | frozen | 11.4% |  |  |
| G | G | no_safe_haven | hypothetical | 20.0% |  |  |
| G | G | stagflation | hypothetical | 15.0% |  |  |
| G | G | energy_shock_severe | hypothetical | 14.0% |  |  |
| G | G | tech_crash | hypothetical | 10.0% |  |  |

Note: in `dotcom_2000` the bond and gold ETFs did not yet exist, so bonds/gold weights are treated as cash (the "proxied to cash" column); this understates their cushion in that window.

Note: for switching candidates the breach count covers the replay cell plus both branch cells (`[risk_on]`, `[risk_off]`), plus the research-period breach.
