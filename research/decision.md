# Decision helper: portfolios, scenarios and withdrawals

A decision aid for deploying savings while withdrawing for income. It compares a fixed set of portfolios; it selects nothing and recommends nothing. Spec: docs/methodology/decision-helper.md.

- data: up to 2018-12-31 only (validation and holdout stay sealed)
- decision.yaml sha256: `b6ae095904f8f5eee9f75ef48e617d954953150b889d6bcfef42f6179105db23`
- core_candidates.yaml sha256: `1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3` (read unchanged)
- stress.yaml sha256: `edd4b0853cc1b9a832111e74690e0c408ef89632002e1cbcfca7594c081cc682` (read unchanged)
- multiple comparisons: 7 in the core comparison, 12 here (A-G again plus 5 new); the more portfolios compared, the likelier the best-looking one is luck
- scenarios are judgement-based, v1: owner-set what-ifs, not forecasts

## Notes

- Every portfolio is 100% of capital, rebalanced daily to its target weights, so blends look smoother than practice: real rebalancing would be less frequent.
- Costs differ by table. Withdrawal paths pay 5 bps per unit of turnover (criteria.yaml cost_bps). Historical-window cells come from `qrl.stress` unchanged: replay cells use the engine's default of 5 bps, frozen cells pay none. Scenario cells are instantaneous and carry no cost.
- Switching portfolios (A, B, C, F and blends holding A) are shown in both states, risk-on and risk-off, because their current state would need sealed data; the worse is marked.
- In the dot-com window (2000) RSP, GLD and bonds are proxied (they did not yet trade), so those cells are indicative only.
- Known gap: no portfolio holds an asset that gains from a falling dollar other than gold.
- Prices are dividend-adjusted, so totals are correct; dividend and interest income is not separated from sales.
- All figures are percentages: of capital for losses, of the starting value for withdrawal paths.

## Portfolios (100% of capital)

| id | definition | state | weights |
|---|---|---|---|
| A | current: QQQ/GLD 200d trend | risk_on | QQQ 100.0% |
| A | current: QQQ/GLD 200d trend | risk_off | GLD 100.0% |
| B | SPY/GLD 200d trend | risk_on | SPY 100.0% |
| B | SPY/GLD 200d trend | risk_off | GLD 100.0% |
| C | SPY/IEF 200d trend | risk_on | SPY 100.0% |
| C | SPY/IEF 200d trend | risk_off | IEF 100.0% |
| D | static 60/40 SPY/IEF | static | IEF 40.0%, SPY 60.0% |
| E | static SPY 60 / IEF 20 / GLD 20 | static | GLD 20.0%, IEF 20.0%, SPY 60.0% |
| F | switched mix, SPY 200d signal | risk_on | IEF 40.0%, SPY 60.0% |
| F | switched mix, SPY 200d signal | risk_off | GLD 50.0%, IEF 50.0% |
| G | static 25% each SPY/TLT/GLD/SHY | static | GLD 25.0%, SHY 25.0%, SPY 25.0%, TLT 25.0% |
| CASH | 100% SHY | static | SHY 100.0% |
| G-EW | 25% each RSP / TLT / GLD / SHY | static | GLD 25.0%, RSP 25.0%, SHY 25.0%, TLT 25.0% |
| AG | 1/2 A + 1/2 G | risk_on | GLD 12.5%, QQQ 50.0%, SHY 12.5%, SPY 12.5%, TLT 12.5% |
| AG | 1/2 A + 1/2 G | risk_off | GLD 62.5%, SHY 12.5%, SPY 12.5%, TLT 12.5% |
| G-CASH | 1/2 G + 1/2 CASH | static | GLD 12.5%, SHY 62.5%, SPY 12.5%, TLT 12.5% |
| A-CASH | 1/2 A + 1/2 CASH | risk_on | QQQ 50.0%, SHY 50.0% |
| A-CASH | 1/2 A + 1/2 CASH | risk_off | GLD 50.0%, SHY 50.0% |

## Historical windows

| portfolio | window | mode | worst drawdown | proxied (per class) | flag |
|---|---|---|---|---|---|
| A | gfc_2008 | replay | 27.8% |  |  |
| A[risk_on] | dotcom_2000 | frozen | 83.0% |  |  |
| A[risk_on] | gfc_2008 | frozen | 53.4% |  |  |
| A[risk_off] | dotcom_2000 | frozen | 0.0% | gold 100% | mostly proxied, indicative only |
| A[risk_off] | gfc_2008 | frozen | 29.4% |  |  |
| B | gfc_2008 | replay | 35.4% |  |  |
| B[risk_on] | dotcom_2000 | frozen | 47.5% |  |  |
| B[risk_on] | gfc_2008 | frozen | 55.2% |  |  |
| B[risk_off] | dotcom_2000 | frozen | 0.0% | gold 100% | mostly proxied, indicative only |
| B[risk_off] | gfc_2008 | frozen | 29.4% |  |  |
| C | gfc_2008 | replay | 13.9% |  |  |
| C[risk_on] | dotcom_2000 | frozen | 47.5% |  |  |
| C[risk_on] | gfc_2008 | frozen | 55.2% |  |  |
| C[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 100% | mostly proxied, indicative only |
| C[risk_off] | gfc_2008 | frozen | 6.2% |  |  |
| D | dotcom_2000 | frozen | 28.5% | bonds 40% | mostly proxied, indicative only |
| D | gfc_2008 | replay | 31.4% |  |  |
| D | gfc_2008 | frozen | 25.1% |  |  |
| E | dotcom_2000 | frozen | 28.5% | bonds 20%, gold 20% | mostly proxied, indicative only |
| E | gfc_2008 | replay | 31.7% |  |  |
| E | gfc_2008 | frozen | 28.0% |  |  |
| F | gfc_2008 | replay | 19.5% |  |  |
| F[risk_on] | dotcom_2000 | frozen | 28.5% | bonds 40% | mostly proxied, indicative only |
| F[risk_on] | gfc_2008 | frozen | 25.1% |  |  |
| F[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 50%, gold 50% | mostly proxied, indicative only |
| F[risk_off] | gfc_2008 | frozen | 16.5% |  |  |
| G | dotcom_2000 | frozen | 11.9% | bonds 50%, gold 25% | mostly proxied, indicative only |
| G | gfc_2008 | replay | 14.1% |  |  |
| G | gfc_2008 | frozen | 14.0% |  |  |
| CASH | dotcom_2000 | frozen | 0.0% | bonds 100% | mostly proxied, indicative only |
| CASH | gfc_2008 | replay | 2.2% |  |  |
| CASH | gfc_2008 | frozen | 2.2% |  |  |
| G-EW | dotcom_2000 | frozen | 11.9% | bonds 50%, equity 25%, gold 25% | mostly proxied, indicative only |
| G-EW | gfc_2008 | replay | 15.5% |  |  |
| G-EW | gfc_2008 | frozen | 14.8% |  |  |
| AG | gfc_2008 | replay | 20.6% |  |  |
| AG[risk_on] | dotcom_2000 | frozen | 47.4% | bonds 25%, gold 12% | mostly proxied, indicative only |
| AG[risk_on] | gfc_2008 | frozen | 30.1% |  |  |
| AG[risk_off] | dotcom_2000 | frozen | 5.9% | bonds 25%, gold 62% | mostly proxied, indicative only |
| AG[risk_off] | gfc_2008 | frozen | 22.5% |  |  |
| G-CASH | dotcom_2000 | frozen | 5.9% | bonds 75%, gold 12% | mostly proxied, indicative only |
| G-CASH | gfc_2008 | replay | 6.6% |  |  |
| G-CASH | gfc_2008 | frozen | 6.3% |  |  |
| A-CASH | gfc_2008 | replay | 13.3% |  |  |
| A-CASH[risk_on] | dotcom_2000 | frozen | 41.5% | bonds 50% | mostly proxied, indicative only |
| A-CASH[risk_on] | gfc_2008 | frozen | 23.0% |  |  |
| A-CASH[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 50%, gold 50% | mostly proxied, indicative only |
| A-CASH[risk_off] | gfc_2008 | frozen | 15.5% |  |  |

Proxies (`qrl.stress`): in a frozen cell, a fund without a price at the window start is replaced by SPY (equity) or by cash (bonds, gold). A cell more than 25% proxied is marked mostly proxied, indicative only. `dotcom_2000` starts before SHY, IEF and TLT (2002), RSP (2003) and GLD (2004): CASH is entirely cash there (0% loss by construction) and G, G-EW, G-CASH and A-CASH are mostly proxied.

Switching portfolios: the replay cell runs the rule; `[risk_on]` / `[risk_off]` frozen cells hold that state's fixed weights.

## Judgement-based scenarios (one year)

| scenario | label | GLD | IEF | QQQ | RSP | SHY | SPY | TLT | inflation |
|---|---|---|---|---|---|---|---|---|---|
| treasury_dollar_crisis | judgement-based, v1 | 25.0% | -12.0% | -30.0% | -22.0% | 1.0% | -25.0% | -30.0% | 8.0% |
| trade_oil_shock | judgement-based, v1 | 10.0% | -6.0% | -25.0% | -18.0% | 2.0% | -20.0% | -15.0% | 7.0% |
| ai_megacap_crash | judgement-based, v1 | 5.0% | 6.0% | -45.0% | -15.0% | 3.0% | -30.0% | 12.0% | 2.0% |

Loss is positive; a negative loss is a gain. Real = (1 + nominal) / (1 + inflation) - 1.

| portfolio | scenario | state | nominal loss | real loss | worse state |
|---|---|---|---|---|---|
| A | treasury_dollar_crisis | risk_on | 30.0% | 35.2% | worse |
| A | treasury_dollar_crisis | risk_off | -25.0% | -15.7% |  |
| A | trade_oil_shock | risk_on | 25.0% | 29.9% | worse |
| A | trade_oil_shock | risk_off | -10.0% | -2.8% |  |
| A | ai_megacap_crash | risk_on | 45.0% | 46.1% | worse |
| A | ai_megacap_crash | risk_off | -5.0% | -2.9% |  |
| B | treasury_dollar_crisis | risk_on | 25.0% | 30.6% | worse |
| B | treasury_dollar_crisis | risk_off | -25.0% | -15.7% |  |
| B | trade_oil_shock | risk_on | 20.0% | 25.2% | worse |
| B | trade_oil_shock | risk_off | -10.0% | -2.8% |  |
| B | ai_megacap_crash | risk_on | 30.0% | 31.4% | worse |
| B | ai_megacap_crash | risk_off | -5.0% | -2.9% |  |
| C | treasury_dollar_crisis | risk_on | 25.0% | 30.6% | worse |
| C | treasury_dollar_crisis | risk_off | 12.0% | 18.5% |  |
| C | trade_oil_shock | risk_on | 20.0% | 25.2% | worse |
| C | trade_oil_shock | risk_off | 6.0% | 12.1% |  |
| C | ai_megacap_crash | risk_on | 30.0% | 31.4% | worse |
| C | ai_megacap_crash | risk_off | -6.0% | -3.9% |  |
| D | treasury_dollar_crisis | static | 19.8% | 25.7% |  |
| D | trade_oil_shock | static | 14.4% | 20.0% |  |
| D | ai_megacap_crash | static | 15.6% | 17.3% |  |
| E | treasury_dollar_crisis | static | 12.4% | 18.9% |  |
| E | trade_oil_shock | static | 11.2% | 17.0% |  |
| E | ai_megacap_crash | static | 15.8% | 17.5% |  |
| F | treasury_dollar_crisis | risk_on | 19.8% | 25.7% | worse |
| F | treasury_dollar_crisis | risk_off | -6.5% | 1.4% |  |
| F | trade_oil_shock | risk_on | 14.4% | 20.0% | worse |
| F | trade_oil_shock | risk_off | -2.0% | 4.7% |  |
| F | ai_megacap_crash | risk_on | 15.6% | 17.3% | worse |
| F | ai_megacap_crash | risk_off | -5.5% | -3.4% |  |
| G | treasury_dollar_crisis | static | 7.2% | 14.1% |  |
| G | trade_oil_shock | static | 5.8% | 11.9% |  |
| G | ai_megacap_crash | static | 2.5% | 4.4% |  |
| CASH | treasury_dollar_crisis | static | -1.0% | 6.5% |  |
| CASH | trade_oil_shock | static | -2.0% | 4.7% |  |
| CASH | ai_megacap_crash | static | -3.0% | -1.0% |  |
| G-EW | treasury_dollar_crisis | static | 6.5% | 13.4% |  |
| G-EW | trade_oil_shock | static | 5.2% | 11.4% |  |
| G-EW | ai_megacap_crash | static | -1.3% | 0.7% |  |
| AG | treasury_dollar_crisis | risk_on | 18.6% | 24.7% | worse |
| AG | treasury_dollar_crisis | risk_off | -8.9% | -0.8% |  |
| AG | trade_oil_shock | risk_on | 15.4% | 20.9% | worse |
| AG | trade_oil_shock | risk_off | -2.1% | 4.6% |  |
| AG | ai_megacap_crash | risk_on | 23.8% | 25.2% | worse |
| AG | ai_megacap_crash | risk_off | -1.3% | 0.7% |  |
| G-CASH | treasury_dollar_crisis | static | 3.1% | 10.3% |  |
| G-CASH | trade_oil_shock | static | 1.9% | 8.3% |  |
| G-CASH | ai_megacap_crash | static | -0.3% | 1.7% |  |
| A-CASH | treasury_dollar_crisis | risk_on | 14.5% | 20.8% | worse |
| A-CASH | treasury_dollar_crisis | risk_off | -13.0% | -4.6% |  |
| A-CASH | trade_oil_shock | risk_on | 11.5% | 17.3% | worse |
| A-CASH | trade_oil_shock | risk_off | -6.0% | 0.9% |  |
| A-CASH | ai_megacap_crash | risk_on | 21.0% | 22.5% | worse |
| A-CASH | ai_megacap_crash | risk_off | -4.0% | -2.0% |  |

## Withdrawals

Paths start on the first trading day of each January 2005-2014 and end 2018-12-31. Values are percentages of the starting value. The monthly withdrawal (annual rate / 12 of the starting value) is taken on the first trading day of each month, after that day's return, proportionally from all holdings, with no extra trading cost. It changes each January by the year-over-year change of CPIAUCNS usable on 1 January (month M is usable from the last day of month M+1). Real values are deflated by the same CPI. Lowest value, max drawdown, longest time below a prior peak and below peak at end are for the 2005 path.

### Withdrawal rate 2.0% per year

| portfolio | real ending value (start 2005) | lowest value | max drawdown | longest below a prior peak | below peak at end | depleted | worst start year (real ending value) |
|---|---|---|---|---|---|---|---|
| A | 148.5% | 62.4% | 37.6% | 62 months | yes | no | 2014 (138.1%) |
| B | 152.6% | 65.4% | 39.2% | 37 months | yes | no | 2014 (142.3%) |
| C | 130.1% | 89.6% | 27.2% | 40 months | yes | no | 2014 (116.3%) |
| D | 148.6% | 78.8% | 33.4% | 39 months | yes | no | 2014 (116.2%) |
| E | 170.7% | 88.0% | 33.1% | 35 months | yes | no | 2014 (113.9%) |
| F | 139.3% | 86.3% | 20.7% | 18 months | yes | no | 2014 (121.2%) |
| G | 149.4% | 98.4% | 15.1% | 26 months | yes | no | 2013 (96.1%) |
| CASH | 72.4% | 94.6% | 15.1% | at least 120 months, not recovered | yes | no | 2009 (72.3%) |
| G-EW | 153.9% | 98.2% | 16.5% | 20 months | yes | no | 2013 (95.0%) |
| AG | 157.6% | 83.8% | 21.8% | 32 months | yes | no | 2014 (121.9%) |
| G-CASH | 105.7% | 98.7% | 7.6% | at least 29 months, not recovered | yes | no | 2012 (89.2%) |
| A-CASH | 111.9% | 81.0% | 19.0% | 49 months | yes | no | 2014 (110.8%) |

### Withdrawal rate 3.3% per year

| portfolio | real ending value (start 2005) | lowest value | max drawdown | longest below a prior peak | below peak at end | depleted | worst start year (real ending value) |
|---|---|---|---|---|---|---|---|
| A | 113.9% | 57.9% | 42.1% | 105 months | yes | no | 2005 (113.9%) |
| B | 120.1% | 61.5% | 40.7% | 42 months | yes | no | 2005 (120.1%) |
| C | 103.1% | 82.9% | 27.8% | 44 months | yes | no | 2005 (103.1%) |
| D | 121.5% | 74.2% | 34.8% | 51 months | yes | no | 2014 (109.2%) |
| E | 143.6% | 83.2% | 34.4% | 37 months | yes | no | 2014 (106.9%) |
| F | 112.2% | 81.4% | 21.6% | 27 months | yes | no | 2005 (112.2%) |
| G | 126.2% | 98.1% | 15.8% | 27 months | yes | no | 2013 (88.0%) |
| CASH | 55.1% | 72.1% | 31.5% | at least 120 months, not recovered | yes | no | 2005 (55.1%) |
| G-EW | 130.7% | 98.0% | 17.3% | 27 months | yes | no | 2013 (87.0%) |
| AG | 128.7% | 80.7% | 22.7% | 33 months | yes | no | 2014 (114.6%) |
| G-CASH | 85.7% | 98.4% | 12.1% | at least 75 months, not recovered | yes | no | 2012 (80.1%) |
| A-CASH | 87.0% | 79.2% | 20.8% | 62 months | yes | no | 2005 (87.0%) |

### Withdrawal rate 4.0% per year

| portfolio | real ending value (start 2005) | lowest value | max drawdown | longest below a prior peak | below peak at end | depleted | worst start year (real ending value) |
|---|---|---|---|---|---|---|---|
| A | 95.3% | 55.5% | 44.5% | 110 months | yes | no | 2005 (95.3%) |
| B | 102.6% | 59.4% | 41.5% | 81 months | yes | no | 2005 (102.6%) |
| C | 88.6% | 78.6% | 28.1% | 49 months | yes | no | 2005 (88.6%) |
| D | 106.9% | 71.8% | 35.7% | 58 months | yes | no | 2014 (105.4%) |
| E | 129.0% | 80.6% | 35.1% | 39 months | yes | no | 2014 (103.2%) |
| F | 97.6% | 78.8% | 22.1% | 38 months | yes | no | 2005 (97.6%) |
| G | 113.7% | 97.9% | 16.2% | 46 months | yes | no | 2013 (83.6%) |
| CASH | 45.8% | 59.9% | 41.3% | at least 129 months, not recovered | yes | no | 2005 (45.8%) |
| G-EW | 118.1% | 97.8% | 17.7% | at least 29 months, not recovered | yes | no | 2013 (82.6%) |
| AG | 113.1% | 78.0% | 23.2% | 37 months | yes | no | 2014 (110.7%) |
| G-CASH | 74.9% | 97.8% | 18.5% | at least 82 months, not recovered | yes | no | 2008 (73.9%) |
| A-CASH | 73.6% | 76.9% | 23.1% | 118 months | yes | no | 2005 (73.6%) |

### Withdrawal rate 5.0% per year

| portfolio | real ending value (start 2005) | lowest value | max drawdown | longest below a prior peak | below peak at end | depleted | worst start year (real ending value) |
|---|---|---|---|---|---|---|---|
| A | 68.7% | 52.0% | 48.0% | 156 months | yes | no | 2005 (68.7%) |
| B | 77.5% | 56.4% | 43.6% | 152 months | yes | no | 2005 (77.5%) |
| C | 67.8% | 70.4% | 30.9% | 93 months | yes | no | 2005 (67.8%) |
| D | 86.0% | 68.2% | 36.9% | 73 months | yes | no | 2005 (86.0%) |
| E | 108.1% | 77.0% | 36.2% | 42 months | yes | no | 2008 (94.3%) |
| F | 76.8% | 75.0% | 25.0% | 114 months | yes | no | 2005 (76.8%) |
| G | 95.8% | 97.6% | 16.8% | at least 75 months, not recovered | yes | no | 2012 (77.1%) |
| CASH | 32.4% | 42.4% | 57.6% | at least 167 months, not recovered | yes | no | 2005 (32.4%) |
| G-EW | 100.3% | 97.4% | 18.4% | at least 75 months, not recovered | yes | no | 2013 (76.5%) |
| AG | 90.9% | 74.1% | 25.9% | 63 months | yes | no | 2005 (90.9%) |
| G-CASH | 59.5% | 77.7% | 29.4% | at least 82 months, not recovered | yes | no | 2005 (59.5%) |
| A-CASH | 54.5% | 70.2% | 29.8% | at least 167 months, not recovered | yes | no | 2005 (54.5%) |

## Year-one scenario hit

Value after one year as a percentage of the start: (1 + the worse state's scenario return) minus the year's withdrawals at that rate (no raise in year one); nominal / real (deflated by the scenario's inflation). A negative value is shown as computed and marked depleted within year one.

### treasury_dollar_crisis

| portfolio | 2.0% nominal / real | 3.3% nominal / real | 4.0% nominal / real | 5.0% nominal / real |
|---|---|---|---|---|
| A (risk_on) | 68.0% / 63.0% | 66.7% / 61.8% | 66.0% / 61.1% | 65.0% / 60.2% |
| B (risk_on) | 73.0% / 67.6% | 71.7% / 66.4% | 71.0% / 65.7% | 70.0% / 64.8% |
| C (risk_on) | 73.0% / 67.6% | 71.7% / 66.4% | 71.0% / 65.7% | 70.0% / 64.8% |
| D | 78.2% / 72.4% | 76.9% / 71.2% | 76.2% / 70.6% | 75.2% / 69.6% |
| E | 85.6% / 79.3% | 84.3% / 78.1% | 83.6% / 77.4% | 82.6% / 76.5% |
| F (risk_on) | 78.2% / 72.4% | 76.9% / 71.2% | 76.2% / 70.6% | 75.2% / 69.6% |
| G | 90.7% / 84.0% | 89.4% / 82.8% | 88.7% / 82.2% | 87.7% / 81.2% |
| CASH | 99.0% / 91.7% | 97.7% / 90.5% | 97.0% / 89.8% | 96.0% / 88.9% |
| G-EW | 91.5% / 84.7% | 90.2% / 83.5% | 89.5% / 82.9% | 88.5% / 81.9% |
| AG (risk_on) | 79.4% / 73.5% | 78.1% / 72.3% | 77.4% / 71.6% | 76.4% / 70.7% |
| G-CASH | 94.9% / 87.8% | 93.6% / 86.6% | 92.9% / 86.0% | 91.9% / 85.1% |
| A-CASH (risk_on) | 83.5% / 77.3% | 82.2% / 76.1% | 81.5% / 75.5% | 80.5% / 74.5% |

### trade_oil_shock

| portfolio | 2.0% nominal / real | 3.3% nominal / real | 4.0% nominal / real | 5.0% nominal / real |
|---|---|---|---|---|
| A (risk_on) | 73.0% / 68.2% | 71.7% / 67.0% | 71.0% / 66.4% | 70.0% / 65.4% |
| B (risk_on) | 78.0% / 72.9% | 76.7% / 71.7% | 76.0% / 71.0% | 75.0% / 70.1% |
| C (risk_on) | 78.0% / 72.9% | 76.7% / 71.7% | 76.0% / 71.0% | 75.0% / 70.1% |
| D | 83.6% / 78.1% | 82.3% / 76.9% | 81.6% / 76.3% | 80.6% / 75.3% |
| E | 86.8% / 81.1% | 85.5% / 79.9% | 84.8% / 79.3% | 83.8% / 78.3% |
| F (risk_on) | 83.6% / 78.1% | 82.3% / 76.9% | 81.6% / 76.3% | 80.6% / 75.3% |
| G | 92.2% / 86.2% | 90.9% / 85.0% | 90.2% / 84.3% | 89.2% / 83.4% |
| CASH | 100.0% / 93.5% | 98.7% / 92.2% | 98.0% / 91.6% | 97.0% / 90.7% |
| G-EW | 92.7% / 86.7% | 91.4% / 85.5% | 90.7% / 84.8% | 89.7% / 83.9% |
| AG (risk_on) | 82.6% / 77.2% | 81.3% / 76.0% | 80.6% / 75.4% | 79.6% / 74.4% |
| G-CASH | 96.1% / 89.8% | 94.8% / 88.6% | 94.1% / 88.0% | 93.1% / 87.0% |
| A-CASH (risk_on) | 86.5% / 80.8% | 85.2% / 79.6% | 84.5% / 79.0% | 83.5% / 78.0% |

### ai_megacap_crash

| portfolio | 2.0% nominal / real | 3.3% nominal / real | 4.0% nominal / real | 5.0% nominal / real |
|---|---|---|---|---|
| A (risk_on) | 53.0% / 52.0% | 51.7% / 50.7% | 51.0% / 50.0% | 50.0% / 49.0% |
| B (risk_on) | 68.0% / 66.7% | 66.7% / 65.4% | 66.0% / 64.7% | 65.0% / 63.7% |
| C (risk_on) | 68.0% / 66.7% | 66.7% / 65.4% | 66.0% / 64.7% | 65.0% / 63.7% |
| D | 82.4% / 80.8% | 81.1% / 79.5% | 80.4% / 78.8% | 79.4% / 77.8% |
| E | 82.2% / 80.6% | 80.9% / 79.3% | 80.2% / 78.6% | 79.2% / 77.6% |
| F (risk_on) | 82.4% / 80.8% | 81.1% / 79.5% | 80.4% / 78.8% | 79.4% / 77.8% |
| G | 95.5% / 93.6% | 94.2% / 92.4% | 93.5% / 91.7% | 92.5% / 90.7% |
| CASH | 101.0% / 99.0% | 99.7% / 97.7% | 99.0% / 97.1% | 98.0% / 96.1% |
| G-EW | 99.2% / 97.3% | 97.9% / 96.0% | 97.2% / 95.3% | 96.2% / 94.4% |
| AG (risk_on) | 74.2% / 72.8% | 72.9% / 71.5% | 72.2% / 70.8% | 71.2% / 69.9% |
| G-CASH | 98.2% / 96.3% | 96.9% / 95.0% | 96.2% / 94.4% | 95.2% / 93.4% |
| A-CASH (risk_on) | 77.0% / 75.5% | 75.7% / 74.2% | 75.0% / 73.5% | 74.0% / 72.5% |
