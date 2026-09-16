# Rules for AI coding agents working in this repo

These rules keep automated strategy research honest. Claude Code, Codex, or any
other agent must follow them. Humans should too.

## Never edit during a research run
- `config/criteria.yaml` — pass rules are fixed before testing.
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
