# Balance-sheet fragility screen — design

Date: 2026-10-05. Status: approved in conversation (owner, 2026-10-05), pending written-spec review.

## In plain words

This tool looks at the published finances of listed US companies and flags the
ones that look fragile if borrowing stays expensive: too little profit to cover
interest, too much debt compared with the cash the business generates, a lot of
debt falling due soon, or a rising cost of that debt. Each flag comes with the
reason.

It does NOT predict prices and does NOT pick stocks to buy. It cannot judge
private companies or companies that do not file with the SEC (for example
foreign companies that file 20-F), and it deliberately skips banks, insurers,
brokers and property trusts, where debt is part of the business. It is unproven
as a return signal: the EDGAR-based factor families tested so far (run 6)
produced no candidate that passed the beat-the-null rule (see the run's ledger
notes). Its only
job is to be a pre-registered filter that could keep fragile companies out of
the sleeve's universe, if the owner later decides so.

## Purpose

Owner choice (b): a pre-registered filter that can exclude fragile companies
from the sleeve's universe.

- Stage 1 (this spec): the point-in-time large-cap universe
  (`config/universe_pit.yaml`), an on-demand run, a report plus a dashboard
  section, and a point-in-time filter function. The screen runs on every
  member of the PIT universe's latest month-end (`top_n` from
  `config/universe_pit.yaml`, about 300 names). This is the universe the
  sleeve's factor runs use, as opposed to the dashboard's static 100-ticker
  universe.
- Stage 2 (named, OUT OF SCOPE, separate spec later): a mid/small-cap
  discovery watchlist of US filers with strong cash flow and solid balance
  sheets. It needs a broader filer list and price data, and its survivorship
  bias is worse (today's listed filers only, so companies that failed are
  missing). Not designed here.

It is EXPLORATION ONLY until a dated PLAN.md amendment says otherwise. It
changes no existing run, config or result.

## Data it builds on

- `qrl.fundamentals`: `parse_companyfacts(ticker, payload, concepts)` (the
  `concepts` argument takes any taxonomy -> concept list), `pit_panel`,
  `pit_panel_fallback`, `filter_duration`, `ANNUAL_DAYS`, `STALENESS_DAYS`,
  `normalize_ticker`, `_map_to_dates`.
- `qrl.factor_data`: `_read_cached_payload`, the pool.csv ticker -> CIK map
  (`data/cache/pit/pool.csv`), and `qrl.pit_universe.CIK_PREDECESSORS` /
  `merge_predecessor_facts` for companies whose history sits under an older CIK.
- `qrl.pit_universe.load_pit_universe()` (sha-verified membership CSV) and
  `membership_mask`'s rule: a month-end's membership applies from the next
  trading day.

Point-in-time rule, reused unchanged: a fact is usable at date t iff its
`filed` date is STRICTLY BEFORE t (public from the next session), the latest
period `end` wins, ties go to the latest `filed` (restatements count once
public), and nothing older than `STALENESS_DAYS` (456) after its period end is
used. Period end is never used to decide availability.

## Data gaps (what the existing loader does not have)

| gap | consequence in this spec |
|---|---|
| `FEATURE_CONCEPTS` / `CONCEPTS` hold only revenue, income, assets and share concepts. No debt, interest, cash, cash-flow, current-asset/liability, retained-earnings or maturity concepts are parsed. | The screen defines its own `FRAGILITY_CONCEPTS` dict and calls `parse_companyfacts` with it on the raw cached payloads (which contain every tag). `load_factor_facts` hardcodes `FEATURE_CONCEPTS`, so a small sibling loader `load_fragility_facts` reuses `_read_cached_payload` and `merge_predecessor_facts`. `factor_data` itself is not edited. |
| No SIC codes anywhere: companyfacts has none, and no loader fetches `data.sec.gov/submissions/CIK##########.json`. | New `load_sic(cik)` using `fundamentals._cached_json` / `_http_get` (same host allowlist and User-Agent rules), cached under `data/cache/sec/submissions/`. Fetched only with `--fetch-sic`; otherwise cache only. Unknown SIC and not on the config override list -> INSUFFICIENT DATA (reason "industry unknown"), never assumed non-financial. |
| `ttm_panel` needs discrete quarters; 10-Q cash-flow items (operating cash flow, capex) and often interest expense are year-to-date only, so TTM would be NaN. | Stage 1 uses the latest FISCAL YEAR (10-K, 350-380 day) flows, not trailing four quarters. Data can be up to ~15 months old; the report shows each company's fiscal-year end used. Quarterly/TTM via YTD differencing is a later refinement, not in stage 1. |
| `pit_panel` is a dates x tickers panel; the screen needs one date. | Called with a one-row `dates` index of the as-of date. |
| The companyfacts cache covers today's listed filers. A past member that delisted has no payload. | Its measures are unavailable -> INSUFFICIENT DATA. Stated, not hidden: the as-of filter is only as complete as the cache. |

## Measures

All flows are the latest fiscal year (annual duration) known at the as-of
date; balance-sheet items are the latest instant of that same fiscal year-end
(`pit_panel` default for instants). Concepts are tried in order, first
available wins. Any missing input makes that measure `unavailable (reason)`;
nothing is imputed, no zero is assumed. One exception, stated so it is not
silent: if total debt is itself reported as exactly 0, coverage, net debt/FCF
and the rate trend are "no debt" (available, not breached).

Shared definitions:

- Debt = `LongTermDebt` (total, includes current portion); else
  `LongTermDebtNoncurrent` + `LongTermDebtCurrent`; (+ `ShortTermBorrowings`
  when reported). Finance/operating leases are excluded (inconsistent tagging).
  Amended run 5: further fallbacks (a)-(d), including convertible-only
  filers (d, added after an audit found DASH/PANW misread as no-debt), and an
  untagged no-debt rule, see Amendments 2026-10-05 (run 5). Amended run 6: the
  split form also accepts `LongTermDebtNoncurrent` + `DebtCurrent`, see
  Amendments 2026-10-06 (run 6).
- Cash = `CashAndCashEquivalentsAtCarryingValue` (amended run 6: else
  `CashAndCashEquivalentsFairValueDisclosure`) + `ShortTermInvestments`
  (or `MarketableSecuritiesCurrent`) when tagged, else cash alone.
- Interest expense = `InterestExpense`; else `InterestExpenseDebt`; else
  `InterestAndDebtExpense`; else `InterestExpenseNonoperating` (amended run 5).
- EBIT = `OperatingIncomeLoss`; else
  `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest`
  (amended run 6: else
  `IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments`)
  + interest expense.
- FCF = `NetCashProvidedByUsedInOperatingActivities` (amended run 6: else
  `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`) −
  `PaymentsToAcquirePropertyPlantAndEquipment` (else
  `PaymentsToAcquireProductiveAssets`).

| # | Measure | Formula | Notes |
|---|---|---|---|
| 1 | Interest coverage | EBIT / interest expense | Interest expense must be > 0. |
| 2 | Net debt / FCF | (Debt − cash) / FCF | Net debt <= 0: no breach (net cash). Net debt > 0 and FCF <= 0: breach, shown as "FCF <= 0". |
| 3 | Near-term maturities | (`LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths` + `...InYearTwo` + `...InYearThree`) / (cash + FCF) | All three tags needed. Denominator <= 0 with maturities > 0: breach. |
| 4 | Effective rate trend | Rate = interest expense / average of opening and closing debt; change = latest FY rate − rate three fiscal years earlier (year-end within +-45 days, as `assets_lag1y_panel`) | Needs four year-end debt values and two interest values. Shown in percentage points. Skipped (ok, available) when net debt <= 5% of assets (amendment after run 3). |
| 5 | Altman Z'' | 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4 + 3.25 | X1 = (`AssetsCurrent` − `LiabilitiesCurrent`) / `Assets`; X2 = `RetainedEarningsAccumulatedDeficit` / `Assets`; X3 = EBIT / `Assets`; X4 = `StockholdersEquity` / `Liabilities`. |
| 6 | Piotroski F-score | Nine 0/1 signals, sum 0-9 | Needs two consecutive fiscal years (below). |

Why Z'' (the non-manufacturer version): it drops the sales/assets term and uses
book equity instead of market value, so it needs no price data (a hard rule
here) and is not distorted by capital-light or service businesses. The +3.25
constant form is used, so the standard zones apply (below 1.1 distress, above
2.6 safe). `Liabilities` missing: `Assets` − `StockholdersEquity`; if neither,
unavailable. An unclassified balance sheet (no `AssetsCurrent`) is unavailable.

Piotroski signals (current year vs prior year): ROA > 0 (`NetIncomeLoss` /
`Assets`); operating cash flow > 0; ROA up; operating cash flow > net income;
long-term debt / average assets down; current ratio up; shares not increased
(`WeightedAverageNumberOfSharesOutstandingBasic`); gross margin up (gross
profit from `GrossProfit`, else revenue − cost via `fundamentals.REVENUE_CONCEPTS`
(amended run 6: plus `RevenueFromContractWithCustomerIncludingAssessedTax`,
fragility only) and `COST_CONCEPTS`); asset turnover (revenue / assets) up. Any signal that
cannot be computed makes the whole score unavailable; a partial score is never
reported.

Financial firms: SIC 6000-6799 (banks, brokers, insurers, trusts, REITs 6798)
-> every measure and the class are "NOT APPLICABLE" (debt is their raw
material; these ratios mislead). SIC comes from the submissions loader above;
`config/fragility.yaml` also holds a small pre-registered `not_applicable`
ticker list as an override for tickers whose SIC is missing or wrong.

## Classification — `config/fragility.yaml`

New, pre-registered and committed before any run. Header comment (like
`core_shortlist.yaml`): fixed before the first run; changes only by dated
amendment comment. Its sha256 is recorded in every report. The thresholds are
judgment calls fixed before seeing results; nobody tunes them after a look.

| key | value | one-line rationale |
|---|---|---|
| `version` | 1 | |
| `date`, `decided_by` | 2026-10-05, owner | |
| `breach_to_fragile` (N) | 1 | owner: any single failed check flags the company, stricter filter |
| `min_available_for_sound` (K) | 4 | SOUND must rest on most of the six measures |
| `interest_coverage_min` | 2.0 | below 2x, a modest profit dip means unpaid interest |
| `net_debt_to_fcf_max` | 6.0 | more than six years of free cash flow to repay net debt |
| `maturities_to_liquidity_max` | 1.0 | years 1-3 repayments exceed cash plus a year of FCF |
| `altman_z_min` | 1.1 | Altman's distress zone for Z'' |
| `piotroski_max_weak` | 2 | score 0-2 is the weak group in Piotroski's study |
| `rate_rise_max_pp` | 2.0 | effective rate up more than 2 points in three years |
| `rate_trend_min_net_debt_to_assets` | 0.05 | rate trend skipped (ok) when net debt <= 5% of assets; added after run 3 |
| `not_applicable_sic` | [[6000, 6799]] | financials |
| `not_applicable_tickers` | [] | override list, empty at registration |

`load_fragility_config(path) -> (FragilityConfig, sha256)` raises `ValueError`
on: a wrong `version`; any threshold missing, non-numeric or <= 0 (rate rise
and coverage must be positive); `breach_to_fragile` not in 1..6;
`min_available_for_sound` not in 1..6; malformed or inverted SIC ranges;
duplicate or non-string override tickers; unknown keys.

Class rules, in this order:

1. NOT APPLICABLE: financial firm (above).
2. FRAGILE: breaches >= N (`breach_to_fragile`).
3. WATCH: 1 <= breaches < N. Empty when N = 1 (owner decision 2026-10-05: N = 1),
   so every breaching company is FRAGILE; the rule stays general so a later
   dated amendment of N needs no code change. The markdown "Fragile and watch"
   section still renders at N = 1; WATCH rows are simply absent.
4. SOUND: zero breaches and at least `min_available_for_sound` (K) measures available.
5. INSUFFICIENT DATA: everything else (zero breaches with fewer measures
   available, or industry unknown). Each row says which measures were
   unavailable and why.

A company with N or more breaches stays FRAGILE even if other measures are
unavailable; a breach is evidence, a gap is not.

## Point-in-time filter

`src/qrl/fragility.py`, pure functions plus the loaders above.

- `fragility_as_of(ticker, date, facts, cfg, sic=None) -> CompanyResult`: uses only
  facts with `filed < date` (via the `pit_panel` rule). Result holds the six
  measures (value or unavailable reason), breached list, class, fiscal-year
  end used.
- `excluded_tickers(date, ...) -> set[str]`: the FRAGILE tickers among the
  universe members applicable on `date` (membership of the latest month-end
  strictly before `date`).

`excluded_tickers` is NOT wired into any existing run, strategy or config.
`config/factor.yaml` and the PIT universe hash bind runs 4-6 and stay
untouched. Using the filter in the sleeve needs a dated PLAN.md amendment and
a new run, a later step the owner decides.

## Outputs and CLI

`scripts/fragility.py`; pixi task `fragility = "python scripts/fragility.py"`
(on demand, never CI).

Arguments: `--as-of YYYY-MM-DD` (default: today), `--fetch-sic`, `--out-md`
(default `research/fragility.md`, committed), `--out-json` (default
`reports/fragility.json`, gitignored), `--refresh-facts`. Without
`--refresh-facts` it never fetches companyfacts; it reads the local SEC cache.
The report header shows the newest filing date seen, so staleness is visible.
No existing command refreshes the cache for the PIT universe
(`fetch-fundamentals` covers only the static 100-ticker `config/universe.yaml`;
`build-pit-universe` rewrites the hash-bound membership CSV and must not be
used for this). So `--refresh-facts` re-fetches companyfacts for the universe
members via the existing `qrl.fundamentals` fetch helpers (same host
allowlist, User-Agent and caching); run it before an on-demand run.

`research/fragility.md` is deterministic for a given as-of date and cache
(no timestamps; sorted by class then ticker). Layout, so the dashboard parser
can rely on it:

- header bullets `- key: value`: as-of date, membership month-end used,
  universe size, newest filing date seen, `config/fragility.yaml` sha256,
  universe membership sha256, thresholds (N, K);
- `## Summary`: table of class, count;
- `## Fragile and watch`: table of ticker, class, breached measures with
  values (for example "coverage 1.4x < 2.0x"), fiscal-year end used;
- `## All companies`: one row per universe member, every class including
  INSUFFICIENT DATA and NOT APPLICABLE, with the six measure values or
  `n/a (reason)`.

`reports/fragility.json` holds the same plus every raw input.

## Dashboard

New section "Balance-sheet fragility (exploration only)" in the public site.
`src/qrl/site_core.py` gains `FRAGILITY_PATH = "research/fragility.md"` and
`build_fragility(root) -> dict | None`, reusing `_sections`, `_table`,
`_bullets`; `scripts/build_site.py` adds the block to the payload next to
`core_comparison` (the site never recomputes; CI only sees the committed
file). Shows: counts per class, the FRAGILE and WATCH table with breached
measures, the as-of date, and a link to the full markdown.

## Guardrails

- Not edited: `config/criteria.yaml`, `combined.yaml`, `combined_null.yaml`,
  `paper.yaml`, `factor.yaml`, `universe_pit.yaml` and its CSV, `profile.yaml`,
  `portfolio.yaml`, `src/qrl/engine.py`, `metrics.py`, `periods.py`,
  `checks.py`, existing tests (tests may be added, none weakened or deleted).
- No price data and no returns are used anywhere: balance-sheet facts only. So
  there is no research/validation/holdout slicing issue; the holdout stays
  sealed and `slice_period` is never called.
- Every universe member appears in the output, including INSUFFICIENT DATA and
  NOT APPLICABLE; nothing is silently dropped.
- Every figure shown is traceable to a filing fact filed before the as-of date.

## Tests — `tests/test_fragility.py`, `tests/test_site_core.py` (additions)

Synthetic company facts and submissions, no network.

- Each measure's formula, with concept fallbacks, including the unavailable
  cases (missing tag, interest <= 0, missing maturity year, one fiscal year
  only for Piotroski) and the "debt reported as 0" case.
- Financial-firm exclusion by SIC range and by override list; unknown SIC ->
  INSUFFICIENT DATA.
- Classification rules and boundaries, at both N = 1 (shipped; WATCH empty) and
  N = 2: exactly N-1, N, N+1 breaches; K-1 and K available measures; values
  exactly at each threshold (not a breach).
- PIT: a filing dated after the as-of date is ignored; a filing dated ON the
  as-of date is ignored (`filed < t`); a restatement counts only once filed;
  stale (> 456 days) data is unavailable.
- Config loader: one rejection test per case listed above; the shipped
  `config/fragility.yaml` loads.
- `excluded_tickers` returns only FRAGILE and uses the right month-end.
- Markdown is deterministic (two renders identical) and lists every member.
- CLI writes both outputs from a temporary cache; `--as-of` is honoured.
- `--refresh-facts` with a stubbed HTTP helper re-fetches companyfacts for
  every universe member, uses the allowlisted host and User-Agent, and
  rewrites the cache; without the flag, no fetch is attempted; the report
  header shows the newest filing date seen.
- Site parser `build_fragility` on a sample markdown; returns None when the
  file is absent.

## Out of scope

Stage 2 discovery watchlist, wiring the filter into any run or config, any
price-based signal, drawdown-profile changes, buy/sell recommendations,
trailing-four-quarter measures, any PLAN.md amendment.

## Amendments

### 2026-10-05 — after run 1 (display and data-quality fixes)

- **Annual reports decide the fiscal year.** Fiscal year ends are taken only
  from annual reports: form 10-K, 10-K/A, 20-F, 20-F/A, 40-F or 40-F/A. Values
  for those fiscal-year periods may come from any filing, because SEC's
  company-facts data sometimes lists a fiscal-year figure only under a later
  filing that repeats it (a proxy statement, or a 10-Q's prior-year column).
  A quarterly report can no longer make a mid-year date a fiscal year end (run
  1: AMZN anchored on 2026-06-30). The 350-380 day duration test stays as it
  was.
- **Labels.** The maturity inputs are named "debt due in 1y", "debt due in 2y"
  and "debt due in 3y" in "missing ..." reasons instead of raw SEC tag names.
  Wording is made consistent: "net debt / FCF" (with spaces) in breach details;
  "maturities due with no liquidity (cash + FCF <= 0)" to match the table cell
  "no liquidity"; the Piotroski missing-input names use "(latest)", "(1y back)"
  and "assets (2y back)", the same year wording as the rate trend.
- **Display rounding.** A value and its threshold are now shown at the same
  precision. When they would look equal after rounding (for example "6.0x > 6.0x"),
  extra decimals are added, up to four. A value that rounds to "-0.0" is shown
  with more decimals, or without the minus sign if it is still zero at four.
  The table cell and the breach detail use the same value text.
- **Not changed.** `config/fragility.yaml` (same sha256), every threshold, and
  the breach and classification rule. Run 1's report is kept unchanged at
  `research/fragility_run1.md`.

### 2026-10-05 — after run 2 (owner)

- N (breach_to_fragile) 1 -> 2: two breaches make FRAGILE, exactly one makes
  WATCH. Decided by the owner after seeing run 2 (so not pre-registered like the
  original value); thresholds of the six measures are unchanged. Run 2 under
  N=1 is kept at `research/fragility_run2.md`.
- Net debt / FCF and maturities / liquidity both lean on free cash flow, so when
  both are breached they count as one breach toward N; the report still lists
  both.
- Annual-report values win: for a fiscal-year period, a value from an annual
  report (10-K, 20-F, 40-F or amendments) is used whenever one exists; other
  filings only fill gaps. Run 2 used a later quarterly report's mis-dated figure
  for FIX (operating income 209.1M tagged as full-year 2025 vs 1,314.6M in the
  10-K).
- Config sha256 changes with this amendment.

### 2026-10-05 — after run 3 (owner)

- **Rate-trend check skipped on little net debt.** At the latest fiscal year
  end, net debt = debt − cash (the same inputs as the net debt / FCF measure)
  and is compared with total assets (the "Assets" value at that year end). If
  net debt / assets <= `rate_trend_min_net_debt_to_assets` (0.05, new key in
  `config/fragility.yaml`), the rate trend is not a breach. Net cash
  (negative net debt) qualifies.
- A skipped rate trend counts as a pass and as available (it still counts
  toward `min_available_for_sound`). It is shown as "little net debt: X% of
  assets".
- **Missing inputs.** If debt, cash or assets is missing (or assets <= 0), the
  ratio cannot be computed: nothing is imputed and the existing rate-trend
  calculation runs unchanged. Companies above the 5% line are unchanged too.
- **Motivation.** In run 3, FIX (net cash) was WATCH on a +4.3 pp rate-trend
  breach. The effective rate on a tiny debt balance is noise.
- Config sha256 changes with this amendment.

### 2026-10-05 — run 5 (debt tag fallbacks, untagged no-debt rule)

- **Interest expense.** `InterestExpenseNonoperating` is appended as the last
  fallback.
- **Debt fallbacks**, tried in order only when the primary chain (`LongTermDebt`;
  else `LongTermDebtNoncurrent` + `LongTermDebtCurrent`; + `ShortTermBorrowings`)
  gives nothing:
  (a) `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities`
  + `ShortTermBorrowings`; (b) `LongTermDebtAndCapitalLeaseObligations` + the
  first available of `LongTermDebtAndCapitalLeaseObligationsCurrent`,
  `LongTermDebtCurrent`, `DebtCurrent` (+ `ShortTermBorrowings`, except with
  `DebtCurrent`, which already includes it); (c)
  `DebtLongtermAndShorttermCombinedAmount`; (d) convertible-only filers: the
  first available noncurrent of `ConvertibleDebtNoncurrent`,
  `ConvertibleLongTermNotesPayable`, `ConvertibleNotesPayable` (required) + the
  first available current of `ConvertibleDebtCurrent`,
  `ConvertibleNotesPayableCurrent` (optional) + `ShortTermBorrowings`
  (optional). (d) is a strict fallback: used only when the primary chain and
  (a)-(c) all fail.
- **Untagged no-debt rule.** A fiscal year end with no debt-family value at all
  (`DEBT_FAMILY` in `src/qrl/fragility.py`), a real balance sheet (`Assets` and
  `Liabilities` present) and no positive interest expense in any interest tag
  is treated as no debt, with the note "no debt tag; treated as no debt".
- **Audit correction.** `DEBT_FAMILY` gained `ConvertibleLongTermNotesPayable`,
  `ConvertibleDebtNoncurrent`, `ConvertibleDebtCurrent` and
  `ConvertibleNotesPayableCurrent` (with fallback (d)) after an audit found
  DASH (`ConvertibleLongTermNotesPayable` 2.724B at 2025-12-31) and PANW
  (`ConvertibleDebtNoncurrent` 1.774B at 2026-07-31) misread as no-debt: their
  only debt is convertible notes under tags that were not listed.
- Paid-cash and "costs incurred" interest tags are different concepts and are
  not used.

### 2026-10-06 — run 6 (same-concept fallbacks)

Owner-approved after run 5. Each tag is appended at LOWER priority than the
existing ones (a new tag is ignored when an old one has a value). No threshold,
K, N or SIC change.

- **Cash.** After `CashAndCashEquivalentsAtCarryingValue`: `CashAndCashEquivalentsFairValueDisclosure`,
  Short-term investments logic unchanged. `Cash` was tried and dropped before the
  run-6 report: in the audit it was a sub-line (TGT 250M), not cash and equivalents.
- **EBIT.** The pretax fallback also tries
  `IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments`
  after the existing pretax tag; still + interest expense, interest still required.
- **Operating cash flow.** After `NetCashProvidedByUsedInOperatingActivities`:
  `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`. Fiscal-year
  anchors still use the original tag only.
- **Debt, primary chain split form.** `LongTermDebtNoncurrent` + the first of
  `LongTermDebtCurrent` (+ `ShortTermBorrowings`), else `DebtCurrent` (no
  `ShortTermBorrowings`: `DebtCurrent` already includes it). A noncurrent part
  with no current part is still unavailable.
- **Revenue for gross profit (fragility only).**
  `RevenueFromContractWithCustomerIncludingAssessedTax` after the existing
  revenue concepts; the shared `fundamentals.REVENUE_CONCEPTS` is unchanged.
- **Rejected.** Proxies were considered and rejected by the owner: restricted
  cash tags, interest paid (`InterestPaid*`), `CostsAndExpenses` /
  `OperatingExpenses` as cost of revenue, oil and gas capex components, and
  zero-imputation of a missing current debt.
