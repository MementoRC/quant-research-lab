# Balance-sheet fragility screen (exploration only)

> Not a return signal and not a recommendation. Latest fiscal-year filings only; banks, insurers, brokers and property trusts are not applicable.

- as-of date: 2026-10-04
- membership month-end: 2026-09-30
- universe size: 300
- newest filing date seen: 2026-10-01
- config/fragility.yaml sha256: `8755cc547a1e792e2345a61844d83e26d4c9ca4349ec59c46168d9811e8d1a42`
- universe membership sha256: `4ede8b2b2ac96e975f9dc2251e4c49ed15b15f2ed52f89959759bde0c8751f9c`
- breach_to_fragile (N): 1
- min_available_for_sound (K): 4
- thresholds: interest_coverage_min 2, net_debt_to_fcf_max 6, maturities_to_liquidity_max 1, altman_z_min 1.1, piotroski_max_weak 2, rate_rise_max_pp 2

## Summary

| class | count |
| --- | --- |
| FRAGILE | 49 |
| WATCH | 0 |
| SOUND | 65 |
| INSUFFICIENT DATA | 136 |
| NOT APPLICABLE | 50 |

## Fragile and watch

| ticker | class | breached measures | fiscal year end |
| --- | --- | --- | --- |
| ADM | FRAGILE | rate +2.4 pp > 2.0 pp in 3y | 2025-12-31 |
| AEP | FRAGILE | net debt/FCF 13.9x > 6.0x; maturities 2.3x > 1.0x of liquidity | 2025-12-31 |
| AMZN | FRAGILE | net debt / FCF: FCF <= 0 with net debt > 0 | 2026-06-30 |
| AZO | FRAGILE | maturities 1.3x > 1.0x of liquidity | 2025-08-30 |
| BA | FRAGILE | coverage 1.5x < 2.0x; net debt / FCF: FCF <= 0 with net debt > 0 | 2025-12-31 |
| BE | FRAGILE | coverage 1.9x < 2.0x | 2025-12-31 |
| CAT | FRAGILE | maturities 1.3x > 1.0x of liquidity | 2025-12-31 |
| COHR | FRAGILE | net debt / FCF: FCF <= 0 with net debt > 0 | 2026-06-30 |
| CP | FRAGILE | maturities 2.1x > 1.0x of liquidity | 2025-12-31 |
| CRWV | FRAGILE | coverage -0.0x < 2.0x; net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no cash plus FCF | 2025-12-31 |
| DE | FRAGILE | maturities 1.9x > 1.0x of liquidity | 2025-11-02 |
| DUK | FRAGILE | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no cash plus FCF | 2025-12-31 |
| ECL | FRAGILE | maturities 1.1x > 1.0x of liquidity | 2025-12-31 |
| ENB | FRAGILE | net debt/FCF 31.6x > 6.0x; maturities 4.3x > 1.0x of liquidity | 2025-12-31 |
| EPD | FRAGILE | net debt/FCF 11.3x > 6.0x; maturities 1.3x > 1.0x of liquidity | 2025-12-31 |
| ET | FRAGILE | net debt/FCF 17.4x > 6.0x; maturities 2.6x > 1.0x of liquidity | 2025-12-31 |
| ETR | FRAGILE | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no cash plus FCF | 2025-12-31 |
| EXC | FRAGILE | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no cash plus FCF | 2025-12-31 |
| FIX | FRAGILE | rate +4.3 pp > 2.0 pp in 3y | 2025-12-31 |
| HPE | FRAGILE | coverage -0.4x < 2.0x; net debt/FCF 32.8x > 6.0x; maturities 1.7x > 1.0x of liquidity | 2025-10-31 |
| INTC | FRAGILE | net debt / FCF: FCF <= 0 with net debt > 0; maturities 1.0x > 1.0x of liquidity | 2025-12-27 |
| IQV | FRAGILE | net debt/FCF 6.6x > 6.0x; maturities 1.5x > 1.0x of liquidity | 2025-12-31 |
| KDP | FRAGILE | net debt/FCF 8.6x > 6.0x | 2025-12-31 |
| KMI | FRAGILE | maturities 1.4x > 1.0x of liquidity | 2025-12-31 |
| LNG | FRAGILE | net debt/FCF 8.7x > 6.0x; maturities 1.9x > 1.0x of liquidity | 2025-12-31 |
| LOW | FRAGILE | maturities 1.2x > 1.0x of liquidity | 2026-01-30 |
| MAR | FRAGILE | maturities 1.8x > 1.0x of liquidity | 2025-12-31 |
| MCD | FRAGILE | maturities 1.1x > 1.0x of liquidity | 2025-12-31 |
| MCHP | FRAGILE | net debt/FCF 6.0x > 6.0x; maturities 2.1x > 1.0x of liquidity | 2026-03-31 |
| NTRA | FRAGILE | coverage -76.2x < 2.0x | 2025-12-31 |
| OKE | FRAGILE | net debt/FCF 13.4x > 6.0x | 2025-12-31 |
| ORCL | FRAGILE | maturities 3.0x > 1.0x of liquidity | 2026-05-31 |
| ORLY | FRAGILE | maturities 1.8x > 1.0x of liquidity | 2025-12-31 |
| PEG | FRAGILE | net debt/FCF 862.0x > 6.0x; maturities 20.9x > 1.0x of liquidity | 2025-12-31 |
| PFE | FRAGILE | net debt/FCF 7.0x > 6.0x | 2025-12-31 |
| RCL | FRAGILE | maturities 4.4x > 1.0x of liquidity | 2025-12-31 |
| SNOW | FRAGILE | Altman Z'' 0.03 < 1.10 | 2026-01-31 |
| SNPS | FRAGILE | net debt/FCF 7.8x > 6.0x; maturities 1.3x > 1.0x of liquidity | 2025-10-31 |
| SO | FRAGILE | maturities due with no cash plus FCF | 2025-12-31 |
| SRE | FRAGILE | maturities due with no cash plus FCF | 2025-12-31 |
| TDG | FRAGILE | net debt/FCF 14.6x > 6.0x | 2025-09-30 |
| TEAM | FRAGILE | Altman Z'' -0.61 < 1.10 | 2026-06-30 |
| TRGP | FRAGILE | net debt/FCF 29.6x > 6.0x; maturities 2.8x > 1.0x of liquidity | 2025-12-31 |
| TTWO | FRAGILE | coverage -0.7x < 2.0x | 2026-03-31 |
| VST | FRAGILE | net debt/FCF 13.7x > 6.0x; maturities 2.6x > 1.0x of liquidity | 2025-12-31 |
| WBD | FRAGILE | net debt/FCF 9.1x > 6.0x; maturities 2.4x > 1.0x of liquidity | 2025-12-31 |
| WM | FRAGILE | maturities 1.9x > 1.0x of liquidity | 2025-12-31 |
| XEL | FRAGILE | coverage 1.8x < 2.0x; net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no cash plus FCF | 2025-12-31 |
| YUM | FRAGILE | maturities 1.6x > 1.0x of liquidity | 2025-12-31 |

## All companies

| ticker | class | fiscal year end | interest coverage | net debt / FCF | maturities / liquidity | rate trend (3y) | Altman Z'' | Piotroski F | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADM | FRAGILE | 2025-12-31 | 3.1x | 1.8x | 0.2x | +2.4 pp | n/a (missing equity, liabilities) | 6 |  |
| AEP | FRAGILE | 2025-12-31 | n/a (missing interest expense) | 13.9x | 2.3x | n/a (missing interest (latest)) | 3.98 | n/a (missing net income (current), gross profit (current), net income (prior), gross profit (prior)) |  |
| AMZN | FRAGILE | 2026-06-30 | n/a (missing EBIT, interest expense) | FCF <= 0 | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing shares (current), gross profit (current), revenue (current), shares (prior), gross profit (prior), revenue (prior)) |  |
| AZO | FRAGILE | 2025-08-30 | n/a (missing interest expense) | n/a (missing debt) | 1.3x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.28 | n/a (missing debt (current), debt (prior)) |  |
| BA | FRAGILE | 2025-12-31 | 1.5x | FCF <= 0 | 0.6x | +0.7 pp | 4.58 | 6 |  |
| BE | FRAGILE | 2025-12-31 | 1.9x | 2.9x | 0.0x | -9.4 pp | 5.26 | n/a (missing net income (current), net income (prior)) |  |
| CAT | FRAGILE | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.3x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing equity) | n/a (missing debt (current), debt (prior)) |  |
| COHR | FRAGILE | 2026-06-30 | n/a (missing EBIT, interest expense) | FCF <= 0 | 0.1x | n/a (missing interest (latest)) | n/a (missing EBIT) | 6 |  |
| CP | FRAGILE | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 2.1x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 5.44 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| CRWV | FRAGILE | 2025-12-31 | -0.0x | FCF <= 0 | no liquidity | n/a (missing fiscal years) | 1.95 | n/a (missing assets (two years back)) |  |
| DE | FRAGILE | 2025-11-02 | n/a (missing EBIT) | n/a (missing debt) | 1.9x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (current), current assets (current), current liabilities (current), gross profit (current), debt (prior), current assets (prior), current liabilities (prior), gross profit (prior)) |  |
| DUK | FRAGILE | 2025-12-31 | 2.4x | FCF <= 0 | no liquidity | +0.7 pp | 3.69 | n/a (missing gross profit (current), revenue (current), gross profit (prior), revenue (prior)) |  |
| ECL | FRAGILE | 2025-12-31 | 8.9x | n/a (missing debt) | 1.1x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.49 | n/a (missing debt (current), debt (prior)) |  |
| ENB | FRAGILE | 2025-12-31 | 2.2x | 31.6x | 4.3x | +0.8 pp | 3.46 | n/a (missing gross profit (current), gross profit (prior)) |  |
| EPD | FRAGILE | 2025-12-31 | n/a (missing interest expense) | 11.3x | 1.3x | n/a (missing interest (latest)) | n/a (missing retained earnings, equity, liabilities) | n/a (missing shares (current), shares (prior)) |  |
| ET | FRAGILE | 2025-12-31 | 2.6x | 17.4x | 2.6x | +0.7 pp | n/a (missing retained earnings, equity, liabilities) | n/a (missing shares (current), shares (prior)) |  |
| ETR | FRAGILE | 2025-12-31 | 2.3x | FCF <= 0 | no liquidity | +1.3 pp | 4.26 | n/a (missing net income (current), gross profit (current), net income (prior), gross profit (prior)) |  |
| EXC | FRAGILE | 2025-12-31 | n/a (missing interest expense) | FCF <= 0 | no liquidity | n/a (missing interest (latest), interest (3y back)) | 4.06 | n/a (missing net income (current), gross profit (current), net income (prior), gross profit (prior)) |  |
| FIX | FRAGILE | 2025-12-31 | 23.2x | net cash | 0.0x | +4.3 pp | 6.15 | 7 |  |
| HPE | FRAGILE | 2025-10-31 | -0.4x | 32.8x | 1.7x | +1.7 pp | 3.63 | n/a (missing gross profit (current), gross profit (prior)) |  |
| INTC | FRAGILE | 2025-12-27 | n/a (missing interest expense) | FCF <= 0 | 1.0x | n/a (missing interest (latest)) | 6.17 | 6 |  |
| IQV | FRAGILE | 2025-12-31 | 3.0x | 6.6x | 1.5x | +1.6 pp | 4.38 | n/a (missing gross profit (current), gross profit (prior)) |  |
| KDP | FRAGILE | 2025-12-31 | n/a (missing interest expense) | 8.6x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 4.55 | 7 |  |
| KMI | FRAGILE | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 3.90 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| LNG | FRAGILE | 2025-12-31 | n/a (missing interest expense) | 8.7x | 1.9x | n/a (missing interest (latest)) | 5.57 | n/a (missing gross profit (current), gross profit (prior)) |  |
| LOW | FRAGILE | 2026-01-30 | n/a (missing interest expense) | 5.0x | 1.2x | n/a (missing interest (latest), interest (3y back)) | 3.88 | 6 |  |
| MAR | FRAGILE | 2025-12-31 | n/a (missing interest expense) | net cash | 1.8x | n/a (missing interest (latest)) | 5.17 | n/a (missing gross profit (current), gross profit (prior)) |  |
| MCD | FRAGILE | 2025-12-31 | 7.8x | 5.5x | 1.1x | +0.7 pp | 8.45 | n/a (missing gross profit (current), gross profit (prior)) |  |
| MCHP | FRAGILE | 2026-03-31 | n/a (missing interest expense) | 6.0x | 2.1x | n/a (missing interest (latest)) | 6.01 | 6 |  |
| NTRA | FRAGILE | 2025-12-31 | -76.2x | n/a (missing debt, cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, cash) | n/a (missing debt (latest), debt (1y back)) | 4.12 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| OKE | FRAGILE | 2025-12-31 | n/a (missing interest expense) | 13.4x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 4.29 | 6 |  |
| ORCL | FRAGILE | 2026-05-31 | 4.5x | n/a (missing debt) | 3.0x | n/a (missing debt (latest), debt (1y back), debt (3y back)) | 4.05 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| ORLY | FRAGILE | 2025-12-31 | 14.7x | n/a (missing debt) | 1.8x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.34 | n/a (missing debt (current), debt (prior)) |  |
| PEG | FRAGILE | 2025-12-31 | 3.0x | 862.0x | 20.9x | +0.9 pp | n/a (missing equity, liabilities) | n/a (missing gross profit (current), gross profit (prior)) |  |
| PFE | FRAGILE | 2025-12-31 | 3.8x | 7.0x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | +0.9 pp | 6.31 | 5 |  |
| RCL | FRAGILE | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 4.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.29 | n/a (missing debt (current), debt (prior)) |  |
| SNOW | FRAGILE | 2026-01-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 0.03 | n/a (missing debt (current), debt (prior)) |  |
| SNPS | FRAGILE | 2025-10-31 | n/a (missing interest expense) | 7.8x | 1.3x | n/a (missing debt (3y back), debt (4y back), interest (latest)) | 5.88 | 3 |  |
| SO | FRAGILE | 2025-12-31 | 2.2x | n/a (missing debt) | no liquidity | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.95 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| SRE | FRAGILE | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt) | no liquidity | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | n/a (missing EBIT) | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| TDG | FRAGILE | 2025-09-30 | n/a (missing interest expense) | 14.6x | 0.5x | n/a (missing interest (latest), interest (3y back)) | 4.03 | 6 |  |
| TEAM | FRAGILE | 2026-06-30 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), interest (latest)) | -0.61 | n/a (missing debt (current), debt (prior)) |  |
| TRGP | FRAGILE | 2025-12-31 | n/a (missing interest expense) | 29.6x | 2.8x | n/a (missing interest (latest), interest (3y back)) | 4.27 | 7 |  |
| TTWO | FRAGILE | 2026-03-31 | -0.7x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back)) | 1.67 | n/a (missing debt (current), debt (prior)) |  |
| VST | FRAGILE | 2025-12-31 | n/a (missing interest expense) | 13.7x | 2.6x | n/a (missing debt (3y back), debt (4y back), interest (latest)) | 3.29 | n/a (missing gross profit (current), gross profit (prior)) |  |
| WBD | FRAGILE | 2025-12-31 | n/a (missing interest expense) | 9.1x | 2.4x | n/a (missing interest (latest)) | 3.57 | n/a (missing gross profit (current), gross profit (prior)) |  |
| WM | FRAGILE | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.9x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 5.31 | n/a (missing debt (current), debt (prior)) |  |
| XEL | FRAGILE | 2025-12-31 | 1.8x | FCF <= 0 | no liquidity | +0.8 pp | 4.09 | n/a (missing gross profit (current), revenue (current), gross profit (prior), revenue (prior)) |  |
| YUM | FRAGILE | 2025-12-31 | 4.7x | n/a (missing debt) | 1.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 2.49 | n/a (missing debt (current), debt (prior)) |  |
| A | SOUND | 2025-10-31 | 13.2x | 1.4x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | +0.3 pp | 6.73 | 5 |  |
| AAPL | SOUND | 2025-09-27 | n/a (missing interest expense) | 0.4x | 0.2x | n/a (missing interest (latest)) | 5.56 | 8 |  |
| ABBV | SOUND | 2025-12-31 | 5.2x | 3.5x | 0.7x | +1.1 pp | 2.91 | 7 |  |
| ABT | SOUND | 2025-12-31 | n/a (missing interest expense) | 0.5x | 0.3x | n/a (missing interest (latest)) | 8.05 | 5 |  |
| ADSK | SOUND | 2026-01-31 | 19.7x | net cash | 0.1x | -0.0 pp | 3.61 | 8 |  |
| AMD | SOUND | 2025-12-27 | 28.2x | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo) | -1.8 pp | 10.10 | 7 |  |
| AME | SOUND | 2025-12-31 | n/a (missing interest expense) | 1.1x | 0.4x | n/a (missing interest (latest)) | 8.66 | 5 |  |
| AMGN | SOUND | 2025-12-31 | 3.3x | 5.6x | 0.7x | +0.9 pp | 3.39 | 7 |  |
| APP | SOUND | 2025-12-31 | 20.7x | n/a (missing FCF) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, FCF) | +0.4 pp | 11.11 | 8 |  |
| AXON | SOUND | 2025-12-31 | n/a (missing interest expense) | 1.4x | 0.0x | n/a (missing debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 6.63 | 5 |  |
| CARR | SOUND | 2025-12-31 | 4.7x | 4.7x | 0.6x | +1.3 pp | n/a (missing equity) | n/a (missing gross profit (current)) |  |
| CL | SOUND | 2025-12-31 | n/a (missing interest expense) | 1.8x | 0.4x | n/a (missing interest (latest)) | 9.46 | 4 |  |
| CMG | SOUND | 2025-12-31 | no debt | no debt | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | no debt | 5.61 | n/a (missing gross profit (current), gross profit (prior)) |  |
| COR | SOUND | 2025-09-30 | n/a (missing interest expense) | 1.0x | 0.4x | n/a (missing interest (latest), interest (3y back)) | 3.30 | 6 |  |
| COST | SOUND | 2025-08-31 | 67.4x | net cash | 0.1x | +0.4 pp | 5.86 | 6 |  |
| CRH | SOUND | 2025-12-31 | n/a (missing interest expense) | 4.7x | 0.8x | n/a (missing debt (4y back), interest (latest)) | 6.81 | 6 |  |
| CRM | SOUND | 2026-01-31 | 25.7x | 0.5x | 0.4x | +0.0 pp | 5.04 | 7 |  |
| CSCO | SOUND | 2026-07-25 | n/a (missing interest expense) | 0.5x | 0.2x | n/a (missing interest (latest)) | 4.61 | 7 |  |
| CTAS | SOUND | 2026-05-31 | n/a (missing interest expense) | 0.6x | 0.6x | n/a (missing interest (latest)) | 10.69 | 8 |  |
| DELL | SOUND | 2026-01-30 | n/a (missing interest expense) | 2.3x | 0.7x | n/a (missing interest (latest)) | 3.51 | 6 |  |
| DIS | SOUND | 2025-09-27 | n/a (interest expense <= 0) | 3.6x | 0.7x | -1.1 pp | 5.83 | n/a (missing gross profit (current), gross profit (prior)) |  |
| DVN | SOUND | 2025-12-31 | 8.0x | 2.6x | 0.4x | -0.3 pp | 6.14 | n/a (missing gross profit (current), gross profit (prior)) |  |
| FCX | SOUND | 2025-12-31 | n/a (missing interest expense) | 5.0x | 0.6x | n/a (missing interest (latest), interest (3y back)) | 5.68 | 6 |  |
| FERG | SOUND | 2025-07-31 | n/a (missing interest expense) | 2.2x | 0.6x | n/a (missing fiscal years) | 7.52 | 5 |  |
| FLEX | SOUND | 2026-03-31 | 6.9x | 1.3x | 0.3x | -0.5 pp | 5.59 | 7 |  |
| FTNT | SOUND | 2025-12-31 | 103.7x | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (3y back), debt (4y back)) | 5.13 | 6 |  |
| GOOGL | SOUND | 2025-12-31 | n/a (missing interest expense) | net cash | 0.0x | n/a (missing interest (latest)) | 10.04 | 6 |  |
| HCA | SOUND | 2025-12-31 | 5.4x | 5.6x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths) | +0.4 pp | 4.12 | n/a (missing gross profit (current), gross profit (prior)) |  |
| HD | SOUND | 2026-02-01 | n/a (missing interest expense) | 3.8x | 0.8x | n/a (missing interest (latest)) | 7.79 | 4 |  |
| HON | SOUND | 2025-12-31 | 6.0x | 4.0x | 0.5x | +2.0 pp | 7.11 | 5 |  |
| HWM | SOUND | 2025-12-31 | 11.6x | 1.6x | 0.2x | +0.1 pp | 7.82 | n/a (missing gross profit (current), gross profit (prior)) |  |
| IDXX | SOUND | 2025-12-31 | n/a (missing interest expense) | 0.3x | 0.1x | n/a (missing interest (latest)) | 13.68 | 8 |  |
| INTU | SOUND | 2026-07-31 | 23.0x | 0.3x | 0.2x | -0.1 pp | 8.05 | n/a (missing gross profit (current), gross profit (prior)) |  |
| KEYS | SOUND | 2025-10-31 | 9.1x | 0.5x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | +0.0 pp | 8.40 | 5 |  |
| LIN | SOUND | 2025-12-31 | 15.5x | 4.3x | 0.6x | +0.6 pp | 5.28 | n/a (missing gross profit (current), gross profit (prior)) |  |
| LRCX | SOUND | 2026-06-28 | 52.6x | net cash | 0.1x | +0.1 pp | 14.32 | 8 |  |
| MCK | SOUND | 2026-03-31 | n/a (missing interest expense) | 0.4x | 0.3x | n/a (missing interest (latest)) | 3.83 | 6 |  |
| MCO | SOUND | 2025-12-31 | n/a (missing interest expense) | 1.8x | 0.2x | n/a (missing interest (latest), interest (3y back)) | 9.63 | 9 |  |
| META | SOUND | 2025-12-31 | 76.4x | net cash | 0.0x | n/a (missing debt (4y back)) | 8.59 | 5 |  |
| MMM | SOUND | 2025-12-31 | 10.3x | n/a (missing cash) | n/a (missing cash) | +0.7 pp | 8.71 | 5 |  |
| MO | SOUND | 2025-12-31 | n/a (missing interest expense) | 2.3x | 0.3x | n/a (missing interest (latest)) | 7.75 | 6 |  |
| MRVL | SOUND | 2026-01-31 | 7.1x | 1.7x | 0.4x | +0.6 pp | 6.68 | 7 |  |
| MSFT | SOUND | 2026-06-30 | n/a (missing interest expense) | net cash | 0.1x | n/a (missing interest (latest)) | 7.84 | 6 |  |
| MSI | SOUND | 2025-12-31 | 8.3x | 3.1x | 0.6x | +0.6 pp | 4.94 | 6 |  |
| MU | SOUND | 2025-08-28 | n/a (missing interest expense) | 1.1x | 0.0x | n/a (missing interest (latest)) | 9.32 | 7 |  |
| NOC | SOUND | 2025-12-31 | 6.8x | 3.4x | 0.4x | +0.2 pp | 5.58 | n/a (missing gross profit (current), gross profit (prior)) |  |
| NXPI | SOUND | 2025-12-31 | 6.5x | 3.2x | 0.6x | +0.4 pp | 5.51 | 4 |  |
| ONC | SOUND | 2025-12-31 | 9.0x | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | -0.0 pp | 5.03 | 8 |  |
| OXY | SOUND | 2025-12-31 | 3.9x | 4.7x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | +0.3 pp | 5.17 | n/a (missing net income (current), gross profit (current), net income (prior)) |  |
| PEP | SOUND | 2025-12-27 | 10.3x | 5.7x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | +0.0 pp | 6.13 | 5 |  |
| PH | SOUND | 2026-06-30 | n/a (missing interest expense) | 1.8x | 0.7x | n/a (missing interest (latest)) | 8.32 | 8 |  |
| QCOM | SOUND | 2025-09-28 | 18.6x | 0.4x | 0.1x | +1.1 pp | n/a (missing equity) | 6 |  |
| RSG | SOUND | 2025-12-31 | n/a (missing interest expense) | 5.7x | 0.8x | n/a (missing interest (latest)) | 5.25 | 6 |  |
| SHW | SOUND | 2025-12-31 | 9.4x | 4.0x | 1.0x | -0.1 pp | 4.34 | 6 |  |
| SNDK | SOUND | 2026-07-03 | no debt | no debt | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | no debt | 12.89 | 7 |  |
| SPGI | SOUND | 2025-12-31 | n/a (missing interest expense) | 2.1x | 0.3x | n/a (missing interest (latest)) | 6.38 | 7 |  |
| STX | SOUND | 2026-07-03 | n/a (missing interest expense) | 0.6x | 0.1x | n/a (missing interest (latest)) | 5.75 | 8 |  |
| TJX | SOUND | 2026-01-31 | 93.4x | net cash | 0.1x | +0.0 pp | 6.25 | n/a (missing gross profit (current), revenue (current), gross profit (prior), revenue (prior)) |  |
| TSLA | SOUND | 2025-12-31 | n/a (missing interest expense) | net cash | 0.1x | n/a (missing interest (latest)) | 7.71 | 5 |  |
| TT | SOUND | 2025-12-31 | 17.5x | 1.0x | 0.3x | +0.2 pp | 7.27 | n/a (missing gross profit (current), gross profit (prior)) |  |
| TXN | SOUND | 2025-12-31 | 11.1x | 3.5x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | +1.3 pp | 12.29 | 7 |  |
| VRT | SOUND | 2025-12-31 | 21.3x | 0.6x | 0.3x | -1.8 pp | 6.33 | 5 |  |
| WAT | SOUND | 2025-12-31 | 11.5x | 1.5x | 0.5x | +1.4 pp | 13.25 | 4 |  |
| WMT | SOUND | 2026-01-31 | 12.9x | 2.3x | 0.4x | +0.9 pp | 5.20 | 6 |  |
| XYZ | SOUND | 2025-12-31 | 6.7x | 0.3x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (3y back)) | 7.25 | 5 |  |
| ABNB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, FCF) | n/a (missing debt (3y back), interest (latest), interest (3y back)) | 5.35 | 6 |  |
| ADBE | INSUFFICIENT DATA | 2025-11-28 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 10.92 | 7 |  |
| ADI | INSUFFICIENT DATA | 2025-11-01 | n/a (missing interest expense) | 1.2x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 7.41 | 8 |  |
| ADP | INSUFFICIENT DATA | 2026-06-30 | 13.5x | n/a (missing debt, FCF) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.67 | n/a (missing debt (current), debt (prior)) |  |
| ALAB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing fiscal years) | 17.81 | n/a (missing debt (current), debt (prior)) |  |
| AMAT | INSUFFICIENT DATA | 2025-10-26 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (3y back), debt (4y back), interest (latest)) | 13.42 | 7 |  |
| ANET | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 11.71 | n/a (missing debt (current), debt (prior)) |  |
| APD | INSUFFICIENT DATA | 2025-09-30 | n/a (missing interest expense) | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.42 | n/a (missing operating cash flow (current), debt (current), operating cash flow (prior), debt (prior)) |  |
| APH | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.3x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 8.28 | n/a (missing debt (current), debt (prior)) |  |
| AVGO | INSUFFICIENT DATA | 2025-11-02 | n/a (missing interest expense) | 1.8x | 0.3x | n/a (missing debt (1y back), debt (3y back), interest (latest)) | n/a (missing equity) | n/a (missing net income (current), debt (prior)) |  |
| BDX | INSUFFICIENT DATA | 2025-09-30 | 4.2x | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.54 | n/a (missing operating cash flow (current), debt (current), operating cash flow (prior), debt (prior)) |  |
| BIIB | INSUFFICIENT DATA | 2025-12-31 | 6.8x | n/a (missing cash) | n/a (missing cash) | +1.0 pp | n/a (missing equity) | 4 |  |
| BKNG | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.2x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 10.89 | n/a (missing gross profit (current), gross profit (prior)) |  |
| BKR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt, cash) | n/a (missing cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing debt (current), shares (current), gross profit (current), debt (prior), shares (prior), gross profit (prior)) |  |
| BMY | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | 2.9x | 0.2x | n/a (missing interest (latest)) | n/a (missing EBIT) | 8 |  |
| BSX | INSUFFICIENT DATA | 2025-12-31 | 10.4x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.03 | n/a (missing net income (current), debt (current), net income (prior), debt (prior)) |  |
| CAH | INSUFFICIENT DATA | 2026-06-30 | 7.5x | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.03 | n/a (missing debt (current), debt (prior)) |  |
| CDNS | INSUFFICIENT DATA | 2025-12-31 | 12.8x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 9.71 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| CEG | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 4.2x | 0.3x | n/a (missing interest (latest)) | 4.79 | n/a (missing gross profit (current), gross profit (prior)) |  |
| CIEN | INSUFFICIENT DATA | 2025-11-01 | n/a (missing interest expense) | 0.3x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 5.15 | 7 |  |
| CLS | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing fiscal years) | 6.45 | n/a (missing debt (current), debt (prior)) |  |
| CMI | INSUFFICIENT DATA | 2025-12-31 | 12.2x | n/a (missing debt) | 0.1x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 8.26 | n/a (missing net income (current), debt (current), net income (prior), debt (prior)) |  |
| COP | INSUFFICIENT DATA | 2025-12-31 | 11.8x | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 7.22 | n/a (missing debt (current), debt (prior)) |  |
| CRDO | INSUFFICIENT DATA | 2026-05-02 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 19.60 | n/a (missing debt (current), debt (prior)) |  |
| CRWD | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.31 | n/a (missing debt (current), revenue (current), debt (prior), revenue (prior)) |  |
| CSX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing equity) | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| CTVA | INSUFFICIENT DATA | 2025-12-31 | 10.4x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.69 | n/a (missing debt (current), debt (prior)) |  |
| CVS | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.7x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 4.24 | n/a (missing debt (current), debt (prior)) |  |
| CVX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT) | n/a (missing debt, cash) | n/a (missing cash) | n/a (missing debt (latest), debt (1y back), debt (3y back)) | n/a (missing EBIT) | n/a (missing debt (current), debt (prior)) |  |
| D | INSUFFICIENT DATA | 2025-12-31 | 2.2x | n/a (missing FCF) | n/a (missing FCF) | n/a (missing debt (4y back)) | 3.81 | n/a (missing gross profit (current), gross profit (prior)) |  |
| DAL | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 2.3x | 0.8x | n/a (missing interest (latest), interest (3y back)) | 3.28 | n/a (missing gross profit (current), gross profit (prior)) |  |
| DASH | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 4.71 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| DHI | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (current), current assets (current), current liabilities (current), debt (prior), current assets (prior), current liabilities (prior)) |  |
| DHR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest)) | 7.71 | 5 |  |
| EBAY | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), interest (latest)) | 12.01 | n/a (missing debt (current), debt (prior)) |  |
| ED | INSUFFICIENT DATA | 2025-12-31 | 2.4x | n/a (missing FCF) | n/a (missing FCF) | +1.2 pp | 4.68 | n/a (missing gross profit (current), gross profit (prior)) |  |
| EL | INSUFFICIENT DATA | 2026-06-30 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | n/a (missing equity, liabilities) | n/a (missing debt (current), debt (prior)) |  |
| EME | INSUFFICIENT DATA | 2025-12-31 | 142.5x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 8.04 | n/a (missing debt (current), debt (prior)) |  |
| EMR | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, cash) | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | 7 |  |
| EOG | INSUFFICIENT DATA | 2025-12-31 | 27.2x | n/a (missing FCF) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, FCF) | +0.2 pp | 7.75 | n/a (missing gross profit (current), gross profit (prior)) |  |
| ETN | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | 2.6x | 0.5x | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | 6 |  |
| EW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 12.85 | n/a (missing debt (current), debt (prior)) |  |
| FANG | INSUFFICIENT DATA | 2025-12-31 | 5.2x | n/a (missing FCF) | n/a (missing FCF) | -0.5 pp | 4.72 | n/a (missing gross profit (current), gross profit (prior)) |  |
| FAST | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 15.26 | 7 |  |
| FDX | INSUFFICIENT DATA | 2026-05-31 | n/a (missing interest expense) | 2.1x | 0.3x | n/a (missing interest (latest)) | 6.18 | n/a (missing gross profit (current), gross profit (prior)) |  |
| GD | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 1.5x | 0.5x | n/a (missing interest (latest)) | 8.09 | n/a (missing gross profit (current), gross profit (prior)) |  |
| GE | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing gross profit (current), gross profit (prior)) |  |
| GEV | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, cash) | n/a (missing fiscal years) | 3.87 | n/a (missing debt (current), debt (prior)) |  |
| GILD | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, cash) | n/a (missing interest (latest)) | 6.53 | 8 |  |
| GLW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 6.85 | n/a (missing debt (current), debt (prior)) |  |
| GM | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 4.57 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| GRMN | INSUFFICIENT DATA | 2025-12-27 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 13.83 | n/a (missing debt (current), debt (prior)) |  |
| GWW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 1.4x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest), interest (3y back)) | 13.91 | 7 |  |
| HLT | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.2x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.19 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| HONA | INSUFFICIENT DATA | n/a | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | no fiscal year known (no filing, or stale) |
| IBM | INSUFFICIENT DATA | 2025-12-31 | 6.3x | n/a (missing debt) | 0.7x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 7.35 | n/a (missing debt (current), debt (prior)) |  |
| ILMN | INSUFFICIENT DATA | 2025-12-28 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 6.29 | n/a (missing debt (current), debt (prior)) |  |
| IMO | INSUFFICIENT DATA | 2025-12-31 | 356.2x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 7.02 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| ISRG | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 15.26 | n/a (missing debt (current), debt (prior)) |  |
| ITW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 2.5x | 0.9x | n/a (missing interest (latest)) | n/a (missing equity, liabilities) | n/a (missing net income (current), net income (prior)) |  |
| JCI | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing debt (3y back), debt (4y back), interest (latest)) | n/a (missing EBIT) | n/a (missing operating cash flow (current), operating cash flow (prior)) |  |
| JNJ | INSUFFICIENT DATA | 2025-12-28 | n/a (missing EBIT, interest expense) | 1.5x | 0.2x | n/a (missing interest (latest)) | n/a (missing EBIT) | 3 |  |
| KLAC | INSUFFICIENT DATA | 2026-06-30 | n/a (missing EBIT, interest expense) | 1.1x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | n/a (missing EBIT) | 7 |  |
| KO | INSUFFICIENT DATA | 2025-12-31 | 8.3x | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back)) | 7.71 | n/a (missing debt (current), debt (prior)) |  |
| KR | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | 3.6x | 0.4x | n/a (missing interest (latest)) | 5.06 | n/a (missing gross profit (current), gross profit (prior)) |  |
| KVUE | INSUFFICIENT DATA | 2025-12-28 | 5.6x | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (4y back)) | 4.46 | n/a (missing debt (current), debt (prior)) |  |
| LHX | INSUFFICIENT DATA | 2026-01-02 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 5.10 | n/a (missing debt (current), gross profit (current), revenue (current), debt (prior)) |  |
| LITE | INSUFFICIENT DATA | 2026-06-27 | n/a (missing interest expense) | 1.7x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (3y back), interest (latest)) | 3.59 | 5 |  |
| LLY | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt, FCF) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, FCF) | n/a (missing debt (latest), interest (latest)) | n/a (missing EBIT) | n/a (missing debt (current)) |  |
| LMT | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 2.5x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 5.24 | 5 |  |
| LYV | INSUFFICIENT DATA | 2025-12-31 | 4.0x | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.47 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| MDLZ | INSUFFICIENT DATA | 2025-12-31 | 5.9x | n/a (missing debt, cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.02 | n/a (missing debt (current), debt (prior)) |  |
| MDT | INSUFFICIENT DATA | 2026-04-24 | n/a (missing interest expense) | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 7.00 | n/a (missing debt (current), debt (prior)) |  |
| MELI | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.3x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest), interest (3y back)) | 5.15 | 4 |  |
| MNST | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 15.50 | n/a (missing net income (current), debt (current), net income (prior)) |  |
| MPC | INSUFFICIENT DATA | 2025-12-31 | 5.6x | n/a (missing debt) | 0.7x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.16 | n/a (missing debt (current), debt (prior)) |  |
| MPLX | INSUFFICIENT DATA | 2025-12-31 | 5.5x | n/a (missing debt) | 0.8x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing retained earnings, equity) | n/a (missing net income (current), debt (current), shares (current), gross profit (current), net income (prior), debt (prior), shares (prior), gross profit (prior)) |  |
| MPWR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 14.88 | n/a (missing debt (current), debt (prior)) |  |
| MRK | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | 2.8x | 0.3x | n/a (missing interest (latest)) | n/a (missing EBIT) | 4 |  |
| MRNA | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 8.37 | n/a (missing debt (current), debt (prior)) |  |
| MSCI | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 3.7x | 0.0x | n/a (missing interest (latest)) | 7.83 | n/a (missing gross profit (current), gross profit (prior)) |  |
| NEE | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest), interest (3y back)) | 4.16 | n/a (missing gross profit (current), revenue (current), gross profit (prior), revenue (prior)) |  |
| NEM | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | net cash | 0.0x | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing gross profit (current), gross profit (prior)) |  |
| NET | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.20 | n/a (missing debt (current), debt (prior)) |  |
| NFLX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 8.54 | n/a (missing debt (current), debt (prior)) |  |
| NOW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.43 | n/a (missing debt (prior)) |  |
| NSC | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.32 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| NTAP | INSUFFICIENT DATA | 2026-04-24 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 5.57 | 9 |  |
| NUE | INSUFFICIENT DATA | 2025-12-31 | 16.1x | n/a (missing debt) | 0.5x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 9.84 | n/a (missing debt (current), debt (prior)) |  |
| NVDA | INSUFFICIENT DATA | 2026-01-25 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 16.10 | 4 |  |
| ODFL | INSUFFICIENT DATA | 2025-12-31 | 4598.1x | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (1y back), debt (3y back), debt (4y back)) | 11.50 | n/a (missing gross profit (current), revenue (current), debt (prior), gross profit (prior), revenue (prior)) |  |
| OKTA | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.94 | n/a (missing debt (current), debt (prior)) |  |
| P | INSUFFICIENT DATA | 2026-02-01 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), interest (latest)) | 4.68 | n/a (missing debt (current)) |  |
| PANW | INSUFFICIENT DATA | 2026-07-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), interest (latest)) | 4.74 | n/a (missing debt (current), debt (prior)) |  |
| PAYX | INSUFFICIENT DATA | 2026-05-31 | n/a (missing interest expense) | 1.5x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 5.69 | 8 |  |
| PCAR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt, cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (current), current assets (current), current liabilities (current), debt (prior), current assets (prior), current liabilities (prior)) |  |
| PG | INSUFFICIENT DATA | 2026-06-30 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest)) | n/a (missing equity) | 6 |  |
| PLTR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 13.80 | n/a (missing debt (current), debt (prior)) |  |
| PM | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.0x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 6.13 | n/a (missing debt (current), debt (prior)) |  |
| PSX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT) | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing EBIT) | n/a (missing debt (current), debt (prior)) |  |
| PWR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.9x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.46 | n/a (missing debt (current), debt (prior)) |  |
| PYPL | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.2x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 6.52 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| RKLB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest), interest (3y back)) | 7.08 | 5 |  |
| ROK | INSUFFICIENT DATA | 2025-09-30 | n/a (missing interest expense) | 2.0x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 6.63 | 8 |  |
| ROP | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest)) | 6.39 | 5 |  |
| ROST | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest), interest (3y back)) | 7.29 | 6 |  |
| RTX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.6x | n/a (missing debt (latest), interest (latest)) | 5.41 | n/a (missing debt (current), gross profit (current), gross profit (prior)) |  |
| RVMD | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.24 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| SBUX | INSUFFICIENT DATA | 2025-09-28 | 5.4x | n/a (missing cash) | n/a (missing cash) | +0.2 pp | 2.23 | n/a (missing gross profit (current), gross profit (prior)) |  |
| SCCO | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.5x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo) | n/a (missing interest (latest), interest (3y back)) | 9.36 | 8 |  |
| SLB | INSUFFICIENT DATA | 2025-12-31 | 8.7x | n/a (missing debt, cash) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.48 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| SPCX | INSUFFICIENT DATA | n/a | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | no fiscal year known (no filing, or stale) |
| SYK | INSUFFICIENT DATA | 2025-12-31 | 8.4x | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing equity) | n/a (missing debt (current), debt (prior)) |  |
| SYY | INSUFFICIENT DATA | 2026-06-27 | n/a (missing interest expense) | n/a (missing debt) | 0.7x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing retained earnings) | n/a (missing debt (current), debt (prior)) |  |
| T | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 6.0x | 0.7x | n/a (missing interest (latest)) | n/a (missing equity, liabilities) | n/a (missing gross profit (current), gross profit (prior)) |  |
| TEL | INSUFFICIENT DATA | 2025-09-26 | n/a (missing interest expense) | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | n/a (missing equity) | n/a (missing debt (current), debt (prior)) |  |
| TER | INSUFFICIENT DATA | 2025-12-31 | 95.0x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 8.30 | n/a (missing debt (current), debt (prior)) |  |
| TEVA | INSUFFICIENT DATA | 2025-12-31 | 2.4x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 2.84 | n/a (missing debt (current), debt (prior)) |  |
| TGT | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest)) | 4.59 | 6 |  |
| TMO | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 4.6x | 0.6x | n/a (missing interest (latest)) | 7.26 | n/a (missing gross profit (current), gross profit (prior)) |  |
| TMUS | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 4.8x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest), interest (3y back)) | 4.51 | n/a (missing gross profit (current), gross profit (prior)) |  |
| TWLO | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, FCF) | n/a (missing interest (latest), interest (3y back)) | 6.59 | 6 |  |
| UAL | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 3.5x | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest), interest (3y back)) | 3.56 | n/a (missing gross profit (current), gross profit (prior)) |  |
| UBER | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.3x | 0.2x | n/a (missing interest (latest)) | 4.31 | n/a (missing gross profit (current), gross profit (prior)) |  |
| UI | INSUFFICIENT DATA | 2026-06-30 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), interest (latest), interest (3y back)) | 14.58 | n/a (missing debt (current)) |  |
| UNP | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 5.6x | 0.6x | n/a (missing interest (latest)) | 7.79 | n/a (missing gross profit (current), gross profit (prior)) |  |
| URI | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest), interest (3y back)) | 6.28 | 5 |  |
| VEEV | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | n/a (missing debt, FCF) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree, FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 14.46 | n/a (missing debt (current), debt (prior)) |  |
| VLO | INSUFFICIENT DATA | 2025-12-31 | 5.7x | n/a (missing FCF) | n/a (missing FCF) | +1.5 pp | 8.07 | n/a (missing gross profit (current), revenue (current), gross profit (prior), revenue (prior)) |  |
| VRTX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 10.75 | n/a (missing debt (current), debt (prior)) |  |
| VZ | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | n/a (missing equity, liabilities) | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| WAB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest), interest (3y back)) | 5.61 | 5 |  |
| WCN | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), interest (latest)) | 5.02 | n/a (missing debt (current), debt (prior)) |  |
| WDC | INSUFFICIENT DATA | 2026-07-03 | n/a (missing interest expense) | net cash | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo, LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree) | n/a (missing interest (latest)) | 10.28 | 8 |  |
| WMB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.02 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| XOM | INSUFFICIENT DATA | 2025-12-31 | 69.4x | n/a (missing debt) | n/a (missing LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 9.04 | n/a (missing debt (current), gross profit (current), debt (prior), gross profit (prior)) |  |
| AFL | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| AIG | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| AJG | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| ALL | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| AMP | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| AMT | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| AON | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| APO | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| AXP | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| BAC | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| BNY | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| BRK-B | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| BX | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| C | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| CB | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| CBRE | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| CI | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| COF | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| COIN | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| DLR | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| ELV | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| EQIX | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| FITB | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| GS | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| HIG | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| HUM | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| IAU | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| ICE | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| JPM | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| KKR | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| MET | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| MRSH | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| MS | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| MSTR | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| NDAQ | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| O | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| PGR | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| PLD | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| PNC | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| PRU | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| PSA | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| SCHW | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| STT | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| TFC | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| TRV | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| UNH | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| USB | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| VTR | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| WELL | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
| WFC | NOT APPLICABLE | n/a | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | financial firm |
