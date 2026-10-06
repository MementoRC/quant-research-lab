# Core shortlist reveal — design

Date: 2026-10-04. Status: approved in conversation (owner, 2026-10-04), pending written-spec review.

## Purpose

The core-compare spec (2026-10-03, "Stress: windows" and "Out of scope")
deferred the validation-window stress cells to "a later, separate step once the
owner has picked". On 2026-10-04, after reading `research/core_compare.md`
(research period only), the owner shortlisted E, F and G.

The shortlist unlocks exactly ONE look at the `covid_2020` and `inflation_2022`
stress windows, for those three cores only. Both windows lie entirely inside
the validation period (2019-01-01..2022-12-31); neither reaches the holdout,
which starts 2023-01-01.

It is still EXPLORATION ONLY: it selects nothing, writes no config and does not
change the core. Switching the core still needs a dated, pre-registered amendment and a
new run.

Consequence, stated plainly: after the reveal, E, F and G are "validation-seen"
for 2020 and 2022. Any later run that evaluates a switched core on the
validation period must record that its validation evidence for these cores was
not blind. A, B, C and D stay unseen in these windows, and this tool can never
show them.

It changes nothing in `config/portfolio.yaml`, `config/combined.yaml`,
`config/combined_null.yaml`, `config/paper.yaml`, `config/criteria.yaml`,
`config/profile.yaml`, `config/factor.yaml`, `config/stress.yaml` or
`config/core_candidates.yaml`, and does not touch `src/qrl/engine.py`,
`metrics.py`, `periods.py`, `checks.py` or any existing test (existing tests are
not weakened or deleted).

## Shortlist — `config/core_shortlist.yaml`

Pre-registered and committed before any reveal run. Header comment: fixed
before the reveal; changes only by dated amendment.

| key | value |
|---|---|
| `version` | 1 |
| `date` | 2026-10-04 |
| `decided_by` | owner |
| `candidates_sha256` | `1a84847ed4ae59e81627c420b88f7736357f0bdc0bcb654a945c5d2ad88107e3` (sha256 of `config/core_candidates.yaml`, computed 2026-10-04) |
| `ids` | [E, F, G] |
| `windows` | [covid_2020, inflation_2022] |

`load_core_shortlist(path, candidates, candidates_sha256, stress_cfg, criteria)
-> (Shortlist, sha256 of the shortlist file)` raises `ValueError` on:

- a wrong `version`;
- empty or duplicate `ids`;
- an id not in the candidates file;
- a `candidates_sha256` that differs from the current candidates file's hash;
- empty or duplicate `windows`;
- a window name not in `stress.yaml`;
- a window that does not overlap the validation period (it ends before the
  validation start: nothing to reveal);
- a window ending on/after the holdout start (the stress loader already
  refuses this; asserted again here).

## Computation — `src/qrl/core_reveal.py`

Pure functions; no I/O except `load_core_shortlist` reading its file.

- Candidates are filtered to the shortlist ids. Windows are the named ones
  only, taken directly from the stress config (bypassing
  `core_compare.split_windows`, which by design drops them).
- Every frame is truncated by index at `max(window.end)` of the revealed
  windows (2022-10-31) before any use. Nothing after the last revealed window
  enters any computation.
- The stress config passed to `run_stress` has the hypotheticals removed and
  only the revealed windows. Cells are kept only for revealed windows
  (defensive filter plus an assertion).
- Portfolios come from `core_compare.stress_portfolios`. A switching
  candidate (F) is stressed as `F` (replay cells only) plus `F[risk_on]` and
  `F[risk_off]` (frozen cells only). Static candidates (E, G) are single
  portfolios with replay and frozen cells.
- No research metrics, no hypotheticals, no other candidates.
- Breach: cell loss > profile `max_drawdown` (0.35), as in core-compare. The
  report gives, per candidate, the breach count over revealed cells.

### Look-ahead guard on frozen cells

`run_stress` frozen mode takes the LAST row of the weights built from the frame
passed (`_latest_weights`) and buys it at the window's first close. Here the
last row is 2022-10-31, after both window starts. That is legitimate only if
the frozen portfolio's weights are constant over the frame: then the last row
equals what could have been held at each window start. For a state-dependent
weight (a switching rule) the last row would reflect the branch live at
2022-10-31, information from after the window start (and, for covid_2020, after
the window end).

So, for each portfolio that gets frozen cells, the module asserts that its
weight rows over the truncated frame are all identical (tolerance 1e-12), and
raises otherwise. Which rows are compared matters: `build` goes through
`combine_portfolio`, which zero-fills the NaN rows a strategy emits while a
held ticker is unpriced or warming up (before GLD/TLT/IEF/SHY existed), so
those rows are all-zero or partial, not NaN. The guard therefore compares only
from the first date on which every ticker the portfolio can hold is priced and
the weights sum to more than ~0, onward. Static mixes and the static branch
portfolios `F[risk_on]`, `F[risk_off]` pass; a switching rule given frozen mode
raises.

The guard (with selection, truncation and `stress_portfolios`) lives in
`preflight(...)`, which `run_core_reveal` reuses.

## Output

`run_core_reveal(...) -> dict`; `render_markdown(report) -> str`, deterministic
apart from the event id. The markdown opens with the banner:

> VALIDATION-SEEN: these cells use validation-period data (2020, 2022). One
> look, recorded in the ledger (event id N).

and lists: shortlist sha256, candidates sha256, `stress.yaml` sha256, the
drawdown cap, the trial count of the original comparison (7) and the shortlist
size (3). Then the replay/frozen table, with the "proxied to cash" column as in
core-compare (blank when nothing is proxied), and per-candidate breach counts.
`reports/core_reveal.json` (gitignored) holds the same data plus generated_at,
params and every cell.

## One-look lock (ledger event)

New table in `src/qrl/ledger.py`, created with `CREATE TABLE IF NOT EXISTS` so
existing ledgers gain it on open:

`reveal_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, created_at,
shortlist_sha256, candidates_sha256, stress_sha256, ids, windows, status TEXT
('started'|'done'), forced INTEGER, reason TEXT)` (naming mirrors
`holdout_events.event_id`).

Methods: `record_reveal_event(...) -> event_id`, `finish_reveal_event(event_id)`,
`list_reveal_events(kind)`.

CLI order: data load and price check -> `preflight` (selection, truncation,
look-ahead guard; a failure returns 1 and records nothing) -> check lock ->
record a `started` event (committed immediately) BEFORE computing -> compute
-> write outputs -> mark `done`. Anything that can fail without revealing a
number runs before the lock.

- Any existing event of kind `core_reveal` (started or done) refuses the run,
  unless `--force` is given with a non-empty `--reason`; the forced run is
  itself recorded as a new event with `forced = 1` (mirrors
  `qrl.holdout.unseal`).
- A crash after `started` therefore spends the look. Re-running needs
  `--force` plus a reason. This is deliberate: we cannot prove the numbers were
  not seen.
- The CLI also requires `--confirm` (as the holdout unseal does), so it cannot
  be run by accident.

## CLI — `scripts/core_reveal.py`

Arguments: `--confirm`, `--force`, `--reason`, `--out-json` (default
`reports/core_reveal.json`, gitignored), `--out-md` (default
`research/core_reveal.md`, committed by the owner after reading). pixi task
`core-reveal`.

Data: `qrl.data.load_ohlcv(tickers, refresh=True)`. Every shortlisted ticker
(signal ticker and the `SPY` equity proxy included) must be priced on the last
row at or before the last revealed window's end, else the CLI fails loudly
(before the lock is taken, so a data failure does not spend the look).

The PR adds code, `config/core_shortlist.yaml` and tests only. The reveal
itself is run by the owner after the PR is merged, never by CI or tests (tests
use synthetic data and a temporary ledger).

## Tests — `tests/test_core_reveal.py`

- Shortlist loader: one rejection test per case listed above.
- Only shortlisted ids and named windows are evaluated; no hypotheticals.
- No frame row after the last window end reaches `run_stress` (spy on
  `run_stress`).
- Frozen look-ahead guard: raises for a switching rule portfolio in frozen
  mode; passes for static mixes.
- A switching candidate is split into replay and branch portfolios.
- Markdown has the VALIDATION-SEEN banner and the hashes.
- Ledger: the first run records `started` then `done`; a second run is
  refused; `--force` without a reason is refused; `--force` with a reason
  records a forced event; a crash mid-run leaves `started` and refuses the
  next run.
- CLI requires `--confirm`; CLI fails loudly on an unpriced ticker.
- The shipped `config/core_shortlist.yaml` loads against the shipped
  candidates and `stress.yaml`.

## Out of scope

Revealing for A-D, any other validation window, research metrics on
validation, choosing a winner, switching the core, any rule amendment.
