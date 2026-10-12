# Decision helper: portfolios, scenarios and withdrawals

A decision aid for deploying savings while withdrawing for income. It compares a fixed set of portfolios; it selects nothing and recommends nothing. Spec: docs/methodology/decision-helper.md.

- data: up to 2018-12-31 only (validation and holdout stay sealed)
- decision.yaml sha256: `7b0d96a47a16f44562286358d05b6b90749d05c1b9ced8f73ad86323dc026774`
- core_candidates.yaml sha256: `1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3` (read unchanged)
- stress.yaml sha256: `edd4b0853cc1b9a832111e74690e0c408ef89632002e1cbcfca7594c081cc682` (read unchanged)
- multiple comparisons: 7 in the core comparison, 22 here (A-G again plus 15 new); the more portfolios compared, the likelier the best-looking one is luck
- of the 21 portfolios here, 4 are by-product rows, each a sleeve held alone (IEF, TLT, RSP, BONDS); only the 5 A80 rows (A80-CASH20, A80-IEF20, A80-TLT20, A80-BONDS20, A80-RSP20) answer the defensive-sleeve question (docs/methodology/defensive-sleeve.md)
- CASH here is SHY, not true cash: SHY's near-zero 2009-2015 yields make the A80-CASH20 baseline look worse than cash at today's rates
- A80-TCASH20 (80% A + 20% cash at +1% real (assumption)) is an assumption row, not a fund: 20.0% cash earning each month's inflation plus 1.0% a year, the long-run report's CASH +1% real assumption, shown to answer the SHY caveat above. It is comparison 22 but not one of the 21 portfolios. Its cash leg and its daily return to 80/20 pay no trading cost, while A80-CASH20 pays 5 bps per unit of turnover on its rebalancing, a small difference in the assumption row's favour.
- scenarios are judgement-based, v1: owner-set what-ifs, not forecasts

## Notes

- Every portfolio is 100% of capital, rebalanced daily to its target weights, so blends look smoother than practice: real rebalancing would be less frequent.
- Costs differ by table. Withdrawal paths pay 5 bps per unit of turnover (criteria.yaml cost_bps). Historical-window cells come from `qrl.stress` unchanged: replay cells use the engine's default of 5 bps, frozen cells pay none. Scenario cells are instantaneous and carry no cost.
- Switching portfolios (A, B, C, F and blends holding A) are shown in both states, risk-on and risk-off, because their current state would need sealed data; the worse is marked.
- In the dot-com window (2000) RSP, GLD and bonds are proxied (they did not yet trade), so those cells are indicative only.
- Known gap: no portfolio holds an asset that gains from a falling dollar other than gold.
- Prices are dividend-adjusted, so totals are correct; dividend and interest income is not separated from sales.
- All figures are percentages: of capital for losses, of the starting value for withdrawal paths.
- A80-TCASH20 appears only in the research-period return and withdrawal tables: the historical windows and the judgement-based scenarios have no cash return to give it. In `dotcom_2000` SHY is already replaced by cash at 0%, so the row would equal A80-CASH20 there; in `gfc_2008` A80-CASH20 uses SHY's actual prices; the scenarios set SHY's one-year return by judgement and set none for cash; the year-one table is built from the scenarios.

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
| IEF | 100% IEF | static | IEF 100.0% |
| TLT | 100% TLT | static | TLT 100.0% |
| RSP | 100% RSP | static | RSP 100.0% |
| BONDS | 1/3 each SHY / IEF / TLT | static | IEF 33.3%, SHY 33.3%, TLT 33.3% |
| AG | 1/2 A + 1/2 G | risk_on | GLD 12.5%, QQQ 50.0%, SHY 12.5%, SPY 12.5%, TLT 12.5% |
| AG | 1/2 A + 1/2 G | risk_off | GLD 62.5%, SHY 12.5%, SPY 12.5%, TLT 12.5% |
| G-CASH | 1/2 G + 1/2 CASH | static | GLD 12.5%, SHY 62.5%, SPY 12.5%, TLT 12.5% |
| A-CASH | 1/2 A + 1/2 CASH | risk_on | QQQ 50.0%, SHY 50.0% |
| A-CASH | 1/2 A + 1/2 CASH | risk_off | GLD 50.0%, SHY 50.0% |
| A80-CASH20 | 80% A + 20% CASH | risk_on | QQQ 80.0%, SHY 20.0% |
| A80-CASH20 | 80% A + 20% CASH | risk_off | GLD 80.0%, SHY 20.0% |
| A80-IEF20 | 80% A + 20% IEF | risk_on | IEF 20.0%, QQQ 80.0% |
| A80-IEF20 | 80% A + 20% IEF | risk_off | GLD 80.0%, IEF 20.0% |
| A80-TLT20 | 80% A + 20% TLT | risk_on | QQQ 80.0%, TLT 20.0% |
| A80-TLT20 | 80% A + 20% TLT | risk_off | GLD 80.0%, TLT 20.0% |
| A80-BONDS20 | 80% A + 20% BONDS | risk_on | IEF 6.7%, QQQ 80.0%, SHY 6.7%, TLT 6.7% |
| A80-BONDS20 | 80% A + 20% BONDS | risk_off | GLD 80.0%, IEF 6.7%, SHY 6.7%, TLT 6.7% |
| A80-RSP20 | 80% A + 20% RSP | risk_on | QQQ 80.0%, RSP 20.0% |
| A80-RSP20 | 80% A + 20% RSP | risk_off | GLD 80.0%, RSP 20.0% |

## Research-period return (2005-2018, no withdrawals)

Each portfolio bought on the first trading day of the research period and held to 2018-12-31 with no withdrawals, paying 5 bps per unit of turnover. Max drawdown is a positive loss. CAGR given up vs A is A's CAGR minus the row's, in percentage points (pp); negative means the row earned more than A, n/a means A is not in the report.

| Portfolio | CAGR | Max drawdown | CAGR given up vs A |
|---|---|---|---|
| A | 7.3% | 31.2% | 0.0 pp |
| B | 7.3% | 37.2% | 0.0 pp |
| C | 6.0% | 26.5% | 1.2 pp |
| D | 6.8% | 31.4% | 0.4 pp |
| E | 7.7% | 31.7% | -0.4 pp |
| F | 6.4% | 19.5% | 0.8 pp |
| G | 6.6% | 14.1% | 0.7 pp |
| CASH | 1.9% | 2.2% | 5.3 pp |
| G-EW | 6.8% | 15.5% | 0.5 pp |
| IEF | 4.4% | 10.4% | 2.9 pp |
| TLT | 5.9% | 26.6% | 1.3 pp |
| RSP | 7.8% | 59.9% | -0.6 pp |
| BONDS | 4.2% | 13.2% | 3.0 pp |
| AG | 7.3% | 20.6% | 0.0 pp |
| G-CASH | 4.3% | 6.6% | 3.0 pp |
| A-CASH | 5.0% | 15.7% | 2.2 pp |
| A80-CASH20 | 6.5% | 25.3% | 0.8 pp |
| A80-IEF20 | 7.0% | 25.6% | 0.2 pp |
| A80-TLT20 | 7.5% | 25.3% | -0.2 pp |
| A80-BONDS20 | 7.0% | 25.4% | 0.3 pp |
| A80-RSP20 | 7.7% | 29.8% | -0.5 pp |
| A80-TCASH20 | 6.7% | 24.6% | 0.6 pp |

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
| IEF | dotcom_2000 | frozen | 0.0% | bonds 100% | mostly proxied, indicative only |
| IEF | gfc_2008 | replay | 6.2% |  |  |
| IEF | gfc_2008 | frozen | 6.2% |  |  |
| TLT | dotcom_2000 | frozen | 0.0% | bonds 100% | mostly proxied, indicative only |
| TLT | gfc_2008 | replay | 16.2% |  |  |
| TLT | gfc_2008 | frozen | 16.2% |  |  |
| RSP | dotcom_2000 | frozen | 47.5% | equity 100% | mostly proxied, indicative only |
| RSP | gfc_2008 | replay | 59.2% |  |  |
| RSP | gfc_2008 | frozen | 59.2% |  |  |
| BONDS | dotcom_2000 | frozen | 0.0% | bonds 100% | mostly proxied, indicative only |
| BONDS | gfc_2008 | replay | 7.6% |  |  |
| BONDS | gfc_2008 | frozen | 8.2% |  |  |
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
| A80-CASH20 | gfc_2008 | replay | 22.1% |  |  |
| A80-CASH20[risk_on] | dotcom_2000 | frozen | 66.4% | bonds 20% |  |
| A80-CASH20[risk_on] | gfc_2008 | frozen | 41.3% |  |  |
| A80-CASH20[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 20%, gold 80% | mostly proxied, indicative only |
| A80-CASH20[risk_off] | gfc_2008 | frozen | 24.2% |  |  |
| A80-IEF20 | gfc_2008 | replay | 22.4% |  |  |
| A80-IEF20[risk_on] | dotcom_2000 | frozen | 66.4% | bonds 20% |  |
| A80-IEF20[risk_on] | gfc_2008 | frozen | 39.7% |  |  |
| A80-IEF20[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 20%, gold 80% | mostly proxied, indicative only |
| A80-IEF20[risk_off] | gfc_2008 | frozen | 24.4% |  |  |
| A80-TLT20 | gfc_2008 | replay | 21.9% |  |  |
| A80-TLT20[risk_on] | dotcom_2000 | frozen | 66.4% | bonds 20% |  |
| A80-TLT20[risk_on] | gfc_2008 | frozen | 38.5% |  |  |
| A80-TLT20[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 20%, gold 80% | mostly proxied, indicative only |
| A80-TLT20[risk_off] | gfc_2008 | frozen | 23.9% |  |  |
| A80-BONDS20 | gfc_2008 | replay | 22.2% |  |  |
| A80-BONDS20[risk_on] | dotcom_2000 | frozen | 66.4% | bonds 20% |  |
| A80-BONDS20[risk_on] | gfc_2008 | frozen | 39.8% |  |  |
| A80-BONDS20[risk_off] | dotcom_2000 | frozen | 0.0% | bonds 20%, gold 80% | mostly proxied, indicative only |
| A80-BONDS20[risk_off] | gfc_2008 | frozen | 24.2% |  |  |
| A80-RSP20 | gfc_2008 | replay | 29.8% |  |  |
| A80-RSP20[risk_on] | dotcom_2000 | frozen | 75.9% | equity 20% |  |
| A80-RSP20[risk_on] | gfc_2008 | frozen | 54.0% |  |  |
| A80-RSP20[risk_off] | dotcom_2000 | frozen | 9.5% | equity 20%, gold 80% | mostly proxied, indicative only |
| A80-RSP20[risk_off] | gfc_2008 | frozen | 30.4% |  |  |

Proxies (`qrl.stress`): in a frozen cell, a fund without a price at the window start is replaced by SPY (equity) or by cash (bonds, gold). A cell more than 25% proxied is marked mostly proxied, indicative only. `dotcom_2000` starts before SHY, IEF and TLT (2002), RSP (2003) and GLD (2004): CASH is entirely cash there (0% loss by construction) and G, G-EW, G-CASH and A-CASH are mostly proxied. IEF, TLT and BONDS are, like CASH, entirely cash in `dotcom_2000` (0% loss), so the A80-CASH20, A80-IEF20, A80-TLT20 and A80-BONDS20 frozen cells are identical there and that window cannot tell the bond sleeves apart; A80-RSP20 uses the SPY proxy.

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
| IEF | treasury_dollar_crisis | static | 12.0% | 18.5% |  |
| IEF | trade_oil_shock | static | 6.0% | 12.1% |  |
| IEF | ai_megacap_crash | static | -6.0% | -3.9% |  |
| TLT | treasury_dollar_crisis | static | 30.0% | 35.2% |  |
| TLT | trade_oil_shock | static | 15.0% | 20.6% |  |
| TLT | ai_megacap_crash | static | -12.0% | -9.8% |  |
| RSP | treasury_dollar_crisis | static | 22.0% | 27.8% |  |
| RSP | trade_oil_shock | static | 18.0% | 23.4% |  |
| RSP | ai_megacap_crash | static | 15.0% | 16.7% |  |
| BONDS | treasury_dollar_crisis | static | 13.7% | 20.1% |  |
| BONDS | trade_oil_shock | static | 6.3% | 12.5% |  |
| BONDS | ai_megacap_crash | static | -7.0% | -4.9% |  |
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
| A80-CASH20 | treasury_dollar_crisis | risk_on | 23.8% | 29.4% | worse |
| A80-CASH20 | treasury_dollar_crisis | risk_off | -20.2% | -11.3% |  |
| A80-CASH20 | trade_oil_shock | risk_on | 19.6% | 24.9% | worse |
| A80-CASH20 | trade_oil_shock | risk_off | -8.4% | -1.3% |  |
| A80-CASH20 | ai_megacap_crash | risk_on | 35.4% | 36.7% | worse |
| A80-CASH20 | ai_megacap_crash | risk_off | -4.6% | -2.5% |  |
| A80-IEF20 | treasury_dollar_crisis | risk_on | 26.4% | 31.9% | worse |
| A80-IEF20 | treasury_dollar_crisis | risk_off | -17.6% | -8.9% |  |
| A80-IEF20 | trade_oil_shock | risk_on | 21.2% | 26.4% | worse |
| A80-IEF20 | trade_oil_shock | risk_off | -6.8% | 0.2% |  |
| A80-IEF20 | ai_megacap_crash | risk_on | 34.8% | 36.1% | worse |
| A80-IEF20 | ai_megacap_crash | risk_off | -5.2% | -3.1% |  |
| A80-TLT20 | treasury_dollar_crisis | risk_on | 30.0% | 35.2% | worse |
| A80-TLT20 | treasury_dollar_crisis | risk_off | -14.0% | -5.6% |  |
| A80-TLT20 | trade_oil_shock | risk_on | 23.0% | 28.0% | worse |
| A80-TLT20 | trade_oil_shock | risk_off | -5.0% | 1.9% |  |
| A80-TLT20 | ai_megacap_crash | risk_on | 33.6% | 34.9% | worse |
| A80-TLT20 | ai_megacap_crash | risk_off | -6.4% | -4.3% |  |
| A80-BONDS20 | treasury_dollar_crisis | risk_on | 26.7% | 32.2% | worse |
| A80-BONDS20 | treasury_dollar_crisis | risk_off | -17.3% | -8.6% |  |
| A80-BONDS20 | trade_oil_shock | risk_on | 21.3% | 26.4% | worse |
| A80-BONDS20 | trade_oil_shock | risk_off | -6.7% | 0.2% |  |
| A80-BONDS20 | ai_megacap_crash | risk_on | 34.6% | 35.9% | worse |
| A80-BONDS20 | ai_megacap_crash | risk_off | -5.4% | -3.3% |  |
| A80-RSP20 | treasury_dollar_crisis | risk_on | 28.4% | 33.7% | worse |
| A80-RSP20 | treasury_dollar_crisis | risk_off | -15.6% | -7.0% |  |
| A80-RSP20 | trade_oil_shock | risk_on | 23.6% | 28.6% | worse |
| A80-RSP20 | trade_oil_shock | risk_off | -4.4% | 2.4% |  |
| A80-RSP20 | ai_megacap_crash | risk_on | 39.0% | 40.2% | worse |
| A80-RSP20 | ai_megacap_crash | risk_off | -1.0% | 1.0% |  |

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
| IEF | 106.8% | 96.2% | 12.1% | 30 months | yes | no | 2013 (87.9%) |
| TLT | 133.9% | 96.8% | 27.2% | 33 months | yes | no | 2009 (92.7%) |
| RSP | 169.9% | 50.7% | 61.4% | 66 months | yes | no | 2014 (118.0%) |
| BONDS | 103.9% | 97.5% | 14.0% | 32 months | yes | no | 2009 (86.5%) |
| AG | 157.6% | 83.8% | 21.8% | 32 months | yes | no | 2014 (121.9%) |
| G-CASH | 105.7% | 98.7% | 7.6% | at least 29 months, not recovered | yes | no | 2012 (89.2%) |
| A-CASH | 111.9% | 81.0% | 19.0% | 49 months | yes | no | 2014 (110.8%) |
| A80-CASH20 | 135.0% | 71.0% | 29.0% | 59 months | yes | no | 2014 (127.0%) |
| A80-IEF20 | 147.1% | 71.0% | 29.0% | 58 months | yes | no | 2014 (130.4%) |
| A80-TLT20 | 157.5% | 71.4% | 28.6% | 57 months | yes | no | 2014 (135.9%) |
| A80-BONDS20 | 146.4% | 71.3% | 28.7% | 58 months | yes | no | 2014 (131.1%) |
| A80-RSP20 | 162.0% | 64.3% | 35.7% | 59 months | yes | no | 2014 (134.7%) |
| A80-TCASH20 | 139.3% | 70.9% | 29.1% | 59 months | yes | no | 2014 (129.5%) |

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
| IEF | 86.5% | 94.2% | 17.4% | at least 77 months, not recovered | yes | no | 2009 (77.9%) |
| TLT | 111.0% | 95.0% | 27.9% | 33 months | yes | no | 2009 (78.0%) |
| RSP | 138.9% | 47.7% | 62.5% | 69 months | yes | no | 2014 (111.1%) |
| BONDS | 83.6% | 95.7% | 18.0% | at least 77 months, not recovered | yes | no | 2009 (73.0%) |
| AG | 128.7% | 80.7% | 22.7% | 33 months | yes | no | 2014 (114.6%) |
| G-CASH | 85.7% | 98.4% | 12.1% | at least 75 months, not recovered | yes | no | 2012 (80.1%) |
| A-CASH | 87.0% | 79.2% | 20.8% | 62 months | yes | no | 2005 (87.0%) |
| A80-CASH20 | 104.5% | 66.2% | 33.8% | 104 months | yes | no | 2005 (104.5%) |
| A80-IEF20 | 115.3% | 66.8% | 33.2% | 63 months | yes | no | 2005 (115.3%) |
| A80-TLT20 | 124.5% | 67.7% | 32.3% | 63 months | yes | no | 2005 (124.5%) |
| A80-BONDS20 | 114.7% | 66.9% | 33.1% | 63 months | yes | no | 2005 (114.7%) |
| A80-RSP20 | 127.5% | 60.0% | 40.0% | 63 months | yes | no | 2014 (127.0%) |
| A80-TCASH20 | 108.1% | 66.1% | 33.9% | 103 months | yes | no | 2005 (108.1%) |

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
| IEF | 75.5% | 93.2% | 23.1% | at least 77 months, not recovered | yes | no | 2009 (70.6%) |
| TLT | 98.7% | 94.1% | 28.6% | 33 months | yes | no | 2009 (70.0%) |
| RSP | 122.2% | 46.0% | 63.1% | 73 months | yes | no | 2007 (106.1%) |
| BONDS | 72.7% | 91.9% | 23.9% | at least 77 months, not recovered | yes | no | 2009 (65.8%) |
| AG | 113.1% | 78.0% | 23.2% | 37 months | yes | no | 2014 (110.7%) |
| G-CASH | 74.9% | 97.8% | 18.5% | at least 82 months, not recovered | yes | no | 2008 (73.9%) |
| A-CASH | 73.6% | 76.9% | 23.1% | 118 months | yes | no | 2005 (73.6%) |
| A80-CASH20 | 88.1% | 63.7% | 36.3% | 109 months | yes | no | 2005 (88.1%) |
| A80-IEF20 | 98.2% | 64.2% | 35.8% | 105 months | yes | no | 2005 (98.2%) |
| A80-TLT20 | 106.8% | 65.0% | 35.0% | 79 months | yes | no | 2005 (106.8%) |
| A80-BONDS20 | 97.6% | 64.3% | 35.7% | 105 months | yes | no | 2005 (97.6%) |
| A80-RSP20 | 108.9% | 57.7% | 42.3% | 104 months | yes | no | 2005 (108.9%) |
| A80-TCASH20 | 91.3% | 63.6% | 36.4% | 109 months | yes | no | 2005 (91.3%) |

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
| IEF | 59.8% | 75.8% | 32.7% | at least 77 months, not recovered | yes | no | 2005 (59.8%) |
| TLT | 81.0% | 91.7% | 30.1% | at least 77 months, not recovered | yes | no | 2009 (58.7%) |
| RSP | 98.4% | 43.7% | 64.1% | 83 months | yes | no | 2007 (86.4%) |
| BONDS | 57.2% | 72.5% | 36.4% | at least 120 months, not recovered | yes | no | 2009 (55.4%) |
| AG | 90.9% | 74.1% | 25.9% | 63 months | yes | no | 2005 (90.9%) |
| G-CASH | 59.5% | 77.7% | 29.4% | at least 82 months, not recovered | yes | no | 2005 (59.5%) |
| A-CASH | 54.5% | 70.2% | 29.8% | at least 167 months, not recovered | yes | no | 2005 (54.5%) |
| A80-CASH20 | 64.7% | 60.0% | 40.0% | at least 167 months, not recovered | yes | no | 2005 (64.7%) |
| A80-IEF20 | 73.8% | 60.5% | 39.5% | 121 months | yes | no | 2005 (73.8%) |
| A80-TLT20 | 81.4% | 61.3% | 38.7% | 115 months | yes | no | 2005 (81.4%) |
| A80-BONDS20 | 73.2% | 60.6% | 39.4% | 121 months | yes | no | 2005 (73.2%) |
| A80-RSP20 | 82.4% | 54.4% | 45.6% | 114 months | yes | no | 2005 (82.4%) |
| A80-TCASH20 | 67.4% | 59.9% | 40.1% | 162 months | yes | no | 2005 (67.4%) |

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
| IEF | 86.0% / 79.6% | 84.7% / 78.4% | 84.0% / 77.8% | 83.0% / 76.9% |
| TLT | 68.0% / 63.0% | 66.7% / 61.8% | 66.0% / 61.1% | 65.0% / 60.2% |
| RSP | 76.0% / 70.4% | 74.7% / 69.2% | 74.0% / 68.5% | 73.0% / 67.6% |
| BONDS | 84.3% / 78.1% | 83.0% / 76.9% | 82.3% / 76.2% | 81.3% / 75.3% |
| AG (risk_on) | 79.4% / 73.5% | 78.1% / 72.3% | 77.4% / 71.6% | 76.4% / 70.7% |
| G-CASH | 94.9% / 87.8% | 93.6% / 86.6% | 92.9% / 86.0% | 91.9% / 85.1% |
| A-CASH (risk_on) | 83.5% / 77.3% | 82.2% / 76.1% | 81.5% / 75.5% | 80.5% / 74.5% |
| A80-CASH20 (risk_on) | 74.2% / 68.7% | 72.9% / 67.5% | 72.2% / 66.9% | 71.2% / 65.9% |
| A80-IEF20 (risk_on) | 71.6% / 66.3% | 70.3% / 65.1% | 69.6% / 64.4% | 68.6% / 63.5% |
| A80-TLT20 (risk_on) | 68.0% / 63.0% | 66.7% / 61.8% | 66.0% / 61.1% | 65.0% / 60.2% |
| A80-BONDS20 (risk_on) | 71.3% / 66.0% | 70.0% / 64.8% | 69.3% / 64.1% | 68.3% / 63.2% |
| A80-RSP20 (risk_on) | 69.6% / 64.4% | 68.3% / 63.2% | 67.6% / 62.6% | 66.6% / 61.7% |

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
| IEF | 92.0% / 86.0% | 90.7% / 84.8% | 90.0% / 84.1% | 89.0% / 83.2% |
| TLT | 83.0% / 77.6% | 81.7% / 76.4% | 81.0% / 75.7% | 80.0% / 74.8% |
| RSP | 80.0% / 74.8% | 78.7% / 73.6% | 78.0% / 72.9% | 77.0% / 72.0% |
| BONDS | 91.7% / 85.7% | 90.4% / 84.5% | 89.7% / 83.8% | 88.7% / 82.9% |
| AG (risk_on) | 82.6% / 77.2% | 81.3% / 76.0% | 80.6% / 75.4% | 79.6% / 74.4% |
| G-CASH | 96.1% / 89.8% | 94.8% / 88.6% | 94.1% / 88.0% | 93.1% / 87.0% |
| A-CASH (risk_on) | 86.5% / 80.8% | 85.2% / 79.6% | 84.5% / 79.0% | 83.5% / 78.0% |
| A80-CASH20 (risk_on) | 78.4% / 73.3% | 77.1% / 72.1% | 76.4% / 71.4% | 75.4% / 70.5% |
| A80-IEF20 (risk_on) | 76.8% / 71.8% | 75.5% / 70.6% | 74.8% / 69.9% | 73.8% / 69.0% |
| A80-TLT20 (risk_on) | 75.0% / 70.1% | 73.7% / 68.9% | 73.0% / 68.2% | 72.0% / 67.3% |
| A80-BONDS20 (risk_on) | 76.7% / 71.7% | 75.4% / 70.5% | 74.7% / 69.8% | 73.7% / 68.9% |
| A80-RSP20 (risk_on) | 74.4% / 69.5% | 73.1% / 68.3% | 72.4% / 67.7% | 71.4% / 66.7% |

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
| IEF | 104.0% / 102.0% | 102.7% / 100.7% | 102.0% / 100.0% | 101.0% / 99.0% |
| TLT | 110.0% / 107.8% | 108.7% / 106.6% | 108.0% / 105.9% | 107.0% / 104.9% |
| RSP | 83.0% / 81.4% | 81.7% / 80.1% | 81.0% / 79.4% | 80.0% / 78.4% |
| BONDS | 105.0% / 102.9% | 103.7% / 101.7% | 103.0% / 101.0% | 102.0% / 100.0% |
| AG (risk_on) | 74.2% / 72.8% | 72.9% / 71.5% | 72.2% / 70.8% | 71.2% / 69.9% |
| G-CASH | 98.2% / 96.3% | 96.9% / 95.0% | 96.2% / 94.4% | 95.2% / 93.4% |
| A-CASH (risk_on) | 77.0% / 75.5% | 75.7% / 74.2% | 75.0% / 73.5% | 74.0% / 72.5% |
| A80-CASH20 (risk_on) | 62.6% / 61.4% | 61.3% / 60.1% | 60.6% / 59.4% | 59.6% / 58.4% |
| A80-IEF20 (risk_on) | 63.2% / 62.0% | 61.9% / 60.7% | 61.2% / 60.0% | 60.2% / 59.0% |
| A80-TLT20 (risk_on) | 64.4% / 63.1% | 63.1% / 61.9% | 62.4% / 61.2% | 61.4% / 60.2% |
| A80-BONDS20 (risk_on) | 63.4% / 62.2% | 62.1% / 60.9% | 61.4% / 60.2% | 60.4% / 59.2% |
| A80-RSP20 (risk_on) | 59.0% / 57.8% | 57.7% / 56.6% | 57.0% / 55.9% | 56.0% / 54.9% |
