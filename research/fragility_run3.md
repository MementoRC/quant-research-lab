# Balance-sheet fragility screen (exploration only)

> Not a return signal and not a recommendation. Latest fiscal-year filings only; banks, insurers, brokers and property trusts are not applicable.

- as-of date: 2026-10-04
- membership month-end: 2026-09-30
- universe size: 300
- newest filing date seen: 2026-10-01
- config/fragility.yaml sha256: `78ce098ed0737a503b628b08ecd45917cb6165bc8c001ae0a628e990c3bd8297`
- universe membership sha256: `4ede8b2b2ac96e975f9dc2251e4c49ed15b15f2ed52f89959759bde0c8751f9c`
- breach_to_fragile (N): 2
- min_available_for_sound (K): 4
- thresholds: interest_coverage_min 2, net_debt_to_fcf_max 6, maturities_to_liquidity_max 1, altman_z_min 1.1, piotroski_max_weak 2, rate_rise_max_pp 2

## Summary

| class | count |
| --- | --- |
| FRAGILE | 4 |
| WATCH | 44 |
| SOUND | 66 |
| INSUFFICIENT DATA | 136 |
| NOT APPLICABLE | 50 |

## Fragile and watch

| ticker | class | breached measures | fiscal year end |
| --- | --- | --- | --- |
| BA | FRAGILE | coverage 1.5x < 2.0x; net debt / FCF: FCF <= 0 with net debt > 0 | 2025-12-31 |
| CRWV | FRAGILE | coverage -0.04x < 2.00x; net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| HPE | FRAGILE | coverage -0.4x < 2.0x; net debt / FCF 32.8x > 6.0x; maturities 1.7x > 1.0x of liquidity | 2025-10-31 |
| XEL | FRAGILE | coverage 1.8x < 2.0x; net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| ADM | WATCH | rate +2.4 pp > 2.0 pp in 3y | 2025-12-31 |
| AEP | WATCH | net debt / FCF 13.9x > 6.0x; maturities 2.3x > 1.0x of liquidity | 2025-12-31 |
| AZO | WATCH | maturities 1.3x > 1.0x of liquidity | 2025-08-30 |
| BE | WATCH | coverage 1.9x < 2.0x | 2025-12-31 |
| CAT | WATCH | maturities 1.3x > 1.0x of liquidity | 2025-12-31 |
| COHR | WATCH | net debt / FCF: FCF <= 0 with net debt > 0 | 2026-06-30 |
| CP | WATCH | maturities 2.1x > 1.0x of liquidity | 2025-12-31 |
| DE | WATCH | maturities 1.9x > 1.0x of liquidity | 2025-11-02 |
| DUK | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| ECL | WATCH | maturities 1.1x > 1.0x of liquidity | 2025-12-31 |
| ENB | WATCH | net debt / FCF 31.6x > 6.0x; maturities 4.3x > 1.0x of liquidity | 2025-12-31 |
| EPD | WATCH | net debt / FCF 11.3x > 6.0x; maturities 1.3x > 1.0x of liquidity | 2025-12-31 |
| ET | WATCH | net debt / FCF 17.4x > 6.0x; maturities 2.6x > 1.0x of liquidity | 2025-12-31 |
| ETR | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| EXC | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| FIX | WATCH | rate +4.3 pp > 2.0 pp in 3y | 2025-12-31 |
| INTC | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities 1.02x > 1.00x of liquidity | 2025-12-27 |
| IQV | WATCH | net debt / FCF 6.6x > 6.0x; maturities 1.5x > 1.0x of liquidity | 2025-12-31 |
| KDP | WATCH | net debt / FCF 8.6x > 6.0x | 2025-12-31 |
| KMI | WATCH | maturities 1.4x > 1.0x of liquidity | 2025-12-31 |
| LNG | WATCH | net debt / FCF 8.7x > 6.0x; maturities 1.9x > 1.0x of liquidity | 2025-12-31 |
| LOW | WATCH | maturities 1.2x > 1.0x of liquidity | 2026-01-30 |
| MAR | WATCH | maturities 1.8x > 1.0x of liquidity | 2025-12-31 |
| MCD | WATCH | maturities 1.1x > 1.0x of liquidity | 2025-12-31 |
| MCHP | WATCH | net debt / FCF 6.03x > 6.00x; maturities 2.1x > 1.0x of liquidity | 2026-03-31 |
| NTRA | WATCH | coverage -76.2x < 2.0x | 2025-12-31 |
| OKE | WATCH | net debt / FCF 13.4x > 6.0x | 2025-12-31 |
| ORCL | WATCH | maturities 3.0x > 1.0x of liquidity | 2026-05-31 |
| ORLY | WATCH | maturities 1.8x > 1.0x of liquidity | 2025-12-31 |
| PEG | WATCH | net debt / FCF 862.0x > 6.0x; maturities 20.9x > 1.0x of liquidity | 2025-12-31 |
| PFE | WATCH | net debt / FCF 7.0x > 6.0x | 2025-12-31 |
| RCL | WATCH | maturities 4.4x > 1.0x of liquidity | 2025-12-31 |
| SNOW | WATCH | Altman Z'' 0.03 < 1.10 | 2026-01-31 |
| SNPS | WATCH | net debt / FCF 7.8x > 6.0x; maturities 1.3x > 1.0x of liquidity | 2025-10-31 |
| SO | WATCH | maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| SRE | WATCH | maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| TDG | WATCH | net debt / FCF 14.6x > 6.0x | 2025-09-30 |
| TEAM | WATCH | Altman Z'' -0.61 < 1.10 | 2026-06-30 |
| TRGP | WATCH | net debt / FCF 29.6x > 6.0x; maturities 2.8x > 1.0x of liquidity | 2025-12-31 |
| TTWO | WATCH | coverage -0.7x < 2.0x | 2026-03-31 |
| VST | WATCH | net debt / FCF 13.7x > 6.0x; maturities 2.6x > 1.0x of liquidity | 2025-12-31 |
| WBD | WATCH | net debt / FCF 9.1x > 6.0x; maturities 2.4x > 1.0x of liquidity | 2025-12-31 |
| WM | WATCH | maturities 1.9x > 1.0x of liquidity | 2025-12-31 |
| YUM | WATCH | maturities 1.6x > 1.0x of liquidity | 2025-12-31 |

## All companies

| ticker | class | fiscal year end | interest coverage | net debt / FCF | maturities / liquidity | rate trend (3y) | Altman Z'' | Piotroski F | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BA | FRAGILE | 2025-12-31 | 1.5x | FCF <= 0 | 0.6x | +0.7 pp | 4.58 | 6 |  |
| CRWV | FRAGILE | 2025-12-31 | -0.04x | FCF <= 0 | no liquidity | n/a (missing fiscal years) | 1.95 | n/a (missing assets (2y back)) |  |
| HPE | FRAGILE | 2025-10-31 | -0.4x | 32.8x | 1.7x | +1.6 pp | 3.63 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| XEL | FRAGILE | 2025-12-31 | 1.8x | FCF <= 0 | no liquidity | +0.8 pp | 4.09 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| ADM | WATCH | 2025-12-31 | 3.1x | 1.8x | 0.2x | +2.4 pp | n/a (missing equity, liabilities) | 6 |  |
| AEP | WATCH | 2025-12-31 | n/a (missing interest expense) | 13.9x | 2.3x | n/a (missing interest (latest)) | 3.98 | n/a (missing net income (latest), gross profit (latest), net income (1y back), gross profit (1y back)) |  |
| AZO | WATCH | 2025-08-30 | n/a (missing interest expense) | n/a (missing debt) | 1.3x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.28 | n/a (missing debt (latest), debt (1y back)) |  |
| BE | WATCH | 2025-12-31 | 1.9x | 2.9x | 0.0x | -9.4 pp | 5.26 | n/a (missing net income (latest), net income (1y back)) |  |
| CAT | WATCH | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.3x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing equity) | n/a (missing debt (latest), debt (1y back)) |  |
| COHR | WATCH | 2026-06-30 | n/a (missing EBIT, interest expense) | FCF <= 0 | 0.1x | n/a (missing interest (latest)) | n/a (missing EBIT) | 6 |  |
| CP | WATCH | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 2.1x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 5.44 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| DE | WATCH | 2025-11-02 | n/a (missing EBIT) | n/a (missing debt) | 1.9x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (latest), current assets (latest), current liabilities (latest), gross profit (latest), debt (1y back), current assets (1y back), current liabilities (1y back), gross profit (1y back)) |  |
| DUK | WATCH | 2025-12-31 | 2.4x | FCF <= 0 | no liquidity | +0.7 pp | 3.69 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| ECL | WATCH | 2025-12-31 | 8.9x | n/a (missing debt) | 1.1x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.49 | n/a (missing debt (latest), debt (1y back)) |  |
| ENB | WATCH | 2025-12-31 | 2.2x | 31.6x | 4.3x | +0.8 pp | 3.46 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| EPD | WATCH | 2025-12-31 | n/a (missing interest expense) | 11.3x | 1.3x | n/a (missing interest (latest)) | n/a (missing retained earnings, equity, liabilities) | n/a (missing shares (latest), shares (1y back)) |  |
| ET | WATCH | 2025-12-31 | 2.6x | 17.4x | 2.6x | +0.7 pp | n/a (missing retained earnings, equity, liabilities) | n/a (missing shares (latest), shares (1y back)) |  |
| ETR | WATCH | 2025-12-31 | 2.3x | FCF <= 0 | no liquidity | +1.3 pp | 4.26 | n/a (missing net income (latest), gross profit (latest), net income (1y back), gross profit (1y back)) |  |
| EXC | WATCH | 2025-12-31 | n/a (missing interest expense) | FCF <= 0 | no liquidity | n/a (missing interest (latest), interest (3y back)) | 4.06 | n/a (missing net income (latest), gross profit (latest), net income (1y back), gross profit (1y back)) |  |
| FIX | WATCH | 2025-12-31 | 145.9x | net cash | 0.0x | +4.3 pp | 7.30 | 7 |  |
| INTC | WATCH | 2025-12-27 | n/a (missing interest expense) | FCF <= 0 | 1.02x | n/a (missing interest (latest)) | 6.17 | 6 |  |
| IQV | WATCH | 2025-12-31 | 3.0x | 6.6x | 1.5x | +1.6 pp | 4.38 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| KDP | WATCH | 2025-12-31 | n/a (missing interest expense) | 8.6x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 4.55 | 7 |  |
| KMI | WATCH | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 3.90 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| LNG | WATCH | 2025-12-31 | n/a (missing interest expense) | 8.7x | 1.9x | n/a (missing interest (latest)) | 5.57 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| LOW | WATCH | 2026-01-30 | n/a (missing interest expense) | 5.0x | 1.2x | n/a (missing interest (latest), interest (3y back)) | 3.88 | 6 |  |
| MAR | WATCH | 2025-12-31 | n/a (missing interest expense) | net cash | 1.8x | n/a (missing interest (latest)) | 5.17 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| MCD | WATCH | 2025-12-31 | 7.8x | 5.5x | 1.1x | +0.7 pp | 8.45 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| MCHP | WATCH | 2026-03-31 | n/a (missing interest expense) | 6.03x | 2.1x | n/a (missing interest (latest)) | 6.01 | 6 |  |
| NTRA | WATCH | 2025-12-31 | -76.2x | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back)) | 4.12 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| OKE | WATCH | 2025-12-31 | n/a (missing interest expense) | 13.4x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 4.29 | 6 |  |
| ORCL | WATCH | 2026-05-31 | 4.5x | n/a (missing debt) | 3.0x | n/a (missing debt (latest), debt (1y back), debt (3y back)) | 4.05 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| ORLY | WATCH | 2025-12-31 | 14.7x | n/a (missing debt) | 1.8x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.34 | n/a (missing debt (latest), debt (1y back)) |  |
| PEG | WATCH | 2025-12-31 | 3.0x | 862.0x | 20.9x | +0.9 pp | n/a (missing equity, liabilities) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| PFE | WATCH | 2025-12-31 | 3.8x | 7.0x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.9 pp | 6.31 | 5 |  |
| RCL | WATCH | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 4.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.29 | n/a (missing debt (latest), debt (1y back)) |  |
| SNOW | WATCH | 2026-01-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 0.03 | n/a (missing debt (latest), debt (1y back)) |  |
| SNPS | WATCH | 2025-10-31 | n/a (missing interest expense) | 7.8x | 1.3x | n/a (missing debt (3y back), debt (4y back), interest (latest)) | 5.88 | 3 |  |
| SO | WATCH | 2025-12-31 | 2.2x | n/a (missing debt) | no liquidity | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.95 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| SRE | WATCH | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt) | no liquidity | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | n/a (missing EBIT) | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| TDG | WATCH | 2025-09-30 | n/a (missing interest expense) | 14.6x | 0.5x | n/a (missing interest (latest), interest (3y back)) | 4.03 | 6 |  |
| TEAM | WATCH | 2026-06-30 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), interest (latest)) | -0.61 | n/a (missing debt (latest), debt (1y back)) |  |
| TRGP | WATCH | 2025-12-31 | n/a (missing interest expense) | 29.6x | 2.8x | n/a (missing interest (latest), interest (3y back)) | 4.27 | 7 |  |
| TTWO | WATCH | 2026-03-31 | -0.7x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back)) | 1.67 | n/a (missing debt (latest), debt (1y back)) |  |
| VST | WATCH | 2025-12-31 | n/a (missing interest expense) | 13.7x | 2.6x | n/a (missing debt (3y back), debt (4y back), interest (latest)) | 3.29 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| WBD | WATCH | 2025-12-31 | n/a (missing interest expense) | 9.1x | 2.4x | n/a (missing interest (latest)) | 3.57 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| WM | WATCH | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.9x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 5.31 | n/a (missing debt (latest), debt (1y back)) |  |
| YUM | WATCH | 2025-12-31 | 4.7x | n/a (missing debt) | 1.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 2.49 | n/a (missing debt (latest), debt (1y back)) |  |
| A | SOUND | 2025-10-31 | 13.2x | 1.4x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.3 pp | 6.73 | 5 |  |
| AAPL | SOUND | 2025-09-27 | n/a (missing interest expense) | 0.4x | 0.2x | n/a (missing interest (latest)) | 5.56 | 8 |  |
| ABBV | SOUND | 2025-12-31 | 5.2x | 3.5x | 0.7x | +1.1 pp | 2.91 | 7 |  |
| ABT | SOUND | 2025-12-31 | n/a (missing interest expense) | 0.5x | 0.3x | n/a (missing interest (latest)) | 8.05 | 5 |  |
| ADSK | SOUND | 2026-01-31 | 19.7x | net cash | 0.1x | -0.02 pp | 3.61 | 8 |  |
| AMD | SOUND | 2025-12-27 | 28.2x | net cash | n/a (missing debt due in 2y) | -1.8 pp | 10.10 | 7 |  |
| AME | SOUND | 2025-12-31 | n/a (missing interest expense) | 1.1x | 0.4x | n/a (missing interest (latest)) | 8.66 | 5 |  |
| AMGN | SOUND | 2025-12-31 | 3.3x | 5.6x | 0.7x | +0.9 pp | 3.39 | 7 |  |
| AMZN | SOUND | 2025-12-31 | n/a (missing interest expense) | net cash | 0.1x | n/a (missing interest (latest)) | 6.05 | 6 |  |
| APP | SOUND | 2025-12-31 | 20.7x | n/a (missing FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | +0.4 pp | 11.11 | 8 |  |
| AXON | SOUND | 2025-12-31 | n/a (missing interest expense) | 1.4x | 0.0x | n/a (missing debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 6.63 | 5 |  |
| CARR | SOUND | 2025-12-31 | 4.7x | 4.7x | 0.6x | +1.3 pp | n/a (missing equity) | n/a (missing gross profit (latest)) |  |
| CL | SOUND | 2025-12-31 | n/a (missing interest expense) | 1.8x | 0.4x | n/a (missing interest (latest)) | 9.46 | 4 |  |
| CMG | SOUND | 2025-12-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 5.61 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| COR | SOUND | 2025-09-30 | n/a (missing interest expense) | 1.0x | 0.4x | n/a (missing interest (latest), interest (3y back)) | 3.30 | 6 |  |
| COST | SOUND | 2025-08-31 | 67.4x | net cash | 0.1x | +0.4 pp | 5.86 | 6 |  |
| CRH | SOUND | 2025-12-31 | n/a (missing interest expense) | 4.7x | 0.8x | n/a (missing debt (4y back), interest (latest)) | 6.81 | 6 |  |
| CRM | SOUND | 2026-01-31 | 25.7x | 0.5x | 0.4x | +0.0 pp | 5.04 | 7 |  |
| CSCO | SOUND | 2026-07-25 | n/a (missing interest expense) | 0.5x | 0.2x | n/a (missing interest (latest)) | 4.61 | 7 |  |
| CTAS | SOUND | 2026-05-31 | n/a (missing interest expense) | 0.6x | 0.6x | n/a (missing interest (latest)) | 10.69 | 8 |  |
| DELL | SOUND | 2026-01-30 | n/a (missing interest expense) | 2.3x | 0.7x | n/a (missing interest (latest)) | 3.51 | 6 |  |
| DIS | SOUND | 2025-09-27 | n/a (interest expense <= 0) | 3.6x | 0.7x | -1.1 pp | 5.83 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| DVN | SOUND | 2025-12-31 | 8.0x | 2.6x | 0.4x | -0.3 pp | 6.14 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| FCX | SOUND | 2025-12-31 | n/a (missing interest expense) | 5.0x | 0.6x | n/a (missing interest (latest), interest (3y back)) | 5.68 | 6 |  |
| FERG | SOUND | 2025-07-31 | n/a (missing interest expense) | 2.2x | 0.6x | n/a (missing fiscal years) | 7.52 | 5 |  |
| FLEX | SOUND | 2026-03-31 | 6.9x | 1.3x | 0.3x | -0.5 pp | 5.59 | 7 |  |
| FTNT | SOUND | 2025-12-31 | 103.7x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (3y back), debt (4y back)) | 5.13 | 6 |  |
| GOOGL | SOUND | 2025-12-31 | n/a (missing interest expense) | net cash | 0.0x | n/a (missing interest (latest)) | 10.04 | 6 |  |
| HCA | SOUND | 2025-12-31 | 5.4x | 5.6x | n/a (missing debt due in 1y) | +0.4 pp | 4.12 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| HD | SOUND | 2026-02-01 | n/a (missing interest expense) | 3.8x | 0.8x | n/a (missing interest (latest)) | 7.79 | 4 |  |
| HON | SOUND | 2025-12-31 | 6.0x | 4.1x | 0.5x | +1.9 pp | 7.11 | 5 |  |
| HWM | SOUND | 2025-12-31 | 11.6x | 1.6x | 0.2x | +0.1 pp | 7.82 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| IDXX | SOUND | 2025-12-31 | n/a (missing interest expense) | 0.3x | 0.1x | n/a (missing interest (latest)) | 13.68 | 8 |  |
| INTU | SOUND | 2026-07-31 | 23.0x | 0.3x | 0.2x | -0.1 pp | 8.05 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| KEYS | SOUND | 2025-10-31 | 9.1x | 0.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.0 pp | 8.40 | 5 |  |
| LIN | SOUND | 2025-12-31 | 15.5x | 4.3x | 0.6x | +0.6 pp | 5.28 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
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
| NOC | SOUND | 2025-12-31 | 6.8x | 3.4x | 0.4x | +0.2 pp | 5.58 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| NXPI | SOUND | 2025-12-31 | 6.5x | 3.2x | 0.6x | +0.4 pp | 5.51 | 4 |  |
| ONC | SOUND | 2025-12-31 | 9.0x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | -0.04 pp | 5.03 | 8 |  |
| OXY | SOUND | 2025-12-31 | 3.9x | 4.7x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.3 pp | 5.17 | n/a (missing net income (latest), gross profit (latest), net income (1y back)) |  |
| PEP | SOUND | 2025-12-27 | 10.3x | 5.7x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.0 pp | 6.13 | 5 |  |
| PH | SOUND | 2026-06-30 | n/a (missing interest expense) | 1.8x | 0.7x | n/a (missing interest (latest)) | 8.32 | 8 |  |
| QCOM | SOUND | 2025-09-28 | 18.6x | 0.4x | 0.1x | +1.1 pp | n/a (missing equity) | 6 |  |
| RSG | SOUND | 2025-12-31 | n/a (missing interest expense) | 5.7x | 0.8x | n/a (missing interest (latest)) | 5.25 | 6 |  |
| SHW | SOUND | 2025-12-31 | 9.4x | 4.0x | 0.96x | -0.1 pp | 4.34 | 6 |  |
| SNDK | SOUND | 2026-07-03 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 12.89 | 7 |  |
| SPGI | SOUND | 2025-12-31 | n/a (missing interest expense) | 2.1x | 0.3x | n/a (missing interest (latest)) | 6.38 | 7 |  |
| STX | SOUND | 2026-07-03 | n/a (missing interest expense) | 0.6x | 0.1x | n/a (missing interest (latest)) | 5.75 | 8 |  |
| TJX | SOUND | 2026-01-31 | 93.4x | net cash | 0.1x | +0.0 pp | 6.25 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| TSLA | SOUND | 2025-12-31 | n/a (missing interest expense) | net cash | 0.1x | n/a (missing interest (latest)) | 7.71 | 5 |  |
| TT | SOUND | 2025-12-31 | 17.5x | 1.0x | 0.3x | +0.2 pp | 7.27 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| TXN | SOUND | 2025-12-31 | 11.1x | 3.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +1.3 pp | 12.29 | 7 |  |
| VRT | SOUND | 2025-12-31 | 21.3x | 0.6x | 0.3x | -1.8 pp | 6.33 | 5 |  |
| WAT | SOUND | 2025-12-31 | 11.5x | 1.5x | 0.5x | +1.4 pp | 13.25 | 4 |  |
| WMT | SOUND | 2026-01-31 | 12.9x | 2.3x | 0.4x | +0.9 pp | 5.20 | 6 |  |
| XYZ | SOUND | 2025-12-31 | 6.7x | 0.3x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (3y back)) | 7.25 | 5 |  |
| ABNB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | n/a (missing debt (3y back), interest (latest), interest (3y back)) | 5.35 | 6 |  |
| ADBE | INSUFFICIENT DATA | 2025-11-28 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 10.92 | 7 |  |
| ADI | INSUFFICIENT DATA | 2025-11-01 | n/a (missing interest expense) | 1.2x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 7.41 | 8 |  |
| ADP | INSUFFICIENT DATA | 2026-06-30 | 13.5x | n/a (missing debt, FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.67 | n/a (missing debt (latest), debt (1y back)) |  |
| ALAB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing fiscal years) | 17.81 | n/a (missing debt (latest), debt (1y back)) |  |
| AMAT | INSUFFICIENT DATA | 2025-10-26 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (3y back), debt (4y back), interest (latest)) | 13.42 | 7 |  |
| ANET | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 11.71 | n/a (missing debt (latest), debt (1y back)) |  |
| APD | INSUFFICIENT DATA | 2025-09-30 | n/a (missing interest expense) | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.42 | n/a (missing operating cash flow (latest), debt (latest), operating cash flow (1y back), debt (1y back)) |  |
| APH | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.3x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 8.28 | n/a (missing debt (latest), debt (1y back)) |  |
| AVGO | INSUFFICIENT DATA | 2025-11-02 | n/a (missing interest expense) | 1.8x | 0.3x | n/a (missing debt (1y back), debt (3y back), interest (latest)) | n/a (missing equity) | n/a (missing net income (latest), debt (1y back)) |  |
| BDX | INSUFFICIENT DATA | 2025-09-30 | 4.2x | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.54 | n/a (missing operating cash flow (latest), debt (latest), operating cash flow (1y back), debt (1y back)) |  |
| BIIB | INSUFFICIENT DATA | 2025-12-31 | 6.8x | n/a (missing cash) | n/a (missing cash) | +0.3 pp | n/a (missing equity) | 5 |  |
| BKNG | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.2x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 10.89 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| BKR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt, cash) | n/a (missing cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing debt (latest), shares (latest), gross profit (latest), debt (1y back), shares (1y back), gross profit (1y back)) |  |
| BMY | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | 2.9x | 0.2x | n/a (missing interest (latest)) | n/a (missing EBIT) | 8 |  |
| BSX | INSUFFICIENT DATA | 2025-12-31 | 10.4x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.03 | n/a (missing net income (latest), debt (latest), net income (1y back), debt (1y back)) |  |
| CAH | INSUFFICIENT DATA | 2026-06-30 | 7.5x | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.03 | n/a (missing debt (latest), debt (1y back)) |  |
| CDNS | INSUFFICIENT DATA | 2025-12-31 | 12.8x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 9.71 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| CEG | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 4.2x | 0.3x | n/a (missing interest (latest)) | 4.79 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| CIEN | INSUFFICIENT DATA | 2025-11-01 | n/a (missing interest expense) | 0.3x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 5.15 | 7 |  |
| CLS | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing fiscal years) | 6.45 | n/a (missing debt (latest), debt (1y back)) |  |
| CMI | INSUFFICIENT DATA | 2025-12-31 | 12.2x | n/a (missing debt) | 0.1x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 8.26 | n/a (missing net income (latest), debt (latest), net income (1y back), debt (1y back)) |  |
| COP | INSUFFICIENT DATA | 2025-12-31 | 11.8x | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 7.22 | n/a (missing debt (latest), debt (1y back)) |  |
| CRDO | INSUFFICIENT DATA | 2026-05-02 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 19.60 | n/a (missing debt (latest), debt (1y back)) |  |
| CRWD | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.31 | n/a (missing debt (latest), revenue (latest), debt (1y back), revenue (1y back)) |  |
| CSX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing equity) | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| CTVA | INSUFFICIENT DATA | 2025-12-31 | 10.4x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.69 | n/a (missing debt (latest), debt (1y back)) |  |
| CVS | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.7x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 4.24 | n/a (missing debt (latest), debt (1y back)) |  |
| CVX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT) | n/a (missing debt, cash) | n/a (missing cash) | n/a (missing debt (latest), debt (1y back), debt (3y back)) | n/a (missing EBIT) | n/a (missing debt (latest), debt (1y back)) |  |
| D | INSUFFICIENT DATA | 2025-12-31 | 2.2x | n/a (missing FCF) | n/a (missing FCF) | n/a (missing debt (4y back)) | 3.81 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| DAL | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 2.3x | 0.8x | n/a (missing interest (latest), interest (3y back)) | 3.28 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| DASH | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 4.71 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| DHI | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (latest), current assets (latest), current liabilities (latest), debt (1y back), current assets (1y back), current liabilities (1y back)) |  |
| DHR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest)) | 7.71 | 5 |  |
| EBAY | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), interest (latest)) | 11.96 | n/a (missing debt (latest), debt (1y back)) |  |
| ED | INSUFFICIENT DATA | 2025-12-31 | 2.4x | n/a (missing FCF) | n/a (missing FCF) | +1.2 pp | 4.68 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| EL | INSUFFICIENT DATA | 2026-06-30 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | n/a (missing equity, liabilities) | n/a (missing debt (latest), debt (1y back)) |  |
| EME | INSUFFICIENT DATA | 2025-12-31 | 142.5x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 8.04 | n/a (missing debt (latest), debt (1y back)) |  |
| EMR | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing cash) | n/a (missing debt due in 1y, cash) | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | 7 |  |
| EOG | INSUFFICIENT DATA | 2025-12-31 | 27.2x | n/a (missing FCF) | n/a (missing debt due in 1y, FCF) | +0.2 pp | 7.75 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| ETN | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | 2.6x | 0.5x | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | 6 |  |
| EW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 12.85 | n/a (missing debt (latest), debt (1y back)) |  |
| FANG | INSUFFICIENT DATA | 2025-12-31 | 5.2x | n/a (missing FCF) | n/a (missing FCF) | -0.5 pp | 4.72 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| FAST | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 15.26 | 7 |  |
| FDX | INSUFFICIENT DATA | 2026-05-31 | n/a (missing interest expense) | 2.1x | 0.3x | n/a (missing interest (latest)) | 6.18 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| GD | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 1.5x | 0.5x | n/a (missing interest (latest)) | 8.09 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| GE | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| GEV | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing fiscal years) | 3.87 | n/a (missing debt (latest), debt (1y back)) |  |
| GILD | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing interest (latest)) | 6.53 | 8 |  |
| GLW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 6.85 | n/a (missing debt (latest), debt (1y back)) |  |
| GM | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 4.57 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| GRMN | INSUFFICIENT DATA | 2025-12-27 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 13.83 | n/a (missing debt (latest), debt (1y back)) |  |
| GWW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 1.4x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 13.91 | 7 |  |
| HLT | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.2x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.19 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| HONA | INSUFFICIENT DATA | n/a | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | no fiscal year known (no filing, or stale) |
| IBM | INSUFFICIENT DATA | 2025-12-31 | 6.3x | n/a (missing debt) | 0.7x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 7.35 | n/a (missing debt (latest), debt (1y back)) |  |
| ILMN | INSUFFICIENT DATA | 2025-12-28 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 6.29 | n/a (missing debt (latest), debt (1y back)) |  |
| IMO | INSUFFICIENT DATA | 2025-12-31 | 356.2x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 7.02 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| ISRG | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 15.26 | n/a (missing debt (latest), debt (1y back)) |  |
| ITW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 2.5x | 0.9x | n/a (missing interest (latest)) | n/a (missing equity, liabilities) | n/a (missing net income (latest), net income (1y back)) |  |
| JCI | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing debt (3y back), debt (4y back), interest (latest)) | n/a (missing EBIT) | n/a (missing operating cash flow (latest), operating cash flow (1y back)) |  |
| JNJ | INSUFFICIENT DATA | 2025-12-28 | n/a (missing EBIT, interest expense) | 1.5x | 0.2x | n/a (missing interest (latest)) | n/a (missing EBIT) | 3 |  |
| KLAC | INSUFFICIENT DATA | 2026-06-30 | n/a (missing EBIT, interest expense) | 1.1x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | n/a (missing EBIT) | 7 |  |
| KO | INSUFFICIENT DATA | 2025-12-31 | 8.3x | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back)) | 7.71 | n/a (missing debt (latest), debt (1y back)) |  |
| KR | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | 3.6x | 0.4x | n/a (missing interest (latest)) | 5.06 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| KVUE | INSUFFICIENT DATA | 2025-12-28 | 5.6x | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (4y back)) | 4.46 | n/a (missing debt (latest), debt (1y back)) |  |
| LHX | INSUFFICIENT DATA | 2026-01-02 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 5.10 | n/a (missing debt (latest), gross profit (latest), revenue (latest), debt (1y back)) |  |
| LITE | INSUFFICIENT DATA | 2026-06-27 | n/a (missing interest expense) | 1.7x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (3y back), interest (latest)) | 3.59 | 5 |  |
| LLY | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt, FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | n/a (missing debt (latest), interest (latest)) | n/a (missing EBIT) | n/a (missing debt (latest)) |  |
| LMT | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 2.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 5.24 | 5 |  |
| LYV | INSUFFICIENT DATA | 2025-12-31 | 4.0x | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.47 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| MDLZ | INSUFFICIENT DATA | 2025-12-31 | 5.9x | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.02 | n/a (missing debt (latest), debt (1y back)) |  |
| MDT | INSUFFICIENT DATA | 2026-04-24 | n/a (missing interest expense) | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 7.00 | n/a (missing debt (latest), debt (1y back)) |  |
| MELI | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.3x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 5.15 | 4 |  |
| MNST | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 15.50 | n/a (missing net income (latest), debt (latest), net income (1y back)) |  |
| MPC | INSUFFICIENT DATA | 2025-12-31 | 5.6x | n/a (missing debt) | 0.7x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.16 | n/a (missing debt (latest), debt (1y back)) |  |
| MPLX | INSUFFICIENT DATA | 2025-12-31 | 5.5x | n/a (missing debt) | 0.8x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing retained earnings, equity) | n/a (missing net income (latest), debt (latest), shares (latest), gross profit (latest), net income (1y back), debt (1y back), shares (1y back), gross profit (1y back)) |  |
| MPWR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 14.88 | n/a (missing debt (latest), debt (1y back)) |  |
| MRK | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | 2.8x | 0.3x | n/a (missing interest (latest)) | n/a (missing EBIT) | 4 |  |
| MRNA | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 8.37 | n/a (missing debt (latest), debt (1y back)) |  |
| MSCI | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 3.7x | 0.0x | n/a (missing interest (latest)) | 7.83 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| NEE | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest), interest (3y back)) | 4.16 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| NEM | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | net cash | 0.0x | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| NET | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.20 | n/a (missing debt (latest), debt (1y back)) |  |
| NFLX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 8.54 | n/a (missing debt (latest), debt (1y back)) |  |
| NOW | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.43 | n/a (missing debt (1y back)) |  |
| NSC | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.32 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| NTAP | INSUFFICIENT DATA | 2026-04-24 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 5.57 | 9 |  |
| NUE | INSUFFICIENT DATA | 2025-12-31 | 16.1x | n/a (missing debt) | 0.5x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 9.84 | n/a (missing debt (latest), debt (1y back)) |  |
| NVDA | INSUFFICIENT DATA | 2026-01-25 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 16.10 | 4 |  |
| ODFL | INSUFFICIENT DATA | 2025-12-31 | 4598.1x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (1y back), debt (3y back), debt (4y back)) | 11.50 | n/a (missing gross profit (latest), revenue (latest), debt (1y back), gross profit (1y back), revenue (1y back)) |  |
| OKTA | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.94 | n/a (missing debt (latest), debt (1y back)) |  |
| P | INSUFFICIENT DATA | 2026-02-01 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), interest (latest)) | 4.68 | n/a (missing debt (latest)) |  |
| PANW | INSUFFICIENT DATA | 2026-07-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), interest (latest)) | 4.74 | n/a (missing debt (latest), debt (1y back)) |  |
| PAYX | INSUFFICIENT DATA | 2026-05-31 | n/a (missing interest expense) | 1.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 5.69 | 8 |  |
| PCAR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (latest), current assets (latest), current liabilities (latest), debt (1y back), current assets (1y back), current liabilities (1y back)) |  |
| PG | INSUFFICIENT DATA | 2026-06-30 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest)) | n/a (missing equity) | 6 |  |
| PLTR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 13.80 | n/a (missing debt (latest), debt (1y back)) |  |
| PM | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.99x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 6.13 | n/a (missing debt (latest), debt (1y back)) |  |
| PSX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT) | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing EBIT) | n/a (missing debt (latest), debt (1y back)) |  |
| PWR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.9x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 5.46 | n/a (missing debt (latest), debt (1y back)) |  |
| PYPL | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.2x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 6.52 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| RKLB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 7.08 | 5 |  |
| ROK | INSUFFICIENT DATA | 2025-09-30 | n/a (missing interest expense) | 2.0x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 6.63 | 8 |  |
| ROP | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest)) | 6.39 | 5 |  |
| ROST | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | net cash | n/a (missing debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 7.29 | 6 |  |
| RTX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.6x | n/a (missing debt (latest), interest (latest)) | 5.41 | n/a (missing debt (latest), gross profit (latest), gross profit (1y back)) |  |
| RVMD | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.24 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| SBUX | INSUFFICIENT DATA | 2025-09-28 | 5.4x | n/a (missing cash) | n/a (missing cash) | +0.2 pp | 2.23 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| SCCO | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.5x | n/a (missing debt due in 1y, debt due in 2y) | n/a (missing interest (latest), interest (3y back)) | 9.36 | 8 |  |
| SLB | INSUFFICIENT DATA | 2025-12-31 | 8.7x | n/a (missing debt, cash) | n/a (missing debt due in 1y, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.48 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| SPCX | INSUFFICIENT DATA | n/a | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | no fiscal year known (no filing, or stale) |
| SYK | INSUFFICIENT DATA | 2025-12-31 | 8.4x | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing equity) | n/a (missing debt (latest), debt (1y back)) |  |
| SYY | INSUFFICIENT DATA | 2026-06-27 | n/a (missing interest expense) | n/a (missing debt) | 0.7x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing retained earnings) | n/a (missing debt (latest), debt (1y back)) |  |
| T | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 5.99x | 0.7x | n/a (missing interest (latest)) | n/a (missing equity, liabilities) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| TEL | INSUFFICIENT DATA | 2025-09-26 | n/a (missing interest expense) | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | n/a (missing equity) | n/a (missing debt (latest), debt (1y back)) |  |
| TER | INSUFFICIENT DATA | 2025-12-31 | 95.0x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 8.30 | n/a (missing debt (latest), debt (1y back)) |  |
| TEVA | INSUFFICIENT DATA | 2025-12-31 | 2.4x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 2.84 | n/a (missing debt (latest), debt (1y back)) |  |
| TGT | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest)) | 4.59 | 6 |  |
| TMO | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 4.6x | 0.6x | n/a (missing interest (latest)) | 7.26 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| TMUS | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 4.8x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 4.51 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| TWLO | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | n/a (missing interest (latest), interest (3y back)) | 6.59 | 6 |  |
| UAL | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 3.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 3.56 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| UBER | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.3x | 0.2x | n/a (missing interest (latest)) | 4.31 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| UI | INSUFFICIENT DATA | 2026-06-30 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), interest (latest), interest (3y back)) | 14.58 | n/a (missing debt (latest)) |  |
| UNP | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 5.6x | 0.6x | n/a (missing interest (latest)) | 7.79 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| URI | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest), interest (3y back)) | 6.28 | 5 |  |
| VEEV | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | n/a (missing debt, FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 14.46 | n/a (missing debt (latest), debt (1y back)) |  |
| VLO | INSUFFICIENT DATA | 2025-12-31 | 5.7x | n/a (missing FCF) | n/a (missing FCF) | +1.5 pp | 8.07 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| VRTX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 10.75 | n/a (missing debt (latest), debt (1y back)) |  |
| VZ | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | n/a (missing equity, liabilities) | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| WAB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest), interest (3y back)) | 5.61 | 5 |  |
| WCN | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), interest (latest)) | 5.02 | n/a (missing debt (latest), debt (1y back)) |  |
| WDC | INSUFFICIENT DATA | 2026-07-03 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 10.28 | 8 |  |
| WMB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt, cash) | n/a (missing cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest)) | 3.02 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| XOM | INSUFFICIENT DATA | 2025-12-31 | 69.4x | n/a (missing debt) | n/a (missing debt due in 1y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 9.04 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
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
