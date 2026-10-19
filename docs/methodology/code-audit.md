# Code audit, October 2026

Status: draft, awaiting owner review (2026-10-19).

A read-only audit of `src/qrl`, `scripts/`, `tests/` and the QA config,
aimed at code that is easy to debug and fix (for a person or an LLM) and at
tests that would catch a real mistake. Four parallel reviews (QA tools, dead
code and size, Python constructs, tests), then a second pass that re-read the
code behind every high-severity claim. Three claims did not survive that pass
and are listed at the end.

Nothing here changes a pass rule, a locked config or a past result. Locked
files (`engine.py`, `metrics.py`, `periods.py`, `checks.py`, the locked YAMLs,
existing tests) are only reported; fixes for them are new tests alongside.

## Baseline (development at f680e02)

| gate | result |
|---|---|
| ruff lint | pass, 0 |
| ruff format | pass, 176 files |
| mypy `src/qrl` | pass, 56 files |
| bandit `src/qrl` | pass, 0 issues |
| pytest (`ci`) | 1432 passed, 0 failed, 0 skipped, 415 s |
| coverage (`qrl` + `scripts`) | 87% (8470 statements, 1096 missed) |

The gates pass because they are loose, not because there is nothing to find:
see section 5.

## 1. Research integrity

1.1 **Walk-forward hides candidate errors.** `src/qrl/walkforward.py:311` is
`except Exception: return None`, and `walk_forward` (`:379`) drops the None
with no count and no ledger record. A code bug looks the same as "no track",
as long as one other candidate survives. AGENTS.md requires a candidate that
raises to be recorded as a failed test with the error as its reason.
Fix: return a failure record (family, params, error text), count it in the
walk-forward output and record it the way `qrl.search.evaluate_candidate`
does. Test: a candidate whose build raises appears as a failure with its
message; an all-fail run still raises.

1.2 **Delisting look-ahead in `qrl.tradability`.** The module forces an exit
before a delisting by using each ticker's last valid bar (`:53`) and
`shift(-1)` (`:46`). The module docstring says this is deliberate. It is used
by search, combined, walk-forward and paper, so it is in reported results. It
likely flatters them (delisting losses are skipped), and no methodology doc
explains it. Owner decision D1 below.

1.3 **No look-ahead test for portfolios and sleeves.** Every `REGISTRY`
strategy, the factor families, null controls, core mix and the overlay have a
truncation test. `combine_portfolio` (`src/qrl/portfolio.py`), the defensive
and RSP sleeves, and the stress, shock and paper transforms do not.
Fix: new tests that truncate future prices and check that earlier weights
(or returns) are unchanged.

## 2. Test gaps (new tests only)

2.1 `qrl.metrics` has no direct test. Add hand-computed CAGR, Sharpe, max
drawdown and volatility, plus constant, all-zero, NaN, zero-volatility and
non-positive-equity series.

2.2 Engine and periods: add empty and single-row frames, an all-NaN weight
row, weights summing to exactly 1 and 1 + eps, a weights/prices index
mismatch, first and last day of each period, and `evaluate` with a metric
exactly at its threshold.

2.3 Coverage holes. Scripts at 0%: `walkforward`, `unseal_holdout`,
`data_check`, `pit_universe`, `factor_smoke`, `fetch_fundamentals`. Modules
below 85%: `pit_universe` 52%, `macro` 64%, `data` 72%, `factor_data` 74%,
`fundamentals` 83%; scripts `longrun` 69%, `stress` 72%, `paper_track` 76%.
Priority: `unseal_holdout` and `walkforward` (they guard sealed data), then
`data` (corrupt or empty cache, duplicate dates).

2.4 About ten `pytest.raises` without `match=` (for example
`tests/test_core_reveal.py:323,362`, `tests/test_paper.py:138,140`,
`tests/test_combined.py:314,316`). Add sibling tests that check the message.

2.5 Registry-wide invariants: one parametrized test over `REGISTRY` and
`SLEEVE_REGISTRY` that weights are non-negative, rows sum to at most
1 + 1e-9 and no NaN reaches the engine; and a same-seed-twice test for
`propose_batch`, null controls and `sample_params`.

2.6 Structure: a shared synthetic-price fixture in `tests/conftest.py`
(today about seven files build their own), a registered `slow` marker on the
two sealing tests (55 s and 31 s) and similar, and new tests for large areas
in new sibling files rather than `test_fragility.py` (1350 lines).

## 3. Duplication and dead code

3.1 `_get_run` and `_check_data_source` are identical in `scripts/validate.py`,
`scripts/search.py` and `scripts/walkforward.py`, and `_get_run` is inlined in
`scripts/unseal_holdout.py`. Move to one shared place.

3.2 The `--synthetic` / `--universe` argparse block is repeated 13 times.
One helper.

3.3 `{**REGISTRY, **SLEEVE_REGISTRY}` is built by hand in `paper.py`,
`combined.py`, `walkforward.py`, `search.py` and `profile.py`, and `_spec_for`
is identical in two of them. Add `strategies.ALL_SPECS` and `spec_for`.

3.4 Config load plus sha256 is hand-written about 15 times with three
truncations (12, 16, 64 characters). One helper that returns the full digest,
truncating at the call site. Every existing digest must stay byte-identical,
because the ledger and the locked-config refusals compare them; a test pins a
few known values before and after.

3.5 `ROOT = Path(__file__).resolve().parents[1]` in 24 scripts: one
`qrl.paths.ROOT`.

3.6 Dead: `fundamentals.pit_panel_fallback` (`:420`) has no caller; its logic
is copied inline at `pit_universe.py:605`. Call it from there or delete it.

3.7 Smaller: `_pct` defined three times; read-only SQLite connects repeated
in five scripts instead of `connect_ro`; near-duplicate `stress_portfolios`
in `decision.py` and `core_compare.py`.

3.8 Stale status lines: `docs/methodology/README.md` lists whatif-shock as
awaiting owner review (merged in PR #65), and `audit-remaining.md` still says
awaiting owner review.

## 4. Debuggability

4.1 Long functions: `scripts/build_site.py:333` `main` (about 245 lines,
complexity 23), `src/qrl/validation.py:344` `validate_survivors` (about 213),
`walk_forward`, `run_daily_health`, `propose_batch`, `evaluate_candidate`
(about 100 to 120 each). Split into named steps, no behaviour change, tests
first.

4.2 Large modules: `Ledger` (about 580 lines: schema, runs, validation,
holdout, reveal and overlay events, pins, queries) and `pit_universe.py`
(about 1000 lines: screening, loading, features, ranking, I/O, report).
Split by job.

4.3 `assert` for runtime checks (removed under `python -O`):
`scripts/factor_smoke.py:46`, `scripts/rebuild_validation.py:399`,
`src/qrl/core_reveal.py:186`. Raise with the offending value.

4.4 `scripts/build_site.py:78` catches every exception while reading strategy
names. Catch `OSError` and `yaml.YAMLError` and name the path.

4.5 `src/qrl/stress.py:144,155` forward-fill with no limit; the PIT code uses
`PRICE_FFILL_LIMIT`. Use one shared limit or document why stress differs.

4.6 Config loaders return different shapes (tuple of dict and hash,
dataclass, bare dict). New loaders return a frozen dataclass carrying its
digest; existing ones move when they are next touched.

## 5. QA strictness

| tool | today | proposal |
|---|---|---|
| mypy | `src/qrl` only, not strict | add `check_untyped_defs`, then `disallow_untyped_defs` per module; add `scripts/` |
| coverage | no threshold, `scripts/` not measured | measure `scripts/`; `fail_under` at the current figure rounded down, raised as gaps close |
| bandit | `src/qrl` only | add `scripts/` |
| ruff | no complexity or argument rules | add `C90` (max 15) and `ARG` for `src/`, with per-file ignores for tests |

Turning everything on at once flags 629 items (339 of them magic numbers,
`PLR2004`), so this goes last and in steps. `PLR2004` is not proposed.

## Plan: four PRs

1. Integrity: 1.1 and 1.3, and whatever D1 decides for 1.2.
2. Tests: section 2 and the coverage gate.
3. Duplication and dead code: section 3.
4. Debuggability and strictness: sections 4 and 5.

Each PR keeps all existing tests passing and unchanged, runs the full suite,
and records no research results.

## Owner decisions

D1, delisting look-ahead (1.2):

- (a) Document it in a methodology note and add a reporting-only sensitivity
  table without the forced exit for already-recorded results. Recommended.
- (b) Leave it as is, documented only.
- (c) Remove it. This changes every result that used it, mid-program, and is
  not recommended.

D2, whether PR 4's mypy and ruff tightening is wanted at all, or only the
splits.

## Claims checked and dropped

- `qrl.health` exception handlers: they do record the failure in the report.
- A test expecting `ZeroDivisionError` (`tests/test_overlay_cli.py:133`): a
  deliberate injected crash, not a pinned bug.
- `metrics.py` CAGR dividing by zero years: not reachable, since fewer than
  two rows returns early.
