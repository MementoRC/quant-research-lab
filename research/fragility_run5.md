# Balance-sheet fragility screen (exploration only)

> Not a return signal and not a recommendation. Latest fiscal-year filings only; banks, insurers, brokers and property trusts are not applicable.

- as-of date: 2026-10-04
- membership month-end: 2026-09-30
- universe size: 300
- newest filing date seen: 2026-10-01
- config/fragility.yaml sha256: `192c7faaed5bd7f75487eaa0a9cb9812d3c7d96e0b048a3d18b1bfa0576b9322`
- universe membership sha256: `4ede8b2b2ac96e975f9dc2251e4c49ed15b15f2ed52f89959759bde0c8751f9c`
- breach_to_fragile (N): 2
- min_available_for_sound (K): 4
- thresholds: interest_coverage_min 2, net_debt_to_fcf_max 6, maturities_to_liquidity_max 1, altman_z_min 1.1, piotroski_max_weak 2, rate_rise_max_pp 2, rate_trend_min_net_debt_to_assets 0.05

## Summary

| class | count |
| --- | --- |
| FRAGILE | 11 |
| WATCH | 55 |
| SOUND | 131 |
| INSUFFICIENT DATA | 53 |
| NOT APPLICABLE | 50 |

## Fragile and watch

| ticker | class | breached measures | fiscal year end |
| --- | --- | --- | --- |
| BA | FRAGILE | coverage 1.5x < 2.0x; net debt / FCF: FCF <= 0 with net debt > 0 | 2025-12-31 |
| CRWV | FRAGILE | coverage -0.04x < 2.00x; net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| CVS | FRAGILE | coverage 1.5x < 2.0x; net debt / FCF 6.9x > 6.0x | 2025-12-31 |
| HPE | FRAGILE | coverage -0.4x < 2.0x; net debt / FCF 32.8x > 6.0x; maturities 1.7x > 1.0x of liquidity | 2025-10-31 |
| INTC | FRAGILE | coverage -2.0x < 2.0x; net debt / FCF: FCF <= 0 with net debt > 0; maturities 1.02x > 1.00x of liquidity | 2025-12-27 |
| NET | FRAGILE | coverage -23.6x < 2.0x; net debt / FCF 8.1x > 6.0x | 2025-12-31 |
| SNOW | FRAGILE | coverage -173.0x < 2.0x; Altman Z'' 0.03 < 1.10 | 2026-01-31 |
| TEAM | FRAGILE | coverage 0.2x < 2.0x; Altman Z'' -0.61 < 1.10 | 2026-06-30 |
| VST | FRAGILE | coverage 1.6x < 2.0x; net debt / FCF 13.7x > 6.0x; maturities 2.6x > 1.0x of liquidity; rate +3.6 pp > 2.0 pp in 3y | 2025-12-31 |
| WBD | FRAGILE | coverage 0.4x < 2.0x; net debt / FCF 9.1x > 6.0x; maturities 2.4x > 1.0x of liquidity | 2025-12-31 |
| XEL | FRAGILE | coverage 1.8x < 2.0x; net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| ADM | WATCH | rate +2.4 pp > 2.0 pp in 3y | 2025-12-31 |
| AEP | WATCH | net debt / FCF 13.9x > 6.0x; maturities 2.3x > 1.0x of liquidity | 2025-12-31 |
| APD | WATCH | coverage -4.1x < 2.0x | 2025-09-30 |
| AXON | WATCH | coverage -0.7x < 2.0x | 2025-12-31 |
| AZO | WATCH | maturities 1.3x > 1.0x of liquidity | 2025-08-30 |
| BE | WATCH | coverage 1.9x < 2.0x | 2025-12-31 |
| BKNG | WATCH | rate +5.8 pp > 2.0 pp in 3y | 2025-12-31 |
| CAH | WATCH | rate +2.3 pp > 2.0 pp in 3y | 2026-06-30 |
| CAT | WATCH | maturities 1.3x > 1.0x of liquidity | 2025-12-31 |
| CEG | WATCH | rate +2.2 pp > 2.0 pp in 3y | 2025-12-31 |
| COHR | WATCH | net debt / FCF: FCF <= 0 with net debt > 0 | 2026-06-30 |
| CP | WATCH | net debt / FCF 10.4x > 6.0x; maturities 2.1x > 1.0x of liquidity | 2025-12-31 |
| CRWD | WATCH | coverage -10.5x < 2.0x | 2026-01-31 |
| D | WATCH | rate +2.1 pp > 2.0 pp in 3y | 2025-12-31 |
| DE | WATCH | maturities 1.9x > 1.0x of liquidity | 2025-11-02 |
| DUK | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| ECL | WATCH | maturities 1.1x > 1.0x of liquidity | 2025-12-31 |
| ENB | WATCH | net debt / FCF 31.6x > 6.0x; maturities 4.3x > 1.0x of liquidity | 2025-12-31 |
| EPD | WATCH | net debt / FCF 11.3x > 6.0x; maturities 1.3x > 1.0x of liquidity | 2025-12-31 |
| ET | WATCH | net debt / FCF 17.4x > 6.0x; maturities 2.6x > 1.0x of liquidity | 2025-12-31 |
| ETR | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| EXC | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| GM | WATCH | net debt / FCF 6.3x > 6.0x | 2025-12-31 |
| IDXX | WATCH | rate +2.4 pp > 2.0 pp in 3y | 2025-12-31 |
| IQV | WATCH | net debt / FCF 6.6x > 6.0x; maturities 1.5x > 1.0x of liquidity | 2025-12-31 |
| KDP | WATCH | net debt / FCF 8.6x > 6.0x | 2025-12-31 |
| KMI | WATCH | maturities 1.4x > 1.0x of liquidity | 2025-12-31 |
| KO | WATCH | net debt / FCF 6.4x > 6.0x | 2025-12-31 |
| LNG | WATCH | net debt / FCF 8.7x > 6.0x; maturities 1.9x > 1.0x of liquidity | 2025-12-31 |
| LOW | WATCH | maturities 1.2x > 1.0x of liquidity | 2026-01-30 |
| MAR | WATCH | maturities 1.8x > 1.0x of liquidity | 2025-12-31 |
| MCD | WATCH | maturities 1.1x > 1.0x of liquidity | 2025-12-31 |
| MCHP | WATCH | net debt / FCF 6.03x > 6.00x; maturities 2.1x > 1.0x of liquidity | 2026-03-31 |
| MPC | WATCH | net debt / FCF 6.1x > 6.0x | 2025-12-31 |
| NSC | WATCH | net debt / FCF 7.2x > 6.0x | 2025-12-31 |
| NTRA | WATCH | coverage -76.2x < 2.0x | 2025-12-31 |
| NUE | WATCH | net debt / FCF: FCF <= 0 with net debt > 0 | 2025-12-31 |
| OKE | WATCH | net debt / FCF 13.4x > 6.0x | 2025-12-31 |
| ORCL | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities 3.0x > 1.0x of liquidity | 2026-05-31 |
| ORLY | WATCH | maturities 1.8x > 1.0x of liquidity | 2025-12-31 |
| PEG | WATCH | net debt / FCF 862.0x > 6.0x; maturities 20.9x > 1.0x of liquidity | 2025-12-31 |
| PFE | WATCH | net debt / FCF 7.0x > 6.0x | 2025-12-31 |
| RCL | WATCH | net debt / FCF 16.6x > 6.0x; maturities 4.4x > 1.0x of liquidity | 2025-12-31 |
| RKLB | WATCH | coverage -8.6x < 2.0x | 2025-12-31 |
| SNPS | WATCH | net debt / FCF 7.8x > 6.0x; maturities 1.3x > 1.0x of liquidity | 2025-10-31 |
| SO | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| SRE | WATCH | net debt / FCF: FCF <= 0 with net debt > 0; maturities due with no liquidity (cash + FCF <= 0) | 2025-12-31 |
| SYY | WATCH | net debt / FCF 6.1x > 6.0x | 2026-06-27 |
| TDG | WATCH | net debt / FCF 14.6x > 6.0x | 2025-09-30 |
| TRGP | WATCH | net debt / FCF 29.6x > 6.0x; maturities 2.8x > 1.0x of liquidity | 2025-12-31 |
| TTWO | WATCH | coverage -0.7x < 2.0x | 2026-03-31 |
| VZ | WATCH | rate +2.03 pp > 2.00 pp in 3y | 2025-12-31 |
| WCN | WATCH | net debt / FCF 7.1x > 6.0x | 2025-12-31 |
| WM | WATCH | net debt / FCF 8.1x > 6.0x; maturities 1.9x > 1.0x of liquidity | 2025-12-31 |
| YUM | WATCH | net debt / FCF 6.9x > 6.0x; maturities 1.6x > 1.0x of liquidity | 2025-12-31 |

## All companies

| ticker | class | fiscal year end | interest coverage | net debt / FCF | maturities / liquidity | rate trend (3y) | Altman Z'' | Piotroski F | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BA | FRAGILE | 2025-12-31 | 1.5x | FCF <= 0 | 0.6x | +0.7 pp | 4.58 | 6 |  |
| CRWV | FRAGILE | 2025-12-31 | -0.04x | FCF <= 0 | no liquidity | n/a (missing fiscal years) | 1.95 | n/a (missing assets (2y back)) |  |
| CVS | FRAGILE | 2025-12-31 | 1.5x | 6.9x | 0.7x | +0.5 pp | 4.24 | 7 |  |
| HPE | FRAGILE | 2025-10-31 | -0.4x | 32.8x | 1.7x | +1.6 pp | 3.63 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| INTC | FRAGILE | 2025-12-27 | -2.0x | FCF <= 0 | 1.02x | +1.0 pp | 6.17 | 6 |  |
| NET | FRAGILE | 2025-12-31 | -23.6x | 8.1x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.0 pp | 5.20 | 3 |  |
| SNOW | FRAGILE | 2026-01-31 | -173.0x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -6.0% of assets | 0.03 | 5 |  |
| TEAM | FRAGILE | 2026-06-30 | 0.2x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back)) | -0.61 | n/a (missing debt (latest), debt (1y back)) |  |
| VST | FRAGILE | 2025-12-31 | 1.6x | 13.7x | 2.6x | +3.6 pp | 3.29 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| WBD | FRAGILE | 2025-12-31 | 0.4x | 9.1x | 2.4x | +0.2 pp | 3.57 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| XEL | FRAGILE | 2025-12-31 | 1.8x | FCF <= 0 | no liquidity | +0.8 pp | 4.09 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| ADM | WATCH | 2025-12-31 | 3.1x | 1.8x | 0.2x | +2.4 pp | n/a (missing equity, liabilities) | 6 |  |
| AEP | WATCH | 2025-12-31 | 2.6x | 13.9x | 2.3x | +0.7 pp | 3.98 | n/a (missing net income (latest), gross profit (latest), net income (1y back), gross profit (1y back)) |  |
| APD | WATCH | 2025-09-30 | -4.1x | n/a (missing FCF) | n/a (missing FCF) | -0.3 pp | 5.42 | n/a (missing operating cash flow (latest), operating cash flow (1y back)) |  |
| AXON | WATCH | 2025-12-31 | -0.7x | 1.4x | 0.0x | little net debt: 1.5% of assets | 6.63 | 5 |  |
| AZO | WATCH | 2025-08-30 | 7.4x | 4.8x | 1.3x | +1.99 pp | 3.28 | 6 |  |
| BE | WATCH | 2025-12-31 | 1.9x | 2.9x | 0.0x | little net debt: 3.8% of assets | 5.26 | n/a (missing net income (latest), net income (1y back)) |  |
| BKNG | WATCH | 2025-12-31 | 5.5x | 0.2x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +5.8 pp | 10.89 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| CAH | WATCH | 2026-06-30 | 7.5x | 0.9x | 0.4x | +2.3 pp | 3.03 | 8 |  |
| CAT | WATCH | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.3x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing equity) | n/a (missing debt (latest), debt (1y back)) |  |
| CEG | WATCH | 2025-12-31 | 6.0x | 4.2x | 0.3x | +2.2 pp | 4.79 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| COHR | WATCH | 2026-06-30 | n/a (missing EBIT, interest expense) | FCF <= 0 | 0.1x | n/a (missing interest (latest)) | n/a (missing EBIT) | 6 |  |
| CP | WATCH | 2025-12-31 | n/a (missing interest expense) | 10.4x | 2.1x | n/a (missing interest (latest), interest (3y back)) | 5.44 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| CRWD | WATCH | 2026-01-31 | -10.5x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.31 | n/a (missing debt (latest), revenue (latest), debt (1y back), revenue (1y back)) |  |
| D | WATCH | 2025-12-31 | 2.2x | n/a (missing FCF) | n/a (missing FCF) | +2.1 pp | 3.81 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| DE | WATCH | 2025-11-02 | n/a (missing EBIT) | n/a (missing debt) | 1.9x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (latest), current assets (latest), current liabilities (latest), gross profit (latest), debt (1y back), current assets (1y back), current liabilities (1y back), gross profit (1y back)) |  |
| DUK | WATCH | 2025-12-31 | 2.4x | FCF <= 0 | no liquidity | +0.7 pp | 3.69 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| ECL | WATCH | 2025-12-31 | 8.9x | 3.9x | 1.1x | +0.9 pp | 6.49 | 5 |  |
| ENB | WATCH | 2025-12-31 | 2.2x | 31.6x | 4.3x | +0.8 pp | 3.46 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| EPD | WATCH | 2025-12-31 | 5.2x | 11.3x | 1.3x | -0.1 pp | n/a (missing retained earnings, equity, liabilities) | n/a (missing shares (latest), shares (1y back)) |  |
| ET | WATCH | 2025-12-31 | 2.6x | 17.4x | 2.6x | +0.7 pp | n/a (missing retained earnings, equity, liabilities) | n/a (missing shares (latest), shares (1y back)) |  |
| ETR | WATCH | 2025-12-31 | 2.3x | FCF <= 0 | no liquidity | +1.3 pp | 4.26 | n/a (missing net income (latest), gross profit (latest), net income (1y back), gross profit (1y back)) |  |
| EXC | WATCH | 2025-12-31 | n/a (missing interest expense) | FCF <= 0 | no liquidity | n/a (missing interest (latest), interest (3y back)) | 4.06 | n/a (missing net income (latest), gross profit (latest), net income (1y back), gross profit (1y back)) |  |
| GM | WATCH | 2025-12-31 | n/a (missing interest expense) | 6.3x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 4.57 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| IDXX | WATCH | 2025-12-31 | 35.0x | 0.3x | 0.1x | +2.4 pp | 13.68 | 8 |  |
| IQV | WATCH | 2025-12-31 | 3.0x | 6.6x | 1.5x | +1.6 pp | 4.38 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| KDP | WATCH | 2025-12-31 | n/a (missing interest expense) | 8.6x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest)) | 4.55 | 7 |  |
| KMI | WATCH | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | 1.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 3.90 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| KO | WATCH | 2025-12-31 | 8.3x | 6.4x | 0.6x | +1.7 pp | 7.71 | 7 |  |
| LNG | WATCH | 2025-12-31 | 9.6x | 8.7x | 1.9x | -1.0 pp | 5.57 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| LOW | WATCH | 2026-01-30 | n/a (missing interest expense) | 5.0x | 1.2x | n/a (missing interest (latest), interest (3y back)) | 3.88 | 6 |  |
| MAR | WATCH | 2025-12-31 | 5.1x | net cash | 1.8x | little net debt: -1.2% of assets | 5.17 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| MCD | WATCH | 2025-12-31 | 7.8x | 5.5x | 1.1x | +0.7 pp | 8.45 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| MCHP | WATCH | 2026-03-31 | 2.2x | 6.03x | 2.1x | +1.1 pp | 6.01 | 6 |  |
| MPC | WATCH | 2025-12-31 | 5.6x | 6.1x | 0.7x | -0.04 pp | 6.16 | 7 |  |
| NSC | WATCH | 2025-12-31 | 5.5x | 7.2x | n/a (missing debt due in 1y) | -0.1 pp | 5.32 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| NTRA | WATCH | 2025-12-31 | -76.2x | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back)) | 4.12 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| NUE | WATCH | 2025-12-31 | 16.1x | FCF <= 0 | 0.5x | -1.1 pp | 9.84 | 6 |  |
| OKE | WATCH | 2025-12-31 | 3.2x | 13.4x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.5 pp | 4.29 | 6 |  |
| ORCL | WATCH | 2026-05-31 | 4.5x | FCF <= 0 | 3.0x | -3.6 pp | 4.05 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| ORLY | WATCH | 2025-12-31 | 14.7x | n/a (missing debt) | 1.8x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 3.34 | n/a (missing debt (latest), debt (1y back)) |  |
| PEG | WATCH | 2025-12-31 | 3.0x | 862.0x | 20.9x | +0.9 pp | n/a (missing equity, liabilities) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| PFE | WATCH | 2025-12-31 | 3.8x | 7.0x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.9 pp | 6.31 | 5 |  |
| RCL | WATCH | 2025-12-31 | 4.9x | 16.6x | 4.4x | -1.3 pp | 3.29 | 7 |  |
| RKLB | WATCH | 2025-12-31 | -8.6x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -37.2% of assets | 7.08 | 5 |  |
| SNPS | WATCH | 2025-10-31 | 2.05x | 7.8x | 1.3x | n/a (missing debt (3y back), debt (4y back)) | 5.88 | 3 |  |
| SO | WATCH | 2025-12-31 | 2.2x | FCF <= 0 | no liquidity | +1.1 pp | 3.95 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| SRE | WATCH | 2025-12-31 | 2.2x | FCF <= 0 | no liquidity | +0.4 pp | 5.14 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| SYY | WATCH | 2026-06-27 | n/a (missing interest expense) | 6.1x | 0.7x | n/a (missing interest (latest), interest (3y back)) | n/a (missing retained earnings) | 7 |  |
| TDG | WATCH | 2025-09-30 | n/a (missing interest expense) | 14.6x | 0.5x | n/a (missing interest (latest), interest (3y back)) | 4.03 | 6 |  |
| TRGP | WATCH | 2025-12-31 | n/a (missing interest expense) | 29.6x | 2.8x | n/a (missing interest (latest), interest (3y back)) | 4.27 | 7 |  |
| TTWO | WATCH | 2026-03-31 | -0.7x | 1.2x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | -2.4 pp | 1.67 | 7 |  |
| VZ | WATCH | 2025-12-31 | 4.4x | n/a (missing FCF) | n/a (missing FCF) | +2.03 pp | n/a (missing equity, liabilities) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| WCN | WATCH | 2025-12-31 | 5.1x | 7.1x | 0.4x | +0.6 pp | 5.02 | 6 |  |
| WM | WATCH | 2025-12-31 | n/a (missing interest expense) | 8.1x | 1.9x | n/a (missing interest (latest), interest (3y back)) | 5.31 | 7 |  |
| YUM | WATCH | 2025-12-31 | 4.7x | 6.9x | 1.6x | -0.1 pp | 2.49 | 5 |  |
| A | SOUND | 2025-10-31 | 13.2x | 1.4x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.3 pp | 6.73 | 5 |  |
| AAPL | SOUND | 2025-09-27 | n/a (missing interest expense) | 0.4x | 0.2x | n/a (missing interest (latest)) | 5.56 | 8 |  |
| ABBV | SOUND | 2025-12-31 | 5.2x | 3.5x | 0.7x | +1.1 pp | 2.91 | 7 |  |
| ABT | SOUND | 2025-12-31 | 16.3x | 0.5x | 0.3x | little net debt: 4.6% of assets | 8.05 | 5 |  |
| ADBE | SOUND | 2025-11-28 | 33.1x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -1.3% of assets | 10.92 | 7 |  |
| ADI | SOUND | 2025-11-01 | 9.2x | 1.2x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.8 pp | 7.41 | 8 |  |
| ADSK | SOUND | 2026-01-31 | 19.7x | net cash | 0.1x | little net debt: -0.8% of assets | 3.61 | 8 |  |
| ALAB | SOUND | 2025-12-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 17.81 | 5 | no debt tag; treated as no debt |
| AMAT | SOUND | 2025-10-26 | 30.8x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -5.6% of assets | 13.42 | 7 |  |
| AMD | SOUND | 2025-12-27 | 28.2x | net cash | n/a (missing debt due in 2y) | little net debt: -8.4% of assets | 10.10 | 7 |  |
| AME | SOUND | 2025-12-31 | 23.5x | 1.1x | 0.4x | +0.3 pp | 8.66 | 5 |  |
| AMGN | SOUND | 2025-12-31 | 3.3x | 5.6x | 0.7x | +0.9 pp | 3.39 | 7 |  |
| AMZN | SOUND | 2025-12-31 | 35.2x | net cash | 0.1x | little net debt: -6.6% of assets | 6.05 | 6 |  |
| ANET | SOUND | 2025-12-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 11.71 | 3 | no debt tag; treated as no debt |
| APH | SOUND | 2025-12-31 | 16.0x | 0.9x | 0.3x | +0.5 pp | 8.28 | 6 |  |
| APP | SOUND | 2025-12-31 | 20.7x | n/a (missing FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | +0.4 pp | 11.11 | 8 |  |
| AVGO | SOUND | 2025-11-02 | 7.9x | 1.8x | 0.3x | +0.5 pp | n/a (missing equity) | n/a (missing net income (latest)) |  |
| BMY | SOUND | 2025-12-31 | 5.9x | 2.9x | 0.2x | +1.2 pp | 5.41 | 8 |  |
| BSX | SOUND | 2025-12-31 | 10.4x | 2.6x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | -2.1 pp | 6.03 | n/a (missing net income (latest), net income (1y back)) |  |
| CARR | SOUND | 2025-12-31 | 4.7x | 4.7x | 0.6x | +1.3 pp | n/a (missing equity) | n/a (missing gross profit (latest)) |  |
| CIEN | SOUND | 2025-11-01 | 2.2x | 0.3x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: 3.9% of assets | 5.15 | 7 |  |
| CL | SOUND | 2025-12-31 | 12.4x | 1.8x | 0.4x | +1.4 pp | 9.46 | 4 |  |
| CLS | SOUND | 2025-12-31 | 19.8x | 0.4x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: 2.5% of assets | 6.45 | 7 |  |
| CMG | SOUND | 2025-12-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 5.61 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| CMI | SOUND | 2025-12-31 | 12.2x | 1.4x | 0.1x | +0.8 pp | 8.26 | n/a (missing net income (latest), net income (1y back)) |  |
| COP | SOUND | 2025-12-31 | 11.8x | n/a (missing FCF) | n/a (missing FCF) | +0.6 pp | 7.22 | 6 |  |
| COR | SOUND | 2025-09-30 | n/a (missing interest expense) | 1.0x | 0.4x | little net debt: 4.3% of assets | 3.30 | 6 |  |
| COST | SOUND | 2025-08-31 | 67.4x | net cash | 0.1x | little net debt: -12.3% of assets | 5.86 | 6 |  |
| CRDO | SOUND | 2026-05-02 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 19.60 | 6 | no debt tag; treated as no debt |
| CRH | SOUND | 2025-12-31 | 6.7x | 4.7x | 0.8x | n/a (missing debt (4y back)) | 6.81 | 6 |  |
| CRM | SOUND | 2026-01-31 | 25.7x | 0.5x | 0.4x | +0.0 pp | 5.04 | 7 |  |
| CSCO | SOUND | 2026-07-25 | 10.5x | 0.5x | 0.2x | +1.3 pp | 4.61 | 7 |  |
| CTAS | SOUND | 2026-05-31 | 24.5x | 0.6x | 0.6x | +1.0 pp | 10.69 | 8 |  |
| CTVA | SOUND | 2025-12-31 | 10.4x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -4.8% of assets | 5.69 | 6 |  |
| DELL | SOUND | 2026-01-30 | 5.2x | 2.3x | 0.7x | +1.2 pp | 3.51 | 6 |  |
| DHR | SOUND | 2025-12-31 | 17.7x | n/a (missing cash) | n/a (missing cash) | +0.6 pp | 7.71 | 5 |  |
| DIS | SOUND | 2025-09-27 | n/a (interest expense <= 0) | 3.6x | 0.7x | -1.1 pp | 5.83 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| DVN | SOUND | 2025-12-31 | 8.0x | 2.6x | 0.4x | -0.3 pp | 6.14 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| EBAY | SOUND | 2025-12-31 | 9.3x | 3.4x | 0.6x | +1.0 pp | 11.96 | 5 |  |
| ETN | SOUND | 2025-12-31 | 21.5x | 2.6x | 0.5x | n/a (missing interest (3y back)) | 6.35 | 6 |  |
| FAST | SOUND | 2025-12-31 | 267.0x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -3.0% of assets | 15.26 | 7 |  |
| FCX | SOUND | 2025-12-31 | n/a (missing interest expense) | 5.0x | 0.6x | n/a (missing interest (latest), interest (3y back)) | 5.68 | 6 |  |
| FDX | SOUND | 2026-05-31 | 5.6x | 2.1x | 0.3x | +0.9 pp | 6.18 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| FERG | SOUND | 2025-07-31 | n/a (missing interest expense) | 2.2x | 0.6x | n/a (missing fiscal years) | 7.52 | 5 |  |
| FIX | SOUND | 2025-12-31 | 145.9x | net cash | 0.0x | little net debt: -13.0% of assets | 7.30 | 7 |  |
| FLEX | SOUND | 2026-03-31 | 6.9x | 1.3x | 0.3x | -0.5 pp | 5.59 | 7 |  |
| FTNT | SOUND | 2025-12-31 | 103.7x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -14.4% of assets | 5.13 | 6 |  |
| GILD | SOUND | 2025-12-31 | 9.8x | n/a (missing cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | +0.4 pp | 6.53 | 8 |  |
| GLW | SOUND | 2025-12-31 | 6.8x | n/a (missing FCF) | n/a (missing FCF) | +0.1 pp | 6.85 | 6 |  |
| GOOGL | SOUND | 2025-12-31 | 175.3x | net cash | 0.0x | little net debt: -13.1% of assets | 10.04 | 6 |  |
| GWW | SOUND | 2025-12-31 | 30.8x | 1.4x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (3y back)) | 13.91 | 7 |  |
| HCA | SOUND | 2025-12-31 | 5.4x | 5.6x | n/a (missing debt due in 1y) | +0.4 pp | 4.12 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| HD | SOUND | 2026-02-01 | 8.7x | 3.8x | 0.8x | +0.6 pp | 7.79 | 4 |  |
| HLT | SOUND | 2025-12-31 | 4.3x | 5.6x | 0.2x | +0.5 pp | 3.19 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| HON | SOUND | 2025-12-31 | 6.0x | 4.1x | 0.5x | +1.9 pp | 7.11 | 5 |  |
| HWM | SOUND | 2025-12-31 | 11.6x | 1.6x | 0.2x | +0.1 pp | 7.82 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| IBM | SOUND | 2025-12-31 | 6.3x | 4.5x | 0.7x | +0.9 pp | 7.35 | 5 |  |
| IMO | SOUND | 2025-12-31 | 356.2x | 0.6x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | -1.0 pp | 7.02 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| INTU | SOUND | 2026-07-31 | 23.0x | 0.3x | 0.2x | -0.1 pp | 8.05 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| ISRG | SOUND | 2025-12-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 15.26 | 6 | no debt tag; treated as no debt |
| ITW | SOUND | 2025-12-31 | 14.4x | 2.5x | 0.9x | +1.5 pp | n/a (missing equity, liabilities) | n/a (missing net income (latest), net income (1y back)) |  |
| JNJ | SOUND | 2025-12-28 | 34.6x | 1.5x | 0.2x | +1.5 pp | 7.92 | 3 |  |
| KEYS | SOUND | 2025-10-31 | 9.1x | 0.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.0 pp | 8.40 | 5 |  |
| KLAC | SOUND | 2026-06-30 | 20.7x | 1.1x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.1 pp | 9.65 | 7 |  |
| KVUE | SOUND | 2025-12-28 | 5.6x | 3.9x | 0.6x | n/a (missing debt (4y back)) | 4.46 | 5 |  |
| LIN | SOUND | 2025-12-31 | 15.5x | 4.3x | 0.6x | +0.6 pp | 5.28 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| LITE | SOUND | 2026-06-27 | 24.1x | 1.7x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | -0.5 pp | 3.59 | 5 |  |
| LLY | SOUND | 2025-12-31 | 29.7x | n/a (missing FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | +0.4 pp | 7.06 | 7 |  |
| LMT | SOUND | 2025-12-31 | 6.9x | 2.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.8 pp | 5.24 | 5 |  |
| LRCX | SOUND | 2026-06-28 | 52.6x | net cash | 0.1x | little net debt: -7.9% of assets | 14.32 | 8 |  |
| LYV | SOUND | 2025-12-31 | 4.0x | 3.3x | 0.6x | little net debt: 4.8% of assets | 3.47 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| MCK | SOUND | 2026-03-31 | 25.1x | 0.4x | 0.3x | little net debt: 3.1% of assets | 3.83 | 6 |  |
| MCO | SOUND | 2025-12-31 | n/a (missing interest expense) | 1.8x | 0.2x | n/a (missing interest (latest), interest (3y back)) | 9.63 | 9 |  |
| MDLZ | SOUND | 2025-12-31 | 5.9x | n/a (missing cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | +1.1 pp | 5.02 | 5 |  |
| MDT | SOUND | 2026-04-24 | 9.0x | 3.5x | 0.4x | -0.1 pp | 7.00 | 8 |  |
| META | SOUND | 2025-12-31 | 76.4x | net cash | 0.0x | little net debt: -6.2% of assets | 8.59 | 5 |  |
| MMM | SOUND | 2025-12-31 | 10.3x | n/a (missing cash) | n/a (missing cash) | +0.7 pp | 8.71 | 5 |  |
| MO | SOUND | 2025-12-31 | 8.4x | 2.3x | 0.3x | +0.5 pp | 7.75 | 6 |  |
| MPLX | SOUND | 2025-12-31 | 5.5x | 5.7x | 0.8x | +0.2 pp | n/a (missing retained earnings, equity) | n/a (missing net income (latest), shares (latest), gross profit (latest), net income (1y back), shares (1y back), gross profit (1y back)) |  |
| MPWR | SOUND | 2025-12-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 14.88 | 6 | no debt tag; treated as no debt |
| MRK | SOUND | 2025-12-31 | 16.5x | 2.8x | 0.3x | +0.1 pp | 7.48 | 4 |  |
| MRVL | SOUND | 2026-01-31 | 7.1x | 1.7x | 0.4x | +0.6 pp | 6.68 | 7 |  |
| MSCI | SOUND | 2025-12-31 | 8.2x | 3.7x | 0.0x | -0.04 pp | 7.83 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| MSFT | SOUND | 2026-06-30 | 50.9x | net cash | 0.1x | little net debt: -4.8% of assets | 7.84 | 6 |  |
| MSI | SOUND | 2025-12-31 | 8.3x | 3.1x | 0.6x | +0.6 pp | 4.94 | 6 |  |
| MU | SOUND | 2025-08-28 | 20.5x | 1.1x | 0.0x | little net debt: 2.3% of assets | 9.32 | 7 |  |
| NOC | SOUND | 2025-12-31 | 6.8x | 3.4x | 0.4x | +0.2 pp | 5.58 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| NOW | SOUND | 2025-12-31 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -8.6% of assets | 5.43 | 4 |  |
| NTAP | SOUND | 2026-04-24 | 15.4x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -10.2% of assets | 5.57 | 9 |  |
| NVDA | SOUND | 2026-01-25 | 503.4x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -1.0% of assets | 16.10 | 4 |  |
| NXPI | SOUND | 2025-12-31 | 6.5x | 3.2x | 0.6x | +0.4 pp | 5.51 | 4 |  |
| ODFL | SOUND | 2025-12-31 | 4598.1x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -1.5% of assets | 11.50 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| OKTA | SOUND | 2026-01-31 | 37.2x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -22.7% of assets | 5.94 | 8 |  |
| ONC | SOUND | 2025-12-31 | 9.0x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -45.2% of assets | 5.03 | 8 |  |
| OXY | SOUND | 2025-12-31 | 3.9x | 4.7x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.3 pp | 5.17 | n/a (missing net income (latest), gross profit (latest), net income (1y back)) |  |
| PANW | SOUND | 2026-07-31 | n/a (interest expense <= 0) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -2.7% of assets | 4.74 | 3 |  |
| PAYX | SOUND | 2026-05-31 | 9.3x | 1.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +1.1 pp | 5.69 | 8 |  |
| PEP | SOUND | 2025-12-27 | 10.3x | 5.7x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.0 pp | 6.13 | 5 |  |
| PH | SOUND | 2026-06-30 | 12.6x | 1.8x | 0.7x | -0.2 pp | 8.32 | 8 |  |
| PLTR | SOUND | 2025-12-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 13.80 | 7 | no debt tag; treated as no debt |
| PM | SOUND | 2025-12-31 | 9.4x | 4.1x | 0.99x | +1.2 pp | 6.13 | 6 |  |
| PWR | SOUND | 2025-12-31 | 6.2x | 3.4x | 0.9x | +1.8 pp | 5.46 | 4 |  |
| QCOM | SOUND | 2025-09-28 | 18.6x | 0.4x | 0.1x | +1.1 pp | n/a (missing equity) | 6 |  |
| ROK | SOUND | 2025-09-30 | 10.9x | 2.0x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +1.4 pp | 6.63 | 8 |  |
| ROP | SOUND | 2025-12-31 | 6.9x | n/a (missing FCF) | n/a (missing FCF) | +1.2 pp | 6.39 | 5 |  |
| ROST | SOUND | 2026-01-31 | n/a (missing interest expense) | net cash | n/a (missing debt due in 3y) | little net debt: -19.8% of assets | 7.29 | 6 |  |
| RSG | SOUND | 2025-12-31 | 5.8x | 5.7x | 0.8x | +0.7 pp | 5.25 | 6 |  |
| RVMD | SOUND | 2025-12-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 3.24 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| SHW | SOUND | 2025-12-31 | 9.4x | 4.0x | 0.96x | -0.1 pp | 4.34 | 6 |  |
| SNDK | SOUND | 2026-07-03 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | no debt | 12.89 | 7 |  |
| SPGI | SOUND | 2025-12-31 | 22.6x | 2.1x | 0.3x | -1.7 pp | 6.38 | 7 |  |
| STX | SOUND | 2026-07-03 | 14.4x | 0.6x | 0.1x | -3.1 pp | 5.75 | 8 |  |
| SYK | SOUND | 2025-12-31 | 8.4x | 2.8x | 0.6x | +1.3 pp | n/a (missing equity) | 4 |  |
| T | SOUND | 2025-12-31 | 3.6x | 5.99x | 0.7x | +1.2 pp | n/a (missing equity, liabilities) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| TGT | SOUND | 2026-01-31 | 11.5x | n/a (missing cash) | n/a (missing cash) | -0.6 pp | 4.59 | 6 |  |
| TJX | SOUND | 2026-01-31 | 93.4x | net cash | 0.1x | little net debt: -9.4% of assets | 6.25 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| TMO | SOUND | 2025-12-31 | 5.5x | 4.6x | 0.6x | +1.9 pp | 7.26 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| TSLA | SOUND | 2025-12-31 | 12.9x | net cash | 0.1x | little net debt: -27.2% of assets | 7.71 | 5 |  |
| TT | SOUND | 2025-12-31 | 17.5x | 1.0x | 0.3x | +0.2 pp | 7.27 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| TXN | SOUND | 2025-12-31 | 11.1x | 3.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +1.3 pp | 12.29 | 7 |  |
| UAL | SOUND | 2025-12-31 | 3.4x | 3.5x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | +0.5 pp | 3.56 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| UBER | SOUND | 2025-12-31 | 12.6x | 0.3x | 0.2x | little net debt: 4.8% of assets | 4.31 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| UNP | SOUND | 2025-12-31 | 7.5x | 5.6x | 0.6x | +0.1 pp | 7.79 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| VEEV | SOUND | 2026-01-31 | no debt | no debt | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | no debt | 14.46 | 6 | no debt tag; treated as no debt |
| VRT | SOUND | 2025-12-31 | 21.3x | 0.6x | 0.3x | -1.8 pp | 6.33 | 5 |  |
| WAB | SOUND | 2025-12-31 | 8.0x | n/a (missing cash) | n/a (missing cash) | +0.1 pp | 5.61 | 5 |  |
| WAT | SOUND | 2025-12-31 | 11.5x | 1.5x | 0.5x | +1.4 pp | 13.25 | 4 |  |
| WDC | SOUND | 2026-07-03 | 27.0x | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -3.8% of assets | 10.28 | 8 |  |
| WMT | SOUND | 2026-01-31 | 12.9x | 2.3x | 0.4x | +0.9 pp | 5.20 | 6 |  |
| XOM | SOUND | 2025-12-31 | 69.4x | 1.3x | n/a (missing debt due in 1y) | -0.4 pp | 9.04 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| XYZ | SOUND | 2025-12-31 | 6.7x | 0.3x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: 1.8% of assets | 7.25 | 5 |  |
| ABNB | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | little net debt: -40.6% of assets | 5.35 | 6 |  |
| ADP | INSUFFICIENT DATA | 2026-06-30 | 13.5x | n/a (missing debt, FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.67 | n/a (missing debt (latest), debt (1y back)) |  |
| BDX | INSUFFICIENT DATA | 2025-09-30 | 4.2x | n/a (missing debt, FCF) | n/a (missing FCF) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 5.54 | n/a (missing operating cash flow (latest), debt (latest), operating cash flow (1y back), debt (1y back)) |  |
| BIIB | INSUFFICIENT DATA | 2025-12-31 | 6.8x | n/a (missing cash) | n/a (missing cash) | +0.3 pp | n/a (missing equity) | 5 |  |
| BKR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing shares (latest), gross profit (latest), shares (1y back), gross profit (1y back)) |  |
| CDNS | INSUFFICIENT DATA | 2025-12-31 | 12.8x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 9.71 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| CSX | INSUFFICIENT DATA | 2025-12-31 | 5.4x | n/a (missing cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | +0.2 pp | n/a (missing equity) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| CVX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT) | n/a (missing cash) | n/a (missing cash) | +1.6 pp | n/a (missing EBIT) | 5 |  |
| DAL | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 2.3x | 0.8x | n/a (missing interest (latest), interest (3y back)) | 3.28 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| DASH | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | net cash | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | little net debt: -8.4% of assets | 4.71 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| DHI | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing debt) | 0.6x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (latest), current assets (latest), current liabilities (latest), debt (1y back), current assets (1y back), current liabilities (1y back)) |  |
| ED | INSUFFICIENT DATA | 2025-12-31 | 2.4x | n/a (missing FCF) | n/a (missing FCF) | +1.2 pp | 4.68 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| EL | INSUFFICIENT DATA | 2026-06-30 | 2.3x | n/a (missing cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | +0.8 pp | n/a (missing equity, liabilities) | 6 |  |
| EME | INSUFFICIENT DATA | 2025-12-31 | 142.5x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back)) | 8.04 | n/a (missing debt (latest), debt (1y back)) |  |
| EMR | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing cash) | n/a (missing debt due in 1y, cash) | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | 7 |  |
| EOG | INSUFFICIENT DATA | 2025-12-31 | 27.2x | n/a (missing FCF) | n/a (missing debt due in 1y, FCF) | +0.2 pp | 7.75 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| EW | INSUFFICIENT DATA | 2025-12-31 | 62.0x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 12.85 | n/a (missing debt (latest), debt (1y back)) |  |
| FANG | INSUFFICIENT DATA | 2025-12-31 | 5.2x | n/a (missing FCF) | n/a (missing FCF) | -0.5 pp | 4.72 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| GD | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 1.5x | 0.5x | n/a (missing interest (latest)) | 8.09 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| GE | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing cash) | n/a (missing cash) | n/a (missing interest (latest), interest (3y back)) | n/a (missing EBIT) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| GEV | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing fiscal years) | 3.87 | n/a (missing debt (1y back)) |  |
| GRMN | INSUFFICIENT DATA | 2025-12-27 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 13.83 | n/a (missing debt (latest), debt (1y back)) |  |
| HONA | INSUFFICIENT DATA | n/a | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | no fiscal year known (no filing, or stale) |
| ILMN | INSUFFICIENT DATA | 2025-12-28 | 8.0x | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back)) | 6.29 | n/a (missing debt (latest), debt (1y back)) |  |
| JCI | INSUFFICIENT DATA | 2025-09-30 | n/a (missing EBIT, interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest)) | n/a (missing EBIT) | n/a (missing operating cash flow (latest), operating cash flow (1y back)) |  |
| KR | INSUFFICIENT DATA | 2026-01-31 | n/a (missing interest expense) | 3.6x | 0.4x | n/a (missing interest (latest)) | 5.06 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| LHX | INSUFFICIENT DATA | 2026-01-02 | n/a (missing interest expense) | 3.7x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 5.10 | n/a (missing gross profit (latest), revenue (latest)) |  |
| MELI | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.3x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 5.15 | 4 |  |
| MNST | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | 15.50 | n/a (missing net income (latest), debt (latest), net income (1y back)) |  |
| MRNA | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), interest (latest), interest (3y back)) | 8.37 | n/a (missing debt (latest), debt (1y back)) |  |
| NEE | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest), interest (3y back)) | 4.16 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| NEM | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | net cash | 0.0x | little net debt: -5.5% of assets | n/a (missing EBIT) | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| NFLX | INSUFFICIENT DATA | 2025-12-31 | 17.2x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 8.54 | n/a (missing debt (latest), debt (1y back)) |  |
| P | INSUFFICIENT DATA | 2026-02-01 | 34.0x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest)) | 4.68 | n/a (missing debt (latest)) |  |
| PCAR | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT, interest expense) | n/a (missing debt, cash) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back), interest (latest), interest (3y back)) | n/a (missing current assets, current liabilities, EBIT) | n/a (missing debt (latest), current assets (latest), current liabilities (latest), debt (1y back), current assets (1y back), current liabilities (1y back)) |  |
| PG | INSUFFICIENT DATA | 2026-06-30 | 22.5x | n/a (missing cash) | n/a (missing cash) | +0.2 pp | n/a (missing equity) | 6 |  |
| PSX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing EBIT) | n/a (missing FCF) | n/a (missing FCF) | +1.2 pp | n/a (missing EBIT) | 8 |  |
| PYPL | INSUFFICIENT DATA | 2025-12-31 | 13.8x | n/a (missing debt) | 0.2x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.52 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| RTX | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 3.7x | 0.6x | n/a (missing interest (latest)) | 5.41 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| SBUX | INSUFFICIENT DATA | 2025-09-28 | 5.4x | n/a (missing cash) | n/a (missing cash) | +0.2 pp | 2.23 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| SCCO | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 0.5x | n/a (missing debt due in 1y, debt due in 2y) | n/a (missing interest (latest), interest (3y back)) | 9.36 | 8 |  |
| SLB | INSUFFICIENT DATA | 2025-12-31 | 8.7x | n/a (missing debt, cash) | n/a (missing debt due in 1y, cash) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 6.48 | n/a (missing debt (latest), gross profit (latest), debt (1y back), gross profit (1y back)) |  |
| SPCX | INSUFFICIENT DATA | n/a | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | n/a (no fiscal year known (no filing, or stale)) | no fiscal year known (no filing, or stale) |
| TEL | INSUFFICIENT DATA | 2025-09-26 | 41.7x | n/a (missing debt) | 0.4x | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | n/a (missing equity) | n/a (missing debt (latest), debt (1y back)) |  |
| TER | INSUFFICIENT DATA | 2025-12-31 | 95.0x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back)) | 8.30 | n/a (missing debt (latest), debt (1y back)) |  |
| TEVA | INSUFFICIENT DATA | 2025-12-31 | 2.4x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back), debt (4y back)) | 2.84 | n/a (missing debt (latest), debt (1y back)) |  |
| TMUS | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | 4.8x | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing interest (latest), interest (3y back)) | 4.51 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
| TWLO | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y, FCF) | little net debt: 3.2% of assets | 6.59 | 6 |  |
| UI | INSUFFICIENT DATA | 2026-06-30 | n/a (missing interest expense) | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), interest (latest), interest (3y back)) | 14.58 | n/a (missing debt (latest)) |  |
| URI | INSUFFICIENT DATA | 2025-12-31 | n/a (missing interest expense) | n/a (missing FCF) | n/a (missing FCF) | n/a (missing interest (latest), interest (3y back)) | 6.28 | 5 |  |
| VLO | INSUFFICIENT DATA | 2025-12-31 | 5.7x | n/a (missing FCF) | n/a (missing FCF) | +1.5 pp | 8.07 | n/a (missing gross profit (latest), revenue (latest), gross profit (1y back), revenue (1y back)) |  |
| VRTX | INSUFFICIENT DATA | 2025-12-31 | 313.8x | n/a (missing debt) | n/a (missing debt due in 1y, debt due in 2y, debt due in 3y) | n/a (missing debt (latest), debt (1y back), debt (3y back)) | 10.75 | n/a (missing debt (latest), debt (1y back)) |  |
| WMB | INSUFFICIENT DATA | 2025-12-31 | 2.9x | n/a (missing cash) | n/a (missing cash) | +0.3 pp | 3.02 | n/a (missing gross profit (latest), gross profit (1y back)) |  |
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
