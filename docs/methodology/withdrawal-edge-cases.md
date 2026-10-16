# Withdrawal edge cases: one order, one depletion threshold

Status: spec written 2026-10-15; owner-approved 2026-10-15. Implemented 2026-10-15.
Source: follow-up of [audit-remaining.md](audit-remaining.md) finding 17 (its
"Follow-up" section). That finding documented four differences between the
decision helper and the long run and left them alone because unifying them
moves numbers. This spec decides each one.

Rule for the whole spec: **no locked file changes** (`config/criteria.yaml`,
`combined.yaml`, `combined_null.yaml`, `paper.yaml`, `factor.yaml`,
`src/qrl/engine.py`, `metrics.py`, `periods.py`, `checks.py`). Only
decision-helper numbers move, and only slightly. Long-run numbers do not
move.

## (a) Withdrawal order: withdraw first, then the day's return

**Problem.** The two code paths disagree on the order.

- Decision helper (`src/qrl/decision_withdraw.py:79-84`): applies the day's
  return, then subtracts the month's withdrawal on the month's first trading
  day. `decision-helper.md:108-109` documents this (return first).
- Long run (`src/qrl/longrun.py:167`): `(value - w) * (1 + r)`, withdrawal
  first.

**Change.** In `withdrawal_path`, on the first trading day of a month,
subtract that month's withdrawal before applying the day's return. The
depletion check runs after both steps, and also straight after the
withdrawal: a value at or below the threshold after the withdrawal is
depleted that month, and no return is applied to it. `decision-helper.md`
(the "Value path" bullet, lines 108-112) is reworded to say withdrawal first.
The long run is not touched.

**Effect.** Tiny and conservative. The draw now misses one day of return, so
values are lower by about one day's return on one month's draw, compounded.
Expected size: about a basis point or less on depletion odds and ending
values. This is reasoned from the formula, not measured; the implementation
reports the actual before/after figures in the PR. Only decision-helper
numbers move. `research/decision.md` is regenerated. Long-run numbers are
unchanged.

**Tests.**

- `tests/test_decision_withdraw.py:31-35`
  (`test_withdrawal_comes_after_the_days_return`) expects 1.05 today; its
  comment says withdraw-first would give 1.045. Its expected value changes to
  1.045 and the test and comment are renamed and reworded to the new order.
  This edits an existing test, approved by the owner 2026-10-15 under
  AGENTS.md. The test is not weakened: it still pins the order, now the new
  one.
- `tests/test_decision_withdraw.py:22-27`
  (`test_withdrawal_path_closed_form_constant_return`) also changes. Every
  index there is a month start, so every day withdraws. The recursion is now
  `V_n = (V_{n-1} - w)(1 + g)` with `V_0 = 1`, so the expected value changes
  from `(1+g)^n - w((1+g)^n - 1)/g` to
  `(1+g)^n - w(1+g)((1+g)^n - 1)/g`: the withdrawal term is multiplied by
  `(1 + g)`. The inputs, the assertions and the check are the same.
- The other tests in that file use zero or hand-picked returns that do not
  depend on the order (`:38-60`, `:84-97`, `:115-120`) and are expected to
  pass unchanged. The implementation must run every other test that calls
  `withdrawal_path` (decision and report tests) and report any that moves.
- New: a withdrawal that empties the account on the first trading day marks
  depletion in that month, the value is 0 and no return is applied (for
  example a withdrawal of 1.0 with a return of +10%).

## (b) Depletion threshold: `<= 1e-9` on both sides

**Problem.** `decision_withdraw.py:83` tests `value <= 0`;
`longrun.py:168` tests `value <= DEPLETED` with `DEPLETED = 1e-9`
(`longrun.py:27`). A floating-point residue between 0 and 1e-9 counts as
depleted in the long run and not in the decision helper.

**Change.** `decision_withdraw.py` uses 1e-9 too, from one shared constant,
not a second literal. `longrun.py` already imports from `decision_withdraw`
(`from .decision_withdraw import monthly_inflation`, `longrun.py:23`), so
importing `DEPLETED` from `longrun` into `decision_withdraw` would create an
import cycle. So the constant moves: `DEPLETED = 1e-9` (same name, same
comment) is defined in `decision_withdraw.py`, and `longrun.py` imports it
beside `monthly_inflation`. `DEPLETED` is used only in `longrun.py` (`:27`,
`:151`, `:168`), so nothing else changes. The `withdrawal_path` docstring
("At or below 0") is reworded to name the threshold.

**Effect.** None in practice: a path rarely ends in the 0 to 1e-9 band.

**Tests.** New: a path that ends at a residue between 0 and 1e-9 is depleted
(value 0, depletion month set). A test that `longrun.DEPLETED` is the same
object as `decision_withdraw.DEPLETED`.

## (c) Step-up timing: kept

The decision helper steps the withdrawal each January by CPI year-on-year
(`decision_withdraw.py:42-55`). The long run steps every 12 months by the
path's own inflation (`longrun.py:150`, `:163-165`). Bootstrapped paths start
in any month and have no calendar January, so a January rule has nothing to
attach to. This is inherent to the model, not an inconsistency.

**Change.** Wording only, in the "Differences from the decision helper"
subsection of `longrun.md`: say it is inherent, not a gap to close.

## (d) Stale CPI: not a decision-versus-long-run difference

Both sides use the same shared 45-day rule: `MAX_CPI_AGE`, `usable_cpi` and
`monthly_inflation` (`decision_withdraw.py:17-39`), which the long run calls
at `longrun.py:275`. The split is inside each side:

- Cash-assumption rows that mix a cash leg with a base portfolio (the true
  cash and SHY 80/20 rows) use `strict_monthly_inflation`
  (`true_cash.py:18-29`, exact month-ends). On the decision side this is
  `decision.py:257` and `:497`. On the long-run side it is reached through
  `longrun.py:218` (`_assumption_monthly`), then `all_assumption_returns`
  (`decision.py:263`), `_row_returns` (`:245`) and `cash_leg_returns`
  (`true_cash.py:44`). Checked by reading the call chain.
- The labelled "CASH +1% real (assumption)" row in the long run does not go
  through that chain. `cash_assumption_returns` (`longrun.py:178`) is fed the
  long run's own `monthly_inflation` (`longrun.py:275, 289, 308`), so it keeps
  the 45-day tolerance.
- This was kept by owner decision 2026-10-11 (`true-cash-sleeve.md:149-152`).

**Change.** Wording only. The "Stale CPI" row in `longrun.md` is reworded to
say the above. `audit-remaining.md` gets a one-line correction note under its
section 17 table ("Corrected 2026-10-15, see withdrawal-edge-cases.md"); its
history is not rewritten.

## RSP sleeve spec: written-spec review

The written-spec review of [rsp-sleeve.md](rsp-sleeve.md) was done 2026-10-15.
Four wording fixes, in the same PR, no code or config change:

1. Status line: run 7 (one attempt) passed the research period 2005-2018 and
   then failed validation 2019-2022 on deflated Sharpe (0.495 < 0.95);
   accepted 0; not adopted. Results in `research/rsp_sleeve.md`.
2. Line-number references to `scripts/search.py` and `scripts/validate.py`
   are replaced with function names, which do not go stale.
3. The Tests section lists the tests that were built but not listed.
4. No program-wide DSR is added to `research/rsp_sleeve.md`. It can only be
   lower than 0.495, so the verdict cannot change, and adding it would need a
   re-run of validation on closed run 7.

## Untouched

- The locked files named in AGENTS.md: `config/criteria.yaml`, `combined.yaml`,
  `combined_null.yaml`, `paper.yaml`, `factor.yaml`, `src/qrl/engine.py`,
  `metrics.py`, `periods.py`, `checks.py`. Existing tests other than the two
  edited in (a).
- `config/decision.yaml` and `config/longrun.yaml`, so the `decision_sha256`
  pin at `longrun.yaml:16` stays valid.
- Long-run numbers: `run_paths` and its order and threshold do not change.

## Outputs

- `research/decision.md` is regenerated (withdrawal numbers move slightly).
- `research/longrun.md` is not expected to change. The implementation will
  confirm it is byte-identical apart from the generated-at line. If it
  changes, stop and report.

## Owner decisions (2026-10-15)

- (a) Unify on withdraw-first. The rewrite of the existing order test (and the
  closed-form expected value) is approved.
- (b) 1e-9 on both sides.
- (c) Kept, documented as inherent.
- (d) Wording corrected. The RSP spec wording fixes go in the same PR.
- One PR to `development`.
