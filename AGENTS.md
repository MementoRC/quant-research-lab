# Rules for AI coding agents working in this repo

These rules keep automated strategy research honest. Claude Code, Codex, or any
other agent must follow them. Humans should too.

## Never edit during a research run
- `config/criteria.yaml` — pass rules are fixed before testing.
- `config/combined.yaml` — the combined pass rule (PLAN.md 2.5, amendment
  2026-10-01). Its hash also covers `profile.yaml`'s `capital_split` and
  `portfolio.yaml`'s core, so do not change those during a combined run
  either; `search batch` and `validate` refuse if the hash changed.
- `config/combined_null.yaml` — the beat-the-null pass rule (PLAN.md 2.5,
  amendment 2026-10-02, run 5). Same hash binding as `combined.yaml`
  (`capital_split` and the core included); `search batch` and `validate`
  refuse if the hash changed.
- `config/paper.yaml` — fixed for the duration of the paper track
  (pre-registered 2026-10-02).
- `config/factor.yaml` — the factor run's research start, universe, families and
  null baseline (PLAN.md Phase 4, milestone 4). Its sha256, and that of the
  universe membership CSV (`config/universe_pit.yaml`), bind factor runs the
  same way `combined_null.yaml` does: `search batch` and `validate` refuse if
  either changed.
- `src/qrl/engine.py`, `src/qrl/metrics.py`, `src/qrl/periods.py`, `src/qrl/checks.py`.
- Existing tests in `tests/`. You may add tests; do not weaken or delete them.

If one of these seems wrong, stop and explain the problem to the human instead.

## Strategy rules
- New strategies go in `src/qrl/strategies/` and must be added to `REGISTRY`
  and to `EXAMPLE_PARAMS` in `tests/test_strategies.py`.
- Weights on day t may only use data up to the close of day t. `pytest` must pass.
- Search and tune on the research period only. Never call `slice_period(...,
  "holdout", unseal_holdout=True)` for a searched candidate.

## Logging
- Record every variant tested, including failures. The number of attempts is
  needed to judge whether a winner is real or luck.

## Unattended search protocol (milestone 2.4)
Driving `scripts/search.py` for an overnight run, repeat per batch:

1. `pixi run search summary --run ID` — read what passed, near-misses, and
   which parameter regions keep failing.
2. Read the notes printed by that summary (prior batches' reasoning).
3. `pixi run search batch --run ID --n N [--max-seconds S]` — propose, test,
   and record the next batch. `propose_batch` already mutates passing
   candidates, recombines partial winners, and prunes dead regions; a batch
   only needs `--families` if you want to widen or narrow the run's set.
4. `pixi run search note --run ID --batch N --text "..."` — write down what
   you tried and why before the next batch, so the next agent (or you,
   tomorrow) does not repeat it.

Rules enforced by `qrl.search` and the ledger, not just this checklist:
- The search only ever slices `qrl.periods`' `"research"` period. It never
  calls `slice_period(..., "holdout", unseal_holdout=True)`, and never
  touches `"validation"` either -- both are milestone 2.5's job.
- Every candidate tested is recorded, passes and failures alike; a candidate
  that raises an exception is recorded as a failed test with the error as
  its failure reason, not silently skipped.
- `search batch` refuses to run if `config/criteria.yaml`'s hash has changed
  since the run was seeded (the ledger's own guardrail).
