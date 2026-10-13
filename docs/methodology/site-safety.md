# Site safety: survivorship label and holdout cut-off on the public dashboard

Status: spec written 2026-10-12, awaiting owner review.
Source: the read-only audit of 2026-10-12 (workflow wf_78e2e1c3-596),
findings 1 and 2, the only two rated medium. No other audit finding is in
scope here.

## Problem

1. **Missing survivorship label.** `scripts/build_site.py:358` sets the
   payload's `survivorship_biased` to `None`, and only
   `site/data/universe_coverage.json` (written by `scripts/data_check.py`)
   can turn it on. The Pages workflow never runs `data_check`, so the live
   site hides the notice (`site/index.html:197`). Its research funnel
   (1495 tested, 603 passed, 27 validated) comes from
   `us_large_cap_stocks` and `us_large_cap_pit`, and both configs say
   `survivorship_biased: true`. `config/universe.yaml:7-8` says any
   dashboard built from that universe must show the label.
2. **Holdout in "full" figures.** For every entry, `build_site.py:290`
   computes `metrics.full` over the whole common window (2023 onward
   included), and `:335-341` publishes weekly equity and drawdown over the
   same window. `allow_holdout` only removes the named `holdout` period row
   (`:291`). Today every shown entry is allowed the holdout (fixed
   baselines, benchmarks, a baseline core and an empty sleeve), so nothing
   leaks. The first search-origin core or sleeve member would publish its
   2023+ performance with no `holdout_events` row.

## Not a test

Site build only. No strategy, metric, period, criteria or ledger rule
changes. No locked file is edited (`engine.py`, `metrics.py`, `periods.py`,
`checks.py`, the locked configs). Existing tests are kept; new tests are
added.

## Design

### A. Survivorship label from the research record, failing closed

The label must not depend on a file CI never builds.

- `scripts/export_ledger.py` adds `universes` to `research.json`: one entry
  per distinct `tests.universe` value in the ledger, with its test count.
- `build_site.py` gains `_research_survivorship(research, ROOT)`. For each
  universe name it finds the config that defines it (`config/universe.yaml`
  via `qrl.universe.load_universe`, `config/universe_pit.yaml` via
  `qrl.pit_universe.load_pit_universe`) and reads its
  `survivorship_biased`. It returns
  `{"biased": bool, "universes": [{"name", "tests", "survivorship_biased"}]}`.
  **Fail closed:** a universe name with no matching config, or a config that
  fails to load, counts as biased. If any tested universe is biased,
  `biased` is true.
- The payload gets this as `research_funnel["survivorship"]`. The front end
  shows the existing notice text above the funnel whenever
  `research_funnel.survivorship.biased` is true, naming the universes.
- Search-origin portfolio entries (a core with `origin != baseline`, or the
  combined line once the sleeve has members) get
  `"survivorship_biased": true` on their entry in `strategies`, rendered as
  a badge beside the entry name. These entries came from the search, and
  every search universe so far is biased. The flag is set to false only
  when the portfolio provenance names a run whose universes are all
  configured as unbiased; otherwise it is true.
- The top-level `survivorship_biased` and `universe` keys keep their current
  meaning: dashboard-universe coverage from `universe_coverage.json`, which
  is `None` and absent without the file. That keeps
  `tests/test_build_site_dashboard.py:164-170` as written. The site notice
  shows when **either** the top-level flag or the funnel flag is true.

### B. Holdout cut-off for entries without holdout clearance

- New helper `_visible_end(r, criteria, common_end)`: `common_end` when
  `r["allow_holdout"]` is true, otherwise
  `min(common_end, period_bounds(criteria, "validation")[1])`.
- `metrics.full` for each entry is computed over
  `common_start.._visible_end(r)`. For an entry without clearance,
  `metrics.full` also carries `"through": "<validation end>"`, and the
  table shows "Full history (to 2022-12-31)" for that row.
- Series keep one shared `dates` list (the common window). For an entry
  without clearance, equity and drawdown values after its visible end are
  `null`. Chart.js draws `null` as a gap by default (`spanGaps` is not set
  in `site/index.html`), so the line simply stops at the validation end.
- Holdout clearance comes from a cross-check, not from config alone.
  `provenance.holdout_unsealed: true` in `config/portfolio.yaml` grants it
  only if `research/ledger.sqlite` has at least one `holdout_events` row.
  Otherwise the build fails with an error that names the mismatch, instead
  of publishing.
- The holdout slice at `build_site.py:293` stays as the single
  `slice_period(..., unseal_holdout=True)` call, reached only when
  `r["allow_holdout"]` lets `"holdout"` into `names` (this keeps
  `tests/test_build_site_dashboard.py:235-241` true). A comment there will
  say why fixed baselines and benchmarks may show holdout without
  `qrl.holdout.unseal`: they were never searched or tuned
  (`build_site.py:230-235`).

## Tests (new)

In `tests/test_build_site_dashboard.py` or a new
`tests/test_site_safety.py`, all with synthetic data:

1. A search-origin core (`origin: search`, no unseal): no `metrics.full`
   value uses a date after the validation end. Its `full` equals metrics
   over `common_start..2022-12-31`, and every equity/drawdown value after
   that date is `null`.
2. The same entry with `holdout_unsealed: true` and a ledger with a
   `holdout_events` row: full window, no nulls.
3. `holdout_unsealed: true` with an empty `holdout_events` table: the build
   raises.
4. Baseline strategies and benchmarks: output unchanged (full window).
5. A `research.json` whose universes are `us_large_cap_stocks` gives
   `research_funnel.survivorship.biased == true`.
6. An unknown universe name gives `biased == true` (fail closed).
7. A universe config with `survivorship_biased: false` alone gives
   `biased == false`.
8. A search-origin entry carries `survivorship_biased: true`.
9. The front end has a notice condition covering the funnel flag (string
   check on `site/index.html`, as existing tests do).

## Effect on the live site

- The survivorship notice appears with the next Pages build and names
  `us_large_cap_stocks` and `us_large_cap_pit`.
- Today's entries are all baselines, so their charts and figures do not
  change.

## Out of scope

Every other audit finding (report wording, deflated-Sharpe counting,
`paper.yaml` pin, docs drift). Those get their own specs.
