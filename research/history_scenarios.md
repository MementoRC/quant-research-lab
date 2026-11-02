# History-grounded scenarios: every large fall since 1971

- data cutoff: 2018-12-31 (the end of the research period); validation and holdout data are never read
- episodes: a fall of 15.0% or more from an all-time high of the S&P 500 price index (without dividends), peaks on or after 1971-01-01; the threshold and start date were fixed in the config before any result
- config/history.yaml sha256: `632a1b1642f656616311da2c9ff55105a9e1d9e3cabd0d14c1b7de8239a0690e`
- config/decision.yaml sha256: `88ab8b08a34f8b3d106fd7670af02e3e827b86467a2755eb3620ada4490aa76d`
- config/core_candidates.yaml sha256: `1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3`
- raw GC=F close sha256: `9c06554a68c4529497eae95e13b872374bfee9f4fd508dbca337aa2e44590318`
- raw GLD close sha256: `0e0213d0f5f52a252cc0aa5461d550ab1c341b0ed54f547612c57c59db8500c4`
- raw IEF close sha256: `7c06874365c8a51a8e90ee4d6ebdd4e0f14772ef8ef11766fa307f9aaf67d564`
- raw QQQ close sha256: `67920a4cab0604908e46b25bb90a4a5cc53e2a2a5b2c1fdc74ccb01a38169e4b`
- raw RSP close sha256: `2a344f213c666310cd709183a535c98277d340d99f3d68f100642a8564c42b5f`
- raw SHY close sha256: `aac2b70bafcea09947e6cfd06b04d92e223ee15d9871fed8301c94d1c35fcbe4`
- raw SPY close sha256: `8917072bbd372e7bc478c4afd4ed61766333c269e9992320a5c8f09b45d9f348`
- raw TLT close sha256: `6b6213d467e479b3d5028ce705f81a8f7c61e8f5565d0d4f676ef4ed8e21191a`
- raw ^GSPC close sha256: `72e62d1780c46721f94dbcac8a163f3d0a86cac762f491121dd1be2283d14384`
- raw ^IXIC close sha256: `b58810dde434101ebbeb38954e17502ef4b4f4a32d13075dc5677e2648bf5dbc`
- raw ^SP500TR close sha256: `ba9ebe2a3302ff4292ec57a956a56a1da83ae8cb25162e9995339598f66d23b5`
- raw FRED DGS1 sha256: `e4362509d3800911658df4abaaceeeb482e3aae7c872d27729736d060ac3a7ad`
- raw FRED DGS2 sha256: `f858a0d528f043009e42ae9bf0bb22ae73befdef7ec41b1d8869038a1cc75156`
- raw FRED DGS7 sha256: `e4edddf65e124dabb5b4d80e44a173d232c75761ccea98552cdb3129e3c9ce1d`
- raw FRED DGS20 sha256: `2736929bd43b8951d13e2514afe77044ab5952fb143830bcb537e488e06e26c8`
- raw FRED DGS30 sha256: `1851c4b93b8645746cf1c2dff99aa6b132f088839268fde56507683be6a4d90e`
- raw Shiller dividend yield sha256: `a88544c78f2a194398c8cd5a7c34c7f5968d81a55cee6f173e2d92c4612cdd5a`
- raw World Bank gold sha256: `6695019884f3b4118f79882e4de70dccee90bdf2b236ca024b18b37ade3b1372`
- portfolios compared: 12
- multiple comparisons: 7 in the core comparison, 12 here (A-G again plus 5 new); the more portfolios compared, the likelier the best-looking one is luck

## Episodes

| peak | trough | recovery | S&P 500 depth | length (peak to recovery) | measure window ends |
|---|---|---|---|---|---|
| 1973-01-11 | 1974-10-03 | 1980-07-17 | 48.2% | 90 months | 1983-01-11 |
| 1980-11-28 | 1982-08-12 | 1982-11-03 | 27.1% | 24 months | 1990-11-28 |
| 1987-08-25 | 1987-12-04 | 1989-07-26 | 33.5% | 23 months | 1997-08-25 |
| 1990-07-16 | 1990-10-11 | 1991-02-13 | 19.9% | 7 months | 2000-07-16 |
| 1998-07-17 | 1998-08-31 | 1998-11-23 | 19.3% | 4 months | 2008-07-17 |
| 2000-03-24 | 2002-10-09 | 2007-05-30 | 49.1% | 86 months | 2010-03-24 |
| 2007-10-09 | 2009-03-09 | 2013-03-28 | 56.8% | 65 months | 2017-10-09 |
| 2018-09-20 | 2018-12-24 | not recovered by 2018 | 19.8% | - | 2018-12-31 |

## Stand-in checks

| check (stand-in against the next series) | frequency | overlap | returns | correlation |
|---|---|---|---|---|
| SPY: ^SP500TR against SPY | daily | 1993-02-01 to 2018-12-31 | 6527 | 0.9805 |
| SPY: S&P 500 + Shiller dividends against ^SP500TR | daily | 1988-01-05 to 2018-12-31 | 7811 | 0.9996 |
| QQQ: ^IXIC against QQQ | daily | 1999-03-11 to 2018-12-31 | 4985 | 0.9560 |
| Gold: World Bank monthly figure against the monthly mean of GC=F | monthly | 2000-09 to 2018-12 | 220 | 0.9969 |
| Gold: month-end GC=F against month-end GLD | monthly | 2004-12 to 2018-12 | 169 | 0.9957 |
| SHY: yield proxy against SHY | monthly | 2002-08 to 2018-12 | 197 | 0.9814 |
| IEF: yield proxy against IEF | monthly | 2002-08 to 2018-12 | 197 | 0.9781 |
| TLT: yield proxy against TLT | monthly | 2002-08 to 2018-12 | 197 | 0.9777 |

## Falls summary

| portfolio | median worst loss | deepest loss | median months to recover | longest recovery |
|---|---|---|---|---|
| A | 16.2% (median of 8) | 50.3% (worst of 8: peak 2000-03-24) | 19 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| B | 16.9% (median of 8) | 38.4% (worst of 8: peak 1980-11-28) | 21.5 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| C | 13.2% (median of 8) | 19.1% (worst of 8: peak 2000-03-24) | 13 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| D | 18.0% (median of 8) | 31.4% (worst of 8: peak 2007-10-09) | 26 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| E | 18.6% (median of 8) | 30.5% (worst of 8: peak 2007-10-09) | 23.5 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| F | 8.3% (median of 8) | 19.0% (worst of 8: peak 1980-11-28) | 15.5 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| G | 4.4% (median of 8) | 20.3% (worst of 8: peak 1980-11-28) | 9 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| CASH | 0.1% (median of 8) | 2.5% (worst of 8: peak 1973-01-11) | 0.5 months (median of 8) | 8 months (worst of 8: peak 1973-01-11) |
| G-EW | 4.4% (median of 8) | 20.3% (worst of 8: peak 1980-11-28) | 9 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| AG | 10.3% (median of 8) | 27.5% (worst of 8: peak 2000-03-24) | 17.5 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |
| G-CASH | 1.4% (median of 8) | 8.0% (worst of 8: peak 1980-11-28) | 3 months (median of 8) | 12 months (worst of 8: peak 1980-11-28) |
| A-CASH | 6.4% (median of 8) | 22.5% (worst of 8: peak 2000-03-24) | 9 months (median of 8) | not recovered by 2018 (worst of 8: peak 2018-09-20) |

## Income summary

### Withdrawal 2.0% a year (real balance, % of the start)

| portfolio | 5-year median | 5-year worst | 10-year median | 10-year worst |
|---|---|---|---|---|
| A | 117.6% (median of 7) | 50.4% (worst of 7: peak 2000-03-24) | 166.8% (median of 7) | 45.0% (worst of 7: peak 2000-03-24) |
| B | 93.2% (median of 7) | 82.9% (worst of 7: peak 2000-03-24) | 140.2% (median of 7) | 81.3% (worst of 7: peak 1998-07-17) |
| C | 97.8% (median of 7) | 75.5% (worst of 7: peak 1973-01-11) | 133.7% (median of 7) | 88.4% (worst of 7: peak 1998-07-17) |
| D | 101.9% (median of 7) | 63.2% (worst of 7: peak 1973-01-11) | 137.0% (median of 7) | 61.1% (worst of 7: peak 1973-01-11) |
| E | 97.8% (median of 7) | 74.0% (worst of 7: peak 1973-01-11) | 133.1% (median of 7) | 86.5% (worst of 7: peak 1973-01-11) |
| F | 110.8% (median of 7) | 101.1% (worst of 7: peak 2000-03-24) | 146.0% (median of 7) | 99.7% (worst of 7: peak 1998-07-17) |
| G | 102.8% (median of 7) | 86.9% (worst of 7: peak 1973-01-11) | 125.7% (median of 7) | 88.9% (worst of 7: peak 1973-01-11) |
| CASH | 106.9% (median of 7) | 84.9% (worst of 7: peak 1973-01-11) | 98.6% (median of 7) | 79.4% (worst of 7: peak 2007-10-09) |
| G-EW | 102.8% (median of 7) | 86.9% (worst of 7: peak 1973-01-11) | 128.6% (median of 7) | 88.9% (worst of 7: peak 1973-01-11) |
| AG | 121.9% (median of 7) | 74.8% (worst of 7: peak 2000-03-24) | 142.1% (median of 7) | 82.5% (worst of 7: peak 2000-03-24) |
| G-CASH | 106.6% (median of 7) | 86.1% (worst of 7: peak 1973-01-11) | 112.9% (median of 7) | 85.3% (worst of 7: peak 1973-01-11) |
| A-CASH | 111.3% (median of 7) | 74.7% (worst of 7: peak 2000-03-24) | 129.3% (median of 7) | 73.8% (worst of 7: peak 2000-03-24) |

### Withdrawal 3.3% a year (real balance, % of the start)

| portfolio | 5-year median | 5-year worst | 10-year median | 10-year worst |
|---|---|---|---|---|
| A | 109.4% (median of 7) | 43.7% (worst of 7: peak 2000-03-24) | 142.6% (median of 7) | 28.9% (worst of 7: peak 2000-03-24) |
| B | 85.7% (median of 7) | 75.5% (worst of 7: peak 2000-03-24) | 127.8% (median of 7) | 66.2% (worst of 7: peak 2000-03-24) |
| C | 90.5% (median of 7) | 69.2% (worst of 7: peak 1973-01-11) | 114.1% (median of 7) | 75.3% (worst of 7: peak 1998-07-17) |
| D | 93.7% (median of 7) | 57.3% (worst of 7: peak 1973-01-11) | 117.0% (median of 7) | 46.8% (worst of 7: peak 1973-01-11) |
| E | 90.1% (median of 7) | 68.0% (worst of 7: peak 1973-01-11) | 113.1% (median of 7) | 71.2% (worst of 7: peak 1973-01-11) |
| F | 102.7% (median of 7) | 93.7% (worst of 7: peak 2000-03-24) | 126.8% (median of 7) | 85.9% (worst of 7: peak 1998-07-17) |
| G | 94.0% (median of 7) | 80.7% (worst of 7: peak 1973-01-11) | 106.5% (median of 7) | 74.6% (worst of 7: peak 1973-01-11) |
| CASH | 99.7% (median of 7) | 78.6% (worst of 7: peak 1973-01-11) | 84.7% (median of 7) | 66.5% (worst of 7: peak 2007-10-09) |
| G-EW | 94.0% (median of 7) | 80.7% (worst of 7: peak 1973-01-11) | 111.2% (median of 7) | 74.6% (worst of 7: peak 1973-01-11) |
| AG | 114.7% (median of 7) | 67.8% (worst of 7: peak 2000-03-24) | 121.5% (median of 7) | 65.6% (worst of 7: peak 2000-03-24) |
| G-CASH | 99.0% (median of 7) | 79.8% (worst of 7: peak 1973-01-11) | 97.4% (median of 7) | 71.1% (worst of 7: peak 1973-01-11) |
| A-CASH | 103.3% (median of 7) | 67.9% (worst of 7: peak 2000-03-24) | 112.0% (median of 7) | 58.4% (worst of 7: peak 2000-03-24) |

### Withdrawal 4.0% a year (real balance, % of the start)

| portfolio | 5-year median | 5-year worst | 10-year median | 10-year worst |
|---|---|---|---|---|
| A | 104.9% (median of 7) | 40.1% (worst of 7: peak 2000-03-24) | 129.5% (median of 7) | 20.2% (worst of 7: peak 2000-03-24) |
| B | 81.7% (median of 7) | 71.6% (worst of 7: peak 2000-03-24) | 121.1% (median of 7) | 57.5% (worst of 7: peak 2000-03-24) |
| C | 86.6% (median of 7) | 65.8% (worst of 7: peak 1973-01-11) | 103.6% (median of 7) | 68.3% (worst of 7: peak 1998-07-17) |
| D | 89.2% (median of 7) | 54.1% (worst of 7: peak 1973-01-11) | 106.2% (median of 7) | 39.0% (worst of 7: peak 1973-01-11) |
| E | 86.0% (median of 7) | 64.7% (worst of 7: peak 1973-01-11) | 102.3% (median of 7) | 63.0% (worst of 7: peak 1973-01-11) |
| F | 98.4% (median of 7) | 89.7% (worst of 7: peak 2000-03-24) | 116.5% (median of 7) | 78.4% (worst of 7: peak 1998-07-17) |
| G | 89.2% (median of 7) | 77.4% (worst of 7: peak 1973-01-11) | 97.4% (median of 7) | 66.9% (worst of 7: peak 1973-01-11) |
| CASH | 95.9% (median of 7) | 75.2% (worst of 7: peak 1973-01-11) | 77.2% (median of 7) | 59.2% (worst of 7: peak 1973-01-11) |
| G-EW | 89.3% (median of 7) | 77.4% (worst of 7: peak 1973-01-11) | 101.9% (median of 7) | 66.9% (worst of 7: peak 1973-01-11) |
| AG | 110.8% (median of 7) | 64.0% (worst of 7: peak 2000-03-24) | 110.5% (median of 7) | 56.5% (worst of 7: peak 2000-03-24) |
| G-CASH | 95.0% (median of 7) | 76.4% (worst of 7: peak 1973-01-11) | 89.0% (median of 7) | 63.4% (worst of 7: peak 1973-01-11) |
| A-CASH | 99.0% (median of 7) | 64.3% (worst of 7: peak 2000-03-24) | 102.6% (median of 7) | 50.1% (worst of 7: peak 2000-03-24) |

### Withdrawal 5.0% a year (real balance, % of the start)

| portfolio | 5-year median | 5-year worst | 10-year median | 10-year worst |
|---|---|---|---|---|
| A | 98.6% (median of 7) | 34.9% (worst of 7: peak 2000-03-24) | 110.9% (median of 7) | 7.7% (worst of 7: peak 2000-03-24) |
| B | 75.9% (median of 7) | 65.9% (worst of 7: peak 2000-03-24) | 104.8% (median of 7) | 45.1% (worst of 7: peak 2000-03-24) |
| C | 81.1% (median of 7) | 61.0% (worst of 7: peak 1973-01-11) | 88.5% (median of 7) | 58.3% (worst of 7: peak 1998-07-17) |
| D | 82.9% (median of 7) | 49.5% (worst of 7: peak 1973-01-11) | 90.8% (median of 7) | 28.0% (worst of 7: peak 1973-01-11) |
| E | 80.1% (median of 7) | 60.1% (worst of 7: peak 1973-01-11) | 86.9% (median of 7) | 51.2% (worst of 7: peak 1973-01-11) |
| F | 92.3% (median of 7) | 84.1% (worst of 7: peak 2000-03-24) | 101.8% (median of 7) | 67.8% (worst of 7: peak 1998-07-17) |
| G | 83.2% (median of 7) | 72.6% (worst of 7: peak 1973-01-11) | 84.3% (median of 7) | 55.9% (worst of 7: peak 1973-01-11) |
| CASH | 90.4% (median of 7) | 70.3% (worst of 7: peak 1973-01-11) | 66.5% (median of 7) | 48.3% (worst of 7: peak 1973-01-11) |
| G-EW | 83.9% (median of 7) | 72.6% (worst of 7: peak 1973-01-11) | 88.5% (median of 7) | 55.9% (worst of 7: peak 1973-01-11) |
| AG | 105.2% (median of 7) | 58.5% (worst of 7: peak 2000-03-24) | 94.6% (median of 7) | 43.5% (worst of 7: peak 2000-03-24) |
| G-CASH | 89.2% (median of 7) | 71.5% (worst of 7: peak 1973-01-11) | 77.1% (median of 7) | 52.4% (worst of 7: peak 1973-01-11) |
| A-CASH | 92.8% (median of 7) | 59.1% (worst of 7: peak 2000-03-24) | 89.3% (median of 7) | 38.2% (worst of 7: peak 2000-03-24) |

## Per-episode detail

Columns are episodes, named by their peak date.

### Worst loss in the measure window

| portfolio | 1973-01-11 | 1980-11-28 | 1987-08-25 | 1990-07-16 | 1998-07-17 | 2000-03-24 | 2007-10-09 | 2018-09-20 |
|---|---|---|---|---|---|---|---|---|
| A | 4.7% †‡ | 23.7% †‡ | 14.6% †‡ | 5.3% †‡ | 17.3% †‡ | 50.3% †‡ | 23.8% | 15.2% |
| B | 7.6% †‡ | 38.4% †‡ | 20.4% †‡ | 9.6% †‡ | 13.4% †‡ | 23.6% †‡ | 33.3% | 10.4% |
| C | 17.8% † | 11.5% † | 15.7% † | 11.5% † | 12.5% † | 19.1% † | 13.9% | 12.6% |
| D | 29.9% † | 14.7% † | 23.7% † | 12.1% † | 10.0% † | 21.3% † | 31.4% | 10.8% |
| E | 16.5% †‡ | 20.7% †‡ | 22.1% †‡ | 10.6% †‡ | 11.4% †‡ | 24.5% †‡ | 30.5% | 10.5% |
| F | 5.5% †‡ | 19.0% †‡ | 13.3% †‡ | 6.0% †‡ | 6.1% †‡ | 10.5% †‡ | 14.3% | 5.7% |
| G | 0.9% †‡ | 20.3% †‡ | 13.7% †‡ | 4.8% †‡ | 3.5% †‡ | 4.1% †‡ | 7.4% | 2.5% |
| CASH | 2.5% † | 1.2% † | 1.5% † | 0.0% † | 0.0% † | 0.0% † | 0.1% | 0.1% |
| G-EW | 0.9% †‡ | 20.3% †‡ | 13.7% †‡ | 4.8% †‡ | 3.5% †‡ | 4.1% †‡ | 9.2% | 2.7% |
| AG | 2.7% †‡ | 20.5% †‡ | 10.4% †‡ | 3.2% †‡ | 10.1% †‡ | 27.5% †‡ | 15.3% | 8.5% |
| G-CASH | 0.7% †‡ | 8.0% †‡ | 7.5% †‡ | 2.1% †‡ | 0.9% †‡ | 1.8% †‡ | 0.1% | 1.1% |
| A-CASH | 2.6% †‡ | 5.3% †‡ | 5.1% †‡ | 2.5% †‡ | 7.7% †‡ | 22.5% †‡ | 8.0% | 7.4% |

### Months from the peak to recover

| portfolio | 1973-01-11 | 1980-11-28 | 1987-08-25 | 1990-07-16 | 1998-07-17 | 2000-03-24 | 2007-10-09 | 2018-09-20 |
|---|---|---|---|---|---|---|---|---|
| A | 1 months †‡ | 23 months †‡ | 22 months †‡ | 1 months †‡ | 5 months †‡ | 137 months †‡ | 16 months | not recovered by 2018 |
| B | 4 months †‡ | 29 months †‡ | 21 months †‡ | 7 months †‡ | 6 months †‡ | 35 months †‡ | 22 months | not recovered by 2018 |
| C | 26 months † | 12 months † | 5 months † | 7 months † | 5 months † | 30 months † | 14 months | not recovered by 2018 |
| D | 36 months † | 12 months † | 17 months † | 6 months † | 3 months † | 45 months † | 35 months | not recovered by 2018 |
| E | 24 months †‡ | 23 months †‡ | 21 months †‡ | 6 months †‡ | 4 months †‡ | 45 months †‡ | 26 months | not recovered by 2018 |
| F | 4 months †‡ | 22 months †‡ | 17 months †‡ | 6 months †‡ | 4 months †‡ | 18 months †‡ | 14 months | not recovered by 2018 |
| G | 1 months †‡ | 22 months †‡ | 16 months †‡ | 4 months †‡ | 2 months †‡ | 3 months †‡ | 14 months | not recovered by 2018 |
| CASH | 8 months † | 1 months † | 2 months † | 0 months † | 0 months † | 0 months † | 0 months | 1 months |
| G-EW | 1 months †‡ | 22 months †‡ | 16 months †‡ | 4 months †‡ | 2 months †‡ | 3 months †‡ | 14 months | not recovered by 2018 |
| AG | 1 months †‡ | 22 months †‡ | 21 months †‡ | 1 months †‡ | 4 months †‡ | 46 months †‡ | 14 months | not recovered by 2018 |
| G-CASH | 1 months †‡ | 12 months †‡ | 5 months †‡ | 3 months †‡ | 2 months †‡ | 3 months †‡ | 12 months | 3 months |
| A-CASH | 1 months †‡ | 1 months †‡ | 18 months †‡ | 1 months †‡ | 4 months †‡ | 46 months †‡ | 14 months | not recovered by 2018 |

### Real balance 10 years after the peak, withdrawing 2.0% a year

| portfolio | 1973-01-11 | 1980-11-28 | 1987-08-25 | 1990-07-16 | 1998-07-17 | 2000-03-24 | 2007-10-09 | 2018-09-20 |
|---|---|---|---|---|---|---|---|---|
| A | 224.0% †‡ | 81.0% †‡ | 166.8% †‡ | 477.6% †‡ | 113.5% †‡ | 45.0% †‡ | 188.4% | n/a (data ends) |
| B | 140.2% †‡ | 122.3% †‡ | 161.6% †‡ | 235.6% †‡ | 81.3% †‡ | 82.3% †‡ | 159.2% | n/a (data ends) |
| C | 133.3% † | 335.5% † | 212.1% † | 230.3% † | 88.4% † | 106.1% † | 133.7% | n/a (data ends) |
| D | 61.1% † | 198.4% † | 186.9% † | 243.9% † | 95.6% † | 83.3% † | 137.0% | n/a (data ends) |
| E | 86.5% †‡ | 133.1% †‡ | 143.4% †‡ | 196.5% †‡ | 107.1% †‡ | 95.9% †‡ | 141.1% | n/a (data ends) |
| F | 102.2% †‡ | 171.3% †‡ | 160.9% †‡ | 196.7% †‡ | 99.7% †‡ | 108.7% †‡ | 146.0% | n/a (data ends) |
| G | 88.9% †‡ | 125.7% †‡ | 117.6% †‡ | 139.3% †‡ | 123.5% †‡ | 127.1% †‡ | 129.9% | n/a (data ends) |
| CASH | 81.0% † | 163.4% † | 116.1% † | 113.9% † | 96.7% † | 98.6% † | 79.4% | n/a (data ends) |
| G-EW | 88.9% †‡ | 125.7% †‡ | 117.4% †‡ | 138.9% †‡ | 128.6% †‡ | 136.3% †‡ | 134.9% | n/a (data ends) |
| AG | 144.9% †‡ | 102.5% †‡ | 142.1% †‡ | 270.9% †‡ | 126.2% †‡ | 82.5% †‡ | 162.7% | n/a (data ends) |
| G-CASH | 85.3% †‡ | 144.6% †‡ | 117.4% †‡ | 126.5% †‡ | 109.9% †‡ | 112.9% †‡ | 102.5% | n/a (data ends) |
| A-CASH | 138.7% †‡ | 116.9% †‡ | 141.4% †‡ | 247.7% †‡ | 113.5% †‡ | 73.8% †‡ | 129.3% | n/a (data ends) |

### Real balance 10 years after the peak, withdrawing 3.3% a year

| portfolio | 1973-01-11 | 1980-11-28 | 1987-08-25 | 1990-07-16 | 1998-07-17 | 2000-03-24 | 2007-10-09 | 2018-09-20 |
|---|---|---|---|---|---|---|---|---|
| A | 208.6% †‡ | 66.9% †‡ | 142.6% †‡ | 437.1% †‡ | 101.0% †‡ | 28.9% †‡ | 165.5% | n/a (data ends) |
| B | 127.8% †‡ | 101.1% †‡ | 137.0% †‡ | 209.4% †‡ | 68.8% †‡ | 66.2% †‡ | 136.2% | n/a (data ends) |
| C | 109.7% † | 306.5% † | 186.3% † | 206.0% † | 75.3% † | 89.0% † | 114.1% | n/a (data ends) |
| D | 46.8% † | 175.1% † | 162.9% † | 218.4% † | 81.6% † | 68.9% † | 117.0% | n/a (data ends) |
| E | 71.2% †‡ | 113.1% †‡ | 122.2% †‡ | 173.9% †‡ | 91.4% †‡ | 79.7% †‡ | 121.5% | n/a (data ends) |
| F | 88.8% †‡ | 148.9% †‡ | 139.2% †‡ | 175.0% †‡ | 85.9% †‡ | 92.3% †‡ | 126.8% | n/a (data ends) |
| G | 74.6% †‡ | 106.5% †‡ | 100.3% †‡ | 121.8% †‡ | 106.5% †‡ | 109.9% †‡ | 113.5% | n/a (data ends) |
| CASH | 66.8% † | 144.3% † | 100.4% † | 98.5% † | 83.0% † | 84.7% † | 66.5% | n/a (data ends) |
| G-EW | 74.6% †‡ | 106.5% †‡ | 100.1% †‡ | 121.5% †‡ | 111.2% †‡ | 118.4% †‡ | 118.4% | n/a (data ends) |
| AG | 130.0% †‡ | 86.0% †‡ | 121.5% †‡ | 243.5% †‡ | 111.4% †‡ | 65.6% †‡ | 143.0% | n/a (data ends) |
| G-CASH | 71.1% †‡ | 125.4% †‡ | 100.9% †‡ | 110.0% †‡ | 94.7% †‡ | 97.4% †‡ | 88.0% | n/a (data ends) |
| A-CASH | 123.9% †‡ | 100.4% †‡ | 121.8% †‡ | 222.0% †‡ | 100.1% †‡ | 58.4% †‡ | 112.0% | n/a (data ends) |

### Real balance 10 years after the peak, withdrawing 4.0% a year

| portfolio | 1973-01-11 | 1980-11-28 | 1987-08-25 | 1990-07-16 | 1998-07-17 | 2000-03-24 | 2007-10-09 | 2018-09-20 |
|---|---|---|---|---|---|---|---|---|
| A | 200.3% †‡ | 59.2% †‡ | 129.5% †‡ | 415.3% †‡ | 94.2% †‡ | 20.2% †‡ | 153.1% | n/a (data ends) |
| B | 121.1% †‡ | 89.7% †‡ | 123.7% †‡ | 195.4% †‡ | 62.1% †‡ | 57.5% †‡ | 123.8% | n/a (data ends) |
| C | 97.1% † | 290.8% † | 172.5% † | 193.0% † | 68.3% † | 79.9% † | 103.6% | n/a (data ends) |
| D | 39.0% † | 162.5% † | 150.0% † | 204.7% † | 74.1% † | 61.2% † | 106.2% | n/a (data ends) |
| E | 63.0% †‡ | 102.3% †‡ | 110.8% †‡ | 161.7% †‡ | 82.9% †‡ | 70.9% †‡ | 110.9% | n/a (data ends) |
| F | 81.6% †‡ | 136.8% †‡ | 127.6% †‡ | 163.4% †‡ | 78.4% †‡ | 83.5% †‡ | 116.5% | n/a (data ends) |
| G | 66.9% †‡ | 96.1% †‡ | 91.0% †‡ | 112.4% †‡ | 97.4% †‡ | 100.6% †‡ | 104.7% | n/a (data ends) |
| CASH | 59.2% † | 134.1% † | 92.0% † | 90.2% † | 75.6% † | 77.2% † | 59.6% | n/a (data ends) |
| G-EW | 66.9% †‡ | 96.1% †‡ | 90.8% †‡ | 112.1% †‡ | 101.9% †‡ | 108.7% †‡ | 109.5% | n/a (data ends) |
| AG | 122.0% †‡ | 77.1% †‡ | 110.5% †‡ | 228.8% †‡ | 103.4% †‡ | 56.5% †‡ | 132.4% | n/a (data ends) |
| G-CASH | 63.4% †‡ | 115.1% †‡ | 92.1% †‡ | 101.2% †‡ | 86.5% †‡ | 89.0% †‡ | 80.2% | n/a (data ends) |
| A-CASH | 116.0% †‡ | 91.6% †‡ | 111.3% †‡ | 208.1% †‡ | 92.8% †‡ | 50.1% †‡ | 102.6% | n/a (data ends) |

### Real balance 10 years after the peak, withdrawing 5.0% a year

| portfolio | 1973-01-11 | 1980-11-28 | 1987-08-25 | 1990-07-16 | 1998-07-17 | 2000-03-24 | 2007-10-09 | 2018-09-20 |
|---|---|---|---|---|---|---|---|---|
| A | 188.4% †‡ | 48.3% †‡ | 110.9% †‡ | 384.1% †‡ | 84.6% †‡ | 7.7% †‡ | 135.4% | n/a (data ends) |
| B | 111.6% †‡ | 73.4% †‡ | 104.8% †‡ | 175.3% †‡ | 52.5% †‡ | 45.1% †‡ | 106.1% | n/a (data ends) |
| C | 78.9% † | 268.5% † | 152.6% † | 174.3% † | 58.3% † | 66.8% † | 88.5% | n/a (data ends) |
| D | 28.0% † | 144.6% † | 131.5% † | 185.2% † | 63.4% † | 50.1% † | 90.8% | n/a (data ends) |
| E | 51.2% †‡ | 86.9% †‡ | 94.5% †‡ | 144.3% †‡ | 70.8% †‡ | 58.5% †‡ | 95.8% | n/a (data ends) |
| F | 71.3% †‡ | 119.6% †‡ | 110.9% †‡ | 146.7% †‡ | 67.8% †‡ | 70.9% †‡ | 101.8% | n/a (data ends) |
| G | 55.9% †‡ | 81.3% †‡ | 77.8% †‡ | 99.0% †‡ | 84.3% †‡ | 87.4% †‡ | 92.0% | n/a (data ends) |
| CASH | 48.3% † | 119.5% † | 79.9% † | 78.4% † | 65.1% † | 66.5% † | 49.7% | n/a (data ends) |
| G-EW | 55.9% †‡ | 81.3% †‡ | 77.6% †‡ | 98.6% †‡ | 88.5% †‡ | 94.8% †‡ | 96.8% | n/a (data ends) |
| AG | 110.6% †‡ | 64.4% †‡ | 94.6% †‡ | 207.7% †‡ | 92.1% †‡ | 43.5% †‡ | 117.3% | n/a (data ends) |
| G-CASH | 52.4% †‡ | 100.4% †‡ | 79.4% †‡ | 88.6% †‡ | 74.7% †‡ | 77.1% †‡ | 69.0% | n/a (data ends) |
| A-CASH | 104.6% †‡ | 79.0% †‡ | 96.2% †‡ | 188.3% †‡ | 82.5% †‡ | 38.2% †‡ | 89.3% | n/a (data ends) |

## Labels

- † the portfolio can hold a fund (either branch of a switching rule, every part of a blend) whose prices are stand-in data on some day of the cell's window.
- ‡ the portfolio can hold GLD and the window includes days before the first gold futures close, where gold is the interpolated World Bank monthly average.
- A cell can carry both. Summary cells mix marked and unmarked episodes; see the per-episode tables.
- no signal yet: the peak is before the portfolio's first return day (a switching rule needs 200 days of history). First return days: A 1971-11-22, B 1971-11-22, C 1971-11-22, D 1971-02-09, E 1971-02-09, F 1971-11-22, G 1971-02-09, CASH 1971-02-09, G-EW 1971-02-09, AG 1971-11-22, G-CASH 1971-02-09, A-CASH 1971-11-22.
- n/a (data ends): the horizon ends after the data does. The 5-year and 10-year columns therefore have different counts.

## Caveats

- There are few episodes (about 10), so a median is a rough guide and every episode is shown on its own row.
- Stand-ins are not the funds: before a fund existed, an index, a yield-based bond proxy or a gold price stands in for it. The stand-in checks above show how closely each tracks the fund where they overlap.
- Gold before 2000 is a World Bank monthly average placed on month ends and interpolated daily, which makes it smoother than gold really was.
- RSP is approximated by the S&P 500 (total return) before it existed; it has no check.
- Every portfolio uses daily rebalancing to its target weights at the engine's normal cost.
- Withdrawals are nominal amounts raised by CPI each January; balances are shown in real terms.
- This report selects nothing and recommends nothing.
