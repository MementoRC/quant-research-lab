# Long-run withdrawals: 30-year resampled paths

Compares portfolios over 30-year withdrawal paths built by resampling 2005-01 to 2018-12 months. It selects and recommends nothing. Spec: docs/methodology/longrun.md.

- data: up to 2018-12-31 only (validation and holdout stay sealed)
- 10000 paths of 30 years, 12-month blocks drawn from 168 months (circular), seed 20261008; every portfolio sees the same draws
- longrun.yaml sha256: `ebd3d59afd1bfbc79118747a944f74a8b3c62688aeddfe2e201183e10acfe061`
- decision.yaml sha256: `88ab8b08a34f8b3d106fd7670af02e3e827b86467a2755eb3620ada4490aa76d` (read unchanged)
- 35 rows per withdrawal rate, including the CASH +1% real (assumption) row, 7 assumption rows (A80-TCASH20 to G80-TCASH20) and 4 by-product rows (IEF, TLT, RSP, BONDS); only the 5 A80 rows answer the defensive-sleeve question (docs/methodology/defensive-sleeve.md); the 7 X80-CASH20 rows and the 7 assumption rows answer the true-cash question (docs/methodology/true-cash-all-cores.md)

## How to read this

- Each path is one made-up 30-year retirement, built by stringing together real 12-month stretches of 2005-01 to 2018-12 in random order. There are 10,000 paths, and every portfolio is run through the same ones, so differences between portfolios are not luck of the draw.
- Money ran out means the portfolio fell to effectively zero.
- Real value means value after inflation, in today's money, as a percentage of the starting amount.
- Bad case (worst 5%) is the value that 1 path in 20 ends below.
- Withdrawals start at the annual rate / 12 of the starting amount each month and rise every 12 months with that path's own inflation.

## Limits

- one market era (2005-2018)
- one large crash (2008)
- falling interest rates that flatter bonds
- low inflation
- near-zero cash yields in 2009-2015

Resampling recombines these months. It cannot create a 1970s-style inflation decade.

## Notes

- Each month the withdrawal is taken first, then the month's return applies. It starts at the annual rate / 12 of the starting value and is raised every 12 months by the path's own inflation.
- Portfolio returns pay trading costs of 5 bps (0.01% each) per unit traded.
- CASH +1% real (assumption): an assumption, not history. It earns each month's inflation plus 1.0% a year.
- A80-TCASH20 to G80-TCASH20: assumptions, not history. Each is 80.0% of its own core plus 20.0% cash earning each month's inflation plus 1.0% a year, rebalanced daily; every real yield is checked equal to the CASH +1% real row's. The cash legs and the daily returns to 80/20 pay no trading cost, and neither do their SHY pairs (A80-TCASH20 with A80-CASH20, B80-TCASH20 with B80-CASH20, C80-TCASH20 with C80-CASH20, D80-TCASH20 with D80-CASH20, E80-TCASH20 with E80-CASH20, F80-TCASH20 with F80-CASH20, G80-TCASH20 with G80-CASH20): the engine charges only target-to-target turnover, so rebalancing a constant mix is free in both rows. It follows unadjusted CPI, so it loses money in deflation months: 40 of 168 months here, worst 4.0% from 2008-09 to 2009-01. A 0% floor would make true cash look better in the crash windows.
- The engine never charges for drift, so the cost of real periodic rebalancing is slightly understated for every blend.
- A path is empty once its value is effectively zero (below one billionth of the start).
- All figures are percentages of the starting value or of paths.

## Withdrawals

### Withdrawal rate 2.0% per year

| portfolio | money ran out by year 20 | by year 25 | by year 30 | typical year it ran out (paths that ran out) | real value ever below 50.0% | real value at year 30: typical | real value at year 30: bad case (worst 5%) |
|---|---|---|---|---|---|---|---|
| A | 0.1% | 0.3% | 0.7% | 27 | 16.0% | 299.8% | 39.6% |
| B | 0.0% | 0.0% | 0.2% | 28 | 9.0% | 309.0% | 65.4% |
| C | 0.0% | 0.0% | 0.1% | 28 | 8.7% | 204.5% | 51.8% |
| D | 0.0% | 0.0% | 0.0% | 30 | 2.7% | 273.7% | 91.3% |
| E | 0.0% | 0.0% | 0.0% | - | 2.0% | 360.7% | 116.6% |
| F | 0.0% | 0.0% | 0.0% | - | 0.5% | 234.9% | 109.4% |
| G | 0.0% | 0.0% | 0.0% | - | 0.0% | 250.2% | 132.9% |
| CASH | 0.0% | 0.0% | 0.0% | - | 89.9% | 38.9% | 27.4% |
| CASH +1% real (assumption) | 0.0% | 0.0% | 0.0% | - | 0.0% | 65.5% | 65.3% |
| G-EW | 0.0% | 0.0% | 0.0% | - | 0.1% | 265.4% | 135.3% |
| IEF | 0.0% | 0.0% | 0.0% | - | 4.1% | 113.4% | 55.6% |
| TLT | 0.0% | 0.0% | 0.1% | 29 | 8.1% | 195.0% | 52.5% |
| RSP | 0.7% | 1.5% | 2.5% | 24 | 24.4% | 383.9% | 19.9% |
| BONDS | 0.0% | 0.0% | 0.0% | - | 6.3% | 106.0% | 50.3% |
| AG | 0.0% | 0.0% | 0.0% | - | 1.0% | 309.5% | 116.6% |
| G-CASH | 0.0% | 0.0% | 0.0% | - | 0.1% | 110.0% | 74.2% |
| A-CASH | 0.0% | 0.0% | 0.0% | - | 7.2% | 141.4% | 50.8% |
| A80-CASH20 | 0.0% | 0.1% | 0.2% | 27 | 11.4% | 232.7% | 47.2% |
| A80-IEF20 | 0.0% | 0.0% | 0.1% | 27 | 8.2% | 283.1% | 62.1% |
| A80-TLT20 | 0.0% | 0.0% | 0.1% | 28 | 6.1% | 330.7% | 77.8% |
| A80-BONDS20 | 0.0% | 0.0% | 0.1% | 27 | 8.2% | 280.6% | 61.7% |
| A80-RSP20 | 0.0% | 0.1% | 0.3% | 27 | 10.5% | 358.1% | 61.2% |
| B80-CASH20 | 0.0% | 0.0% | 0.0% | 30 | 5.6% | 232.8% | 68.2% |
| C80-CASH20 | 0.0% | 0.0% | 0.0% | 29 | 6.9% | 159.4% | 52.9% |
| D80-CASH20 | 0.0% | 0.0% | 0.0% | - | 1.7% | 201.5% | 84.6% |
| E80-CASH20 | 0.0% | 0.0% | 0.0% | - | 1.1% | 254.4% | 104.0% |
| F80-CASH20 | 0.0% | 0.0% | 0.0% | - | 0.3% | 175.2% | 94.1% |
| G80-CASH20 | 0.0% | 0.0% | 0.0% | - | 0.0% | 183.0% | 107.5% |
| A80-TCASH20 | 0.0% | 0.0% | 0.2% | 27 | 10.2% | 251.2% | 52.2% |
| B80-TCASH20 | 0.0% | 0.0% | 0.0% | 30 | 5.0% | 251.1% | 73.3% |
| C80-TCASH20 | 0.0% | 0.0% | 0.0% | 29 | 5.7% | 173.0% | 57.9% |
| D80-TCASH20 | 0.0% | 0.0% | 0.0% | - | 1.5% | 217.6% | 90.1% |
| E80-TCASH20 | 0.0% | 0.0% | 0.0% | - | 1.0% | 274.4% | 110.5% |
| F80-TCASH20 | 0.0% | 0.0% | 0.0% | - | 0.2% | 190.0% | 102.0% |
| G80-TCASH20 | 0.0% | 0.0% | 0.0% | - | 0.0% | 198.2% | 118.2% |

### Withdrawal rate 3.3% per year

| portfolio | money ran out by year 20 | by year 25 | by year 30 | typical year it ran out (paths that ran out) | real value ever below 50.0% | real value at year 30: typical | real value at year 30: bad case (worst 5%) |
|---|---|---|---|---|---|---|---|
| A | 1.4% | 4.3% | 7.2% | 24 | 27.8% | 206.6% | 0.0% |
| B | 0.5% | 1.7% | 3.5% | 25 | 19.9% | 216.2% | 10.4% |
| C | 0.3% | 1.5% | 4.4% | 27 | 25.3% | 128.8% | 3.0% |
| D | 0.1% | 0.5% | 1.3% | 27 | 10.3% | 187.9% | 32.9% |
| E | 0.1% | 0.3% | 0.9% | 27 | 6.8% | 261.1% | 53.1% |
| F | 0.0% | 0.0% | 0.1% | 29 | 6.3% | 155.4% | 50.9% |
| G | 0.0% | 0.0% | 0.0% | - | 2.4% | 168.8% | 69.7% |
| CASH | 0.0% | 0.0% | 46.8% | 29 | 100.0% | 0.5% | 0.0% |
| CASH +1% real (assumption) | 0.0% | 0.0% | 0.0% | - | 100.0% | 20.4% | 20.1% |
| G-EW | 0.0% | 0.0% | 0.0% | - | 2.3% | 181.7% | 71.6% |
| IEF | 0.0% | 0.1% | 1.8% | 29 | 43.6% | 57.4% | 10.0% |
| TLT | 0.3% | 1.5% | 4.5% | 27 | 26.0% | 121.6% | 2.6% |
| RSP | 3.8% | 7.4% | 10.3% | 22 | 32.9% | 271.5% | 0.0% |
| BONDS | 0.0% | 0.2% | 2.8% | 29 | 50.1% | 51.7% | 5.7% |
| AG | 0.0% | 0.1% | 0.4% | 28 | 6.3% | 217.7% | 53.7% |
| G-CASH | 0.0% | 0.0% | 0.0% | 30 | 41.2% | 54.9% | 25.1% |
| A-CASH | 0.0% | 0.7% | 3.6% | 28 | 33.3% | 79.8% | 4.3% |
| A80-CASH20 | 0.6% | 2.5% | 5.8% | 26 | 25.9% | 152.4% | 0.0% |
| A80-IEF20 | 0.4% | 1.6% | 3.7% | 26 | 19.6% | 194.5% | 6.9% |
| A80-TLT20 | 0.2% | 1.0% | 2.6% | 27 | 15.4% | 233.4% | 18.9% |
| A80-BONDS20 | 0.4% | 1.6% | 3.7% | 26 | 19.8% | 191.9% | 6.6% |
| A80-RSP20 | 0.6% | 2.4% | 4.5% | 25 | 20.3% | 255.2% | 3.7% |
| B80-CASH20 | 0.1% | 0.9% | 2.5% | 27 | 19.0% | 153.6% | 15.2% |
| C80-CASH20 | 0.0% | 0.7% | 3.5% | 28 | 28.9% | 93.3% | 5.5% |
| D80-CASH20 | 0.0% | 0.2% | 0.9% | 28 | 12.1% | 128.3% | 30.1% |
| E80-CASH20 | 0.0% | 0.1% | 0.5% | 27 | 7.4% | 172.4% | 45.1% |
| F80-CASH20 | 0.0% | 0.0% | 0.1% | 30 | 10.7% | 106.5% | 39.3% |
| G80-CASH20 | 0.0% | 0.0% | 0.0% | - | 5.6% | 113.7% | 49.9% |
| A80-TCASH20 | 0.5% | 2.1% | 5.1% | 26 | 23.5% | 168.0% | 0.0% |
| B80-TCASH20 | 0.1% | 0.8% | 2.1% | 27 | 17.0% | 169.0% | 19.9% |
| C80-TCASH20 | 0.0% | 0.6% | 2.7% | 28 | 25.1% | 104.1% | 9.1% |
| D80-TCASH20 | 0.0% | 0.1% | 0.8% | 28 | 10.3% | 141.6% | 33.9% |
| E80-TCASH20 | 0.0% | 0.1% | 0.4% | 27 | 6.2% | 188.5% | 50.6% |
| F80-TCASH20 | 0.0% | 0.0% | 0.0% | 29 | 7.4% | 119.0% | 45.9% |
| G80-TCASH20 | 0.0% | 0.0% | 0.0% | - | 3.3% | 126.1% | 58.7% |

### Withdrawal rate 4.0% per year

| portfolio | money ran out by year 20 | by year 25 | by year 30 | typical year it ran out (paths that ran out) | real value ever below 50.0% | real value at year 30: typical | real value at year 30: bad case (worst 5%) |
|---|---|---|---|---|---|---|---|
| A | 4.2% | 9.3% | 14.8% | 24 | 35.2% | 156.4% | 0.0% |
| B | 1.8% | 4.8% | 9.5% | 25 | 28.0% | 165.6% | 0.0% |
| C | 1.4% | 6.2% | 13.1% | 26 | 38.5% | 89.7% | 0.0% |
| D | 0.5% | 2.1% | 5.0% | 26 | 19.8% | 141.8% | 0.0% |
| E | 0.4% | 1.5% | 3.3% | 26 | 12.8% | 207.0% | 15.6% |
| F | 0.0% | 0.4% | 1.8% | 28 | 18.6% | 113.5% | 17.7% |
| G | 0.0% | 0.0% | 0.6% | 29 | 10.6% | 125.3% | 33.7% |
| CASH | 0.0% | 51.7% | 99.6% | 25 | 100.0% | 0.0% | 0.0% |
| CASH +1% real (assumption) | 0.0% | 0.0% | 100.0% | 30 | 100.0% | 0.0% | 0.0% |
| G-EW | 0.0% | 0.0% | 0.6% | 29 | 9.8% | 136.9% | 35.5% |
| IEF | 0.1% | 3.1% | 17.3% | 28 | 74.6% | 27.2% | 0.0% |
| TLT | 1.4% | 6.2% | 13.7% | 26 | 40.5% | 82.3% | 0.0% |
| RSP | 7.4% | 12.5% | 16.9% | 21 | 38.3% | 213.3% | 0.0% |
| BONDS | 0.1% | 4.3% | 21.8% | 28 | 79.1% | 22.3% | 0.0% |
| AG | 0.1% | 0.9% | 2.5% | 27 | 14.0% | 169.3% | 18.9% |
| G-CASH | 0.0% | 0.1% | 6.6% | 29 | 88.8% | 25.2% | 0.0% |
| A-CASH | 0.6% | 5.4% | 16.0% | 27 | 54.6% | 46.4% | 0.0% |
| A80-CASH20 | 2.5% | 7.3% | 13.9% | 25 | 36.4% | 109.0% | 0.0% |
| A80-IEF20 | 1.6% | 5.3% | 9.6% | 25 | 29.1% | 146.9% | 0.0% |
| A80-TLT20 | 1.1% | 3.9% | 7.1% | 25 | 23.5% | 181.0% | 0.0% |
| A80-BONDS20 | 1.6% | 5.4% | 9.7% | 25 | 29.3% | 144.9% | 0.0% |
| A80-RSP20 | 2.5% | 6.0% | 10.0% | 24 | 27.5% | 200.4% | 0.0% |
| B80-CASH20 | 1.0% | 3.6% | 9.1% | 27 | 31.4% | 110.8% | 0.0% |
| C80-CASH20 | 0.7% | 5.3% | 14.4% | 27 | 47.2% | 58.6% | 0.0% |
| D80-CASH20 | 0.2% | 1.5% | 5.2% | 27 | 28.5% | 88.9% | 0.0% |
| E80-CASH20 | 0.2% | 1.1% | 3.3% | 27 | 17.5% | 127.4% | 11.3% |
| F80-CASH20 | 0.0% | 0.3% | 2.6% | 29 | 34.0% | 70.2% | 9.0% |
| G80-CASH20 | 0.0% | 0.0% | 1.0% | 29 | 26.0% | 76.4% | 17.9% |
| A80-TCASH20 | 2.1% | 6.6% | 12.3% | 25 | 33.6% | 123.1% | 0.0% |
| B80-TCASH20 | 0.9% | 3.1% | 7.8% | 27 | 27.8% | 124.5% | 0.0% |
| C80-TCASH20 | 0.5% | 4.3% | 12.1% | 27 | 42.5% | 68.0% | 0.0% |
| D80-TCASH20 | 0.2% | 1.4% | 4.5% | 27 | 24.3% | 100.5% | 2.5% |
| E80-TCASH20 | 0.2% | 0.9% | 2.9% | 27 | 14.8% | 142.6% | 15.7% |
| F80-TCASH20 | 0.0% | 0.2% | 1.6% | 28 | 26.4% | 81.0% | 14.5% |
| G80-TCASH20 | 0.0% | 0.0% | 0.6% | 29 | 18.6% | 87.5% | 25.2% |

### Withdrawal rate 5.0% per year

| portfolio | money ran out by year 20 | by year 25 | by year 30 | typical year it ran out (paths that ran out) | real value ever below 50.0% | real value at year 30: typical | real value at year 30: bad case (worst 5%) |
|---|---|---|---|---|---|---|---|
| A | 11.6% | 21.2% | 29.2% | 22 | 47.4% | 85.7% | 0.0% |
| B | 6.8% | 15.6% | 23.5% | 23 | 43.0% | 94.6% | 0.0% |
| C | 8.3% | 21.5% | 35.0% | 24 | 58.5% | 33.4% | 0.0% |
| D | 3.4% | 10.3% | 19.4% | 25 | 40.4% | 76.7% | 0.0% |
| E | 2.6% | 6.9% | 12.4% | 25 | 28.2% | 131.3% | 0.0% |
| F | 0.9% | 6.1% | 17.7% | 27 | 49.8% | 53.3% | 0.0% |
| G | 0.2% | 2.9% | 11.3% | 28 | 41.8% | 63.4% | 0.0% |
| CASH | 50.7% | 100.0% | 100.0% | 20 | 100.0% | 0.0% | 0.0% |
| CASH +1% real (assumption) | 0.0% | 100.0% | 100.0% | 23 | 100.0% | 0.0% | 0.0% |
| G-EW | 0.2% | 2.9% | 10.5% | 27 | 37.6% | 72.8% | 0.0% |
| IEF | 4.5% | 34.9% | 69.4% | 25 | 95.9% | 0.0% | 0.0% |
| TLT | 8.2% | 22.5% | 36.9% | 24 | 61.6% | 26.8% | 0.0% |
| RSP | 14.6% | 22.2% | 28.5% | 20 | 46.3% | 132.1% | 0.0% |
| BONDS | 6.1% | 40.2% | 74.1% | 25 | 96.8% | 0.0% | 0.0% |
| AG | 1.5% | 6.1% | 13.6% | 26 | 33.8% | 100.1% | 0.0% |
| G-CASH | 0.2% | 27.6% | 83.4% | 27 | 99.9% | 0.0% | 0.0% |
| A-CASH | 7.2% | 28.4% | 50.5% | 25 | 80.9% | 0.0% | 0.0% |
| A80-CASH20 | 9.6% | 21.7% | 32.0% | 23 | 53.5% | 48.7% | 0.0% |
| A80-IEF20 | 6.9% | 16.3% | 25.8% | 24 | 44.8% | 79.6% | 0.0% |
| A80-TLT20 | 5.4% | 12.5% | 20.3% | 24 | 38.6% | 108.5% | 0.0% |
| A80-BONDS20 | 7.0% | 16.5% | 26.0% | 24 | 45.4% | 77.9% | 0.0% |
| A80-RSP20 | 8.0% | 16.0% | 22.8% | 23 | 39.8% | 122.3% | 0.0% |
| B80-CASH20 | 5.1% | 16.3% | 28.2% | 25 | 52.6% | 50.6% | 0.0% |
| C80-CASH20 | 7.1% | 24.9% | 44.1% | 25 | 73.7% | 9.1% | 0.0% |
| D80-CASH20 | 2.5% | 11.9% | 27.2% | 26 | 60.7% | 33.7% | 0.0% |
| E80-CASH20 | 1.9% | 7.8% | 17.3% | 26 | 43.0% | 65.8% | 0.0% |
| F80-CASH20 | 0.6% | 9.0% | 31.1% | 27 | 76.0% | 18.4% | 0.0% |
| G80-CASH20 | 0.2% | 5.6% | 24.9% | 28 | 75.1% | 23.7% | 0.0% |
| A80-TCASH20 | 8.6% | 19.6% | 29.8% | 23 | 50.4% | 59.7% | 0.0% |
| B80-TCASH20 | 4.4% | 14.5% | 25.2% | 25 | 48.4% | 61.9% | 0.0% |
| C80-TCASH20 | 6.2% | 21.9% | 39.6% | 25 | 69.0% | 16.7% | 0.0% |
| D80-TCASH20 | 2.2% | 10.5% | 23.6% | 26 | 54.8% | 43.2% | 0.0% |
| E80-TCASH20 | 1.7% | 6.9% | 15.0% | 26 | 38.3% | 78.0% | 0.0% |
| F80-TCASH20 | 0.5% | 6.9% | 25.0% | 27 | 69.1% | 26.9% | 0.0% |
| G80-TCASH20 | 0.1% | 3.6% | 18.6% | 28 | 66.9% | 32.7% | 0.0% |
