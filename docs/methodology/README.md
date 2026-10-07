# Methodology

These documents fix each study's rules before any results are seen. Each one
records the question, the pre-registered inputs and the pass or reporting
rules; later changes are made only as dated amendments recorded in the
document itself.

- [core-comparison.md](core-comparison.md) — exploration-only comparison of
  seven pre-registered, more resilient cores against the current core, on
  past shocks and research-period return.
- [core-reveal.md](core-reveal.md) — the single, one-time look at the
  validation-period stress windows for the owner's shortlisted cores.
- [stress-scenarios.md](stress-scenarios.md) — diagnostic stress scenarios
  showing how much the portfolio would lose in a shock and whether that
  breaches the max-drawdown cap.
- [fragility-screen.md](fragility-screen.md) — balance-sheet screen that flags
  listed US companies that look fragile if borrowing stays expensive.
- [decision-helper.md](decision-helper.md) — decision aid comparing a fixed
  set of portfolios under historical crashes, judgement-based shocks and
  inflation-indexed withdrawals.

## Former paths

Config files whose sha256 is recorded in reports (`config/fragility.yaml`,
`config/stress.yaml`, `config/core_candidates.yaml`,
`config/core_shortlist.yaml`) still cite the old paths in their header
comments. They are left unchanged so their hashes stay valid.

| Old path | New file |
|---|---|
| `docs/superpowers/specs/2026-10-03-core-compare-design.md` | `core-comparison.md` |
| `docs/superpowers/specs/2026-10-03-stress-scenarios-design.md` | `stress-scenarios.md` |
| `docs/superpowers/specs/2026-10-04-core-reveal-design.md` | `core-reveal.md` |
| `docs/superpowers/specs/2026-10-05-fragility-screen-design.md` | `fragility-screen.md` |
