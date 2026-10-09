# Long-run withdrawals: 30-year resampled paths

Compares portfolios over 30-year withdrawal paths built by resampling 2005-01 to 2018-12 months. It selects and recommends nothing. Spec: docs/methodology/longrun.md.

- data: up to 2018-12-31 only (validation and holdout stay sealed)
- 10000 paths of 30 years, 12-month blocks drawn from 168 months (circular), seed 20261008; every portfolio sees the same draws
- longrun.yaml sha256: `653071eec3dabadc59db6d0cf5bd50a1a9bd16d4d819a828b983ff9638956d8c`
- decision.yaml sha256: `b6ae095904f8f5eee9f75ef48e617d954953150b889d6bcfef42f6179105db23` (read unchanged)

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
| AG | 0.0% | 0.0% | 0.0% | - | 1.0% | 309.5% | 116.6% |
| G-CASH | 0.0% | 0.0% | 0.0% | - | 0.1% | 110.0% | 74.2% |
| A-CASH | 0.0% | 0.0% | 0.0% | - | 7.2% | 141.4% | 50.8% |

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
| AG | 0.0% | 0.1% | 0.4% | 28 | 6.3% | 217.7% | 53.7% |
| G-CASH | 0.0% | 0.0% | 0.0% | 30 | 41.2% | 54.9% | 25.1% |
| A-CASH | 0.0% | 0.7% | 3.6% | 28 | 33.3% | 79.8% | 4.3% |

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
| AG | 0.1% | 0.9% | 2.5% | 27 | 14.0% | 169.3% | 18.9% |
| G-CASH | 0.0% | 0.1% | 6.6% | 29 | 88.8% | 25.2% | 0.0% |
| A-CASH | 0.6% | 5.4% | 16.0% | 27 | 54.6% | 46.4% | 0.0% |

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
| AG | 1.5% | 6.1% | 13.6% | 26 | 33.8% | 100.1% | 0.0% |
| G-CASH | 0.2% | 27.6% | 83.4% | 27 | 99.9% | 0.0% | 0.0% |
| A-CASH | 7.2% | 28.4% | 50.5% | 25 | 80.9% | 0.0% | 0.0% |
