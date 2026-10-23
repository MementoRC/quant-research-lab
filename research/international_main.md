# International final test: set main

Spec: docs/methodology/international-test.md. One sealed run; the verdict is final for this rule.

- Rule: designated core: subject not validated (owner-designated; failed fixed standalone attempt, test 1496), core_trend {"lookback": 200, "risk_off": "GLD", "risk_on": "QQQ"}; equity leg QQQ (derived)
- Ledger international event 1; data frozen at 2026-10-21
- international.yaml sha256: `27547d2e4e18fce6f3edc4a90c6e3c2ef90341a836f55a88a1e141de11e80568`
- Rule fingerprint: `ad4e69afc23a`
- Data fingerprint: `ced641b407d0`
- **subject not validated (owner-designated; failed fixed standalone attempt, test 1496)**
- Cash: uninvested weight earned the 3-month T-bill rate (FRED DTB3, lagged one business day). The US research, validation and holdout results used 0% cash, so a rule that holds cash scores somewhat better here than under the US convention.

## Verdict

0 of 7 markets passed (need 5); average Sharpe gain -0.21. Verdict: **FAIL**.

This rule can hold gold and the gold check did not pass (GC=F vs GLD correlation 0.93), so it is scored on the late window only.

## Markets

| Market | Scored days | Sharpe | B&H Sharpe | Gain | CAGR | B&H CAGR | Max DD | B&H max DD | Passed |
|---|---|---|---|---|---|---|---|---|---|
| EWJ | 954 | 0.81 | 1.03 | -0.22 | 14.0% | 19.0% | 21.2% | 14.7% | no |
| EWU | 954 | 0.98 | 1.14 | -0.16 | 13.8% | 16.5% | 14.3% | 12.6% | no |
| EWG | 954 | 0.71 | 1.02 | -0.31 | 11.4% | 17.5% | 22.8% | 15.8% | no |
| EWC | 954 | 1.20 | 1.29 | -0.10 | 17.9% | 20.1% | 15.8% | 13.0% | no |
| EWA | 954 | 0.62 | 0.66 | -0.04 | 9.4% | 11.0% | 22.1% | 21.9% | no |
| EWL | 954 | 0.67 | 0.95 | -0.28 | 9.4% | 13.8% | 14.4% | 13.5% | no |
| EWQ | 954 | 0.27 | 0.62 | -0.36 | 3.2% | 9.7% | 23.3% | 15.2% | no |

## Per window (information only; the verdict uses the joined series)

- EWJ 2023-01-01 to 2026-10-21: 954 days, Sharpe 0.81 vs 1.03
- EWU 2023-01-01 to 2026-10-21: 954 days, Sharpe 0.98 vs 1.14
- EWG 2023-01-01 to 2026-10-21: 954 days, Sharpe 0.71 vs 1.02
- EWC 2023-01-01 to 2026-10-21: 954 days, Sharpe 1.20 vs 1.29
- EWA 2023-01-01 to 2026-10-21: 954 days, Sharpe 0.62 vs 0.66
- EWL 2023-01-01 to 2026-10-21: 954 days, Sharpe 0.67 vs 0.95
- EWQ 2023-01-01 to 2026-10-21: 954 days, Sharpe 0.27 vs 0.62
