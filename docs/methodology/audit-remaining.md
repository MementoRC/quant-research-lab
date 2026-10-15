# Audit remainder: deflated-Sharpe counting, paper.yaml pin, docs drift

Status: spec written 2026-10-14; owner decisions taken 2026-10-14 (listed at
the end). Awaiting owner review of this written spec.
Source: the read-only audit of 2026-10-12 (workflow wf_78e2e1c3-596),
findings 8, 9, 15, 16, 17 and 18, all rated low. Findings 3-7 and 14 were
handled by `report-wording.md`. This closes the audit.

Rule for the whole spec: **no reported number changes, and no locked file
changes** (`config/criteria.yaml`, `combined.yaml`, `combined_null.yaml`,
`paper.yaml`, `factor.yaml`, `src/qrl/engine.py`, `metrics.py`, `periods.py`,
`checks.py`). The one exception is new *added* output: the program-wide
deflated Sharpe in finding 8.

## 8. Deflated Sharpe: add a program-wide figure next to the per-run one

**Problem.** `validate_survivors` computes the deflated Sharpe ratio (DSR)
from `ledger.trial_sharpes(run_id, key=...)` (`src/qrl/validation.py:491`,
`:496`). The count is per run and running: neighbour re-tests recorded during
validation (`:440-451`) join the list before the DSR is taken. This is the
documented rule (PLAN.md:290, 311-313; `validation.py:10, 18`) and stays the
pass statistic. But the program as a whole has tried far more variants than
any one run, and a reader of the paper candidate (test 1046, run 3, per-run
DSR 0.714 at N=62, `research/run3_validation_rebuilt.txt:21`) is not told
that. The audit's rough program-wide figure was about 0.51 (runs 1-3, same
universe, all rows, normal returns assumed); nothing passed 0.95 under any
count.

**Change.** Report a second, informational figure: the program-wide DSR.

- *Pool:* every test in every run whose pass rule uses the same Sharpe key
  as the candidate's run (`"sharpe"` for standalone runs,
  `"improvement_sharpe"` for combined, combined-null and factor runs;
  `ledger.py:834, 850`). Mixing the two keys would compare unlike numbers.
- *Cut-off:* only tests with `created_at <=` the moment the candidate's DSR
  is taken -- the same rule `scripts/rebuild_validation.py:295-296` already
  uses, so the figure is reproducible after the fact.
- *Inputs:* the same observed Sharpe, `n_obs`, skew and kurtosis as the
  per-run DSR. Only the trial list differs (so both N and the trial-Sharpe
  spread change).
- *Formula:* the existing `deflated_sharpe_ratio` (`validation.py:186`),
  unchanged.

New `Ledger.program_trial_sharpes(key, *, up_to)` returns that list. In
`validate_survivors` each survivor entry gains `program_deflated_sharpe` and
`program_trial_count` beside `deflated_sharpe`; the pass/fail test still reads
only `deflated_sharpe`. `scripts/validate.py` prints both;
`scripts/rebuild_validation.py` adds the program-wide figure to its per-row
line.

*As built (2026-10-15):* `research/run3_validation_rebuilt.txt` (the only
rebuilt file) is **not** regenerated. The rebuild reads cached prices only,
but the cache has drifted since 2026-10-01: every candidate's backtest
cross-check now reports a mismatch and is tagged `[approx]`, and several
per-run DSRs move in the third decimal (e.g. 0.684 -> 0.683). Regenerating
would change recorded numbers, which this spec rules out. The paper
candidate's figure is recorded here instead: test 1046 has a program-wide
DSR of about **0.508 at N = 1076** standalone trials (rows up to its
validation event), against the per-run 0.714 at N = 62. It is `[approx]`
(stored Sharpe, skew 0, kurtosis 3) and agrees with the audit's 0.51.
PLAN.md is not edited.

**Tests.** The program-wide list includes other runs with the same key,
excludes the other key, and excludes rows created after the cut-off; pass/fail
is unchanged when the program-wide DSR is lower; rebuild output carries both
figures.

## 9. Pin `config/paper.yaml`'s hash

**Problem.** `load_paper_config` (`src/qrl/paper.py:34-37`) computes a
sha256 that `scripts/paper_track.py:67-87` only prints and writes to the
private report. Nothing compares it to a recorded value, so "fixed for the
paper track" is convention, unlike every other locked config (criteria,
combined and combined-null hashes live on the ledger's `runs` row and
`record_test` refuses on mismatch, `ledger.py:454-463`; factor hashes are
checked by `check_factor_run`, `factor_run.py:148-170`). The file has one
commit and is intact.

**Change.** The pin lives in the ledger, which is git-tracked
(`.gitignore:24-29`) and is where the other hashes live.

- New table `config_pins(name TEXT PRIMARY KEY, sha256 TEXT NOT NULL,
  pinned_at TEXT NOT NULL, source TEXT NOT NULL)`, created by the ledger's
  existing schema setup. Full 64-hex digest.
- `Ledger.pin_config(name, sha256, source)` inserts once and refuses to
  overwrite; `Ledger.config_pin(name)` reads it.
- `qrl.paper.check_paper_pin(ledger, sha256)` raises if a pin exists and
  differs, naming both hashes and pointing to PLAN.md (a changed paper rule
  needs a dated amendment and a new track, not an edit).
- Back-fill: a one-off `scripts/paper_track.py --pin` computes the hash of
  `paper.yaml` at its pre-registration commit
  (`git show <commit>:config/paper.yaml`), checks it equals the working file,
  and records it with that commit as `source`. It refuses if they differ or a
  pin exists. Normal runs refuse when no pin exists, so the track cannot run
  unpinned.
- `scripts/stress.py:112` also loads `paper.yaml`; it reports, it does not
  run the track, so it records the hash as today and is not gated.

**Tests.** Pin round-trip; second pin refused; mismatch refused with both
hashes in the message; `paper_track.main` refuses unpinned and mismatched,
runs when matched; `--pin` refuses when the working file differs from the
commit.

## 15. One source for the cash-assumption rows

**Problem.** Three overlapping paths read the cash-assumption rows: the
single-row accessor `assumption_returns` (`src/qrl/decision.py:222-238`,
first row only), the multi-row `cash_rows` (`:241-244`), and the report's
`cash_assumption` / `cash_assumptions` keys with `_multi` branching
(`src/qrl/decision_report.py:36-55, 134-158`). The single-row text
hard-codes "CASH +1% real" (`:100, 145`) while the percentage comes from the
config. `cash_rows` returns `()` whenever `cash_assumption` is None, even if
`cash_assumptions` is not empty.

**Change.** Code only; `config/decision.yaml` is not edited, so the longrun
pin (`config/longrun.yaml:16`) is untouched.

- `DecisionConfig.cash_assumptions` is the source; `cash_assumption` becomes
  a read-only property (the first row, or None).
- `cash_rows(cfg)` returns `cfg.cash_assumptions`. `assumption_returns`
  calls the multi-row path and takes the first row, instead of a parallel
  implementation.
- The report keeps both JSON keys (the site and older readers use them) but
  builds `cash_assumption` from `cash_assumptions`. The hard-coded "+1%"
  becomes the row's `real_yield`, formatted.
- `_cash_nominal_loss` (`decision.py:497`) keeps `rows[0].real_yield` but
  asserts every row has the same yield (true today, and each row is already
  checked against longrun by `check_cash_assumption`), so a future unequal
  row fails loudly instead of being silently ignored.

**Tests.** Existing tests pass unchanged. New: the report text follows a
non-1% yield; `cash_rows` with a non-empty tuple; unequal yields refused.
Regenerated `research/decision.md` is byte-identical apart from its
generated-at line.

## 16. Stale status lines in the specs

| File | Now says | Becomes |
|---|---|---|
| `rsp-sleeve.md:3-4` | Not yet run | Run 7 (one attempt), research period 2005-2018 passed; results in `research/rsp_sleeve.md` (cdcb7d9). Written-spec review still outstanding. |
| `README.md:33` (true-cash-all-cores entry) | spec awaiting owner review | owner-approved 2026-10-12; implemented and run 2026-10-12 |
| `core-comparison.md:3`, `core-reveal.md:3`, `fragility-screen.md:3`, `stress-scenarios.md:3` | pending written-spec review | Implemented; results in `research/<file>.md`. No review date is claimed (the repo does not record one). |
| `longrun.md:18` | same 12 portfolios as the decision helper | the same portfolios as the decision helper (12 when written; 34 after the defensive-sleeve and true-cash amendments, plus the CASH +1% real row: 35 rows per rate) |
| `longrun.md:3` | report fd87fd8f | the commit of the current `research/longrun.md` (1d66ca3) |
| `report-wording.md:3-4` (not in the audit) | Awaiting implementation | Implemented in PR #60 (1d66ca3) |
| this file | Awaiting owner review | updated when merged |

## 17. Duplicated rates: check them, document the deliberate differences

**Problem.** The real cash yield (0.01) is in seven `config/decision.yaml`
rows and `config/longrun.yaml:24`; equality is checked at run time
(`check_cash_assumption`, `longrun.py:90-98`). The withdrawal rates
`[0.02, 0.033, 0.04, 0.05]` are in both `decision.yaml:98` and
`longrun.yaml:23` with **no** equality check. `cash_real_yield` has no
bounds check in `load_longrun_config` (`longrun.py:85`), unlike the decision
rows' |y| <= 0.05 (`decision_config.py:45, 231-233`). The decision and
longrun paths also differ on edge cases (below).

**Change.** No config edits (they would change the pinned longrun hash) and
no behaviour changes (they would move reported depletion odds).

- `check_withdrawal_rates(cfg, lcfg)` next to `check_cash_assumption`,
  called at the same two places (`run_longrun` and `longrun.main`, before any
  data is read): refuses if the two lists differ.
- `load_longrun_config` applies the same |y| <= 0.05 bound to
  `cash_real_yield`, reusing the decision-side constant.
- The deliberate differences are written down in `longrun.md` (new
  subsection "Differences from the decision helper"), not unified:

  | | Decision helper | Long run |
  |---|---|---|
  | Withdrawal timing | first trading day of each month | each simulated month |
  | Order | month's return, then withdrawal (`decision_withdraw.py:80-82`) | withdrawal, then return (`longrun.py:167`) |
  | Step-up | each January by CPI year-on-year | every 12 months by the path's own inflation |
  | Depleted at | value <= 0 (`decision_withdraw.py:83`) | value <= 1e-9 (`longrun.py:27, 168`) |
  | Stale CPI | up to 45 days old allowed (`decision_withdraw.py:17-26`); cash leg needs exact month-ends (`true_cash.py:18-29`, kept deliberately, `true-cash-sleeve.md:140-152`) | same 45-day rule (`longrun.py:275`) |

  Unifying any row would change reported numbers, so it is left to a
  separate, later change (see "Follow-up" at the end).

**Tests.** Unequal rate lists refused before data is read; an out-of-bounds
`cash_real_yield` refused; the shipped configs pass both.

## 18. A test that cannot fail

**Problem.** `tests/test_factor_run.py:177-189`,
`test_load_factor_run_rejects_bad_configs`, has the case
`({"research_start": "not-a-date"}, "")`: `match=""` accepts any
`ValueError`, including the other validation errors at
`src/qrl/factor_run.py:83-89, 92`. Line 90 calls
`pd.Timestamp(cfg["research_start"])` with no message of its own.
Separately, `tests/test_fragility.py:573-575` uses `match=r"."`, which matches
any non-empty message.

**Change.** `factor_run.py:90` catches the pandas error and raises
`ValueError(f"{path}: research_start {value!r} is not a date")`; the test case
matches `"research_start .* is not a date"`. This makes the test stricter,
not weaker (AGENTS.md allows that; the case stays). `test_fragility.py:574`
gets one expected message per parametrized case.

## Owner decisions (2026-10-14)

- 8: report both; the per-run DSR stays the pass statistic.
- 9: pin in persistent state (the ledger), not in code.
- 15-18: all four in scope, including tightening the existing test.
- One PR for all of it.

## Owner decisions on the open questions (2026-10-15)

- RSP sleeve status: implemented and run; the written-spec review stays
  outstanding.
- Program-wide DSR pool (8): same Sharpe key across all runs, rows up to the
  moment the DSR is taken. Not restricted to the candidate's universe.
- Edge-case differences (17): documented now, not unified here.

## Follow-up (not in this change)

- Decide whether to unify the decision-helper and long-run edge cases listed
  in 17 (withdrawal order, depletion threshold, step-up timing, stale-CPI
  rule). Any unification moves reported depletion odds, so it needs its own
  spec and regenerated reports.
