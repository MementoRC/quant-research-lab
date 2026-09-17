# Project Plan: Quant Research Lab

This document holds the full plan: where the idea came from, the principles, the
decisions already made, what Phase 1 delivered, and detailed specs for Phases 2 and 3.
It is written so a person or an AI coding agent can pick up the work without the
original conversation.

Last updated: September 2026, end of Phase 1.

---

## 1. Origin and goal

The project is inspired by a YouTube walkthrough of using an agentic AI model (the
video used OpenAI's Codex app) to build a systematic trading research process. The
video's central argument, which this project adopts:

- The AI does not predict prices or make trading decisions.
- The AI acts as a tireless research assistant: it writes code, runs backtests, reads
  its own results, and decides what to test next, for hours unattended.
- A deterministic backtest engine with rules fixed in advance does the judging.
- Strategies decay. The valuable, lasting asset is the process that finds, validates,
  and replaces them, not any single strategy.

The goal is a personal, tool-agnostic version of that process: runnable locally with
any coding agent (Claude Code, Codex, or by hand), with results published to a static
dashboard on GitHub Pages.

This is a research and learning tool, not a source of financial advice.

---

## 2. The methodology in nine steps

A summary, in our own terms, of the pipeline described in the video, with the phase
of this project that implements each step.

| # | Step | What it means | Phase |
|---|------|---------------|-------|
| 1 | Trader profile | Goal (growth, income, conservative), trade frequency, assets, drawdown tolerance. The goal decides timeframe, data needs, and the core/sleeve mix. | 2 |
| 2 | Data | Daily bars from free sources; macro series (Fed data, yields, credit spreads, jobless claims); optionally scraped sources. Test on baskets, not single tickers. | 1 (prices), 2 (macro, baskets) |
| 3 | Rules and engine | Pass criteria written before any test. Data split into periods. Costs always on. Decide at the close, trade at the next open. | 1 |
| 4 | Search loop | Seed ideas, then an unattended loop that mutates what passed, recombines partial winners, prunes dead regions, and logs every test with notes. | 2 |
| 5 | Validation | Survivors run once on unseen data. The rotating sleeve is walk-forward tested quarterly. Neighboring parameter settings must also work. | 2 |
| 6 | Portfolio | A "core" that is always invested and rarely trades, plus a "sleeve" of short-term strategies that must trade something different from the core. | 2 |
| 7 | News reading (optional) | An LLM reads Fed statements and suggests hold, move to gold, or go to cash. | 3 |
| 8 | Risk | Max loss per trade, max exposure, leverage ceiling, max open positions. The only step the human must decide. | 3 |
| 9 | Decay and review | Daily health check, monthly live-versus-expected review, quarterly sleeve reselection, a kill rule tied to backtested drawdown. When a strategy dies, rerun step 4. | 3 |

### The example portfolio from the video

- **Core:** hold QQQ while it closes above its 200-day moving average, otherwise hold
  gold. Always invested, switches a few times a year.
- **Sleeve:** short swing trades (days to a couple of weeks) in large-cap stocks,
  reselected quarterly. Three families were shown: trend pullback, low-range close,
  and quiet pullback, all buying dips in stocks still in uptrends.
- Stocks worked better than ETFs for the sleeve because ETFs move together too much
  to diversify each other.

The specific strategies are not the point; they were fitted to one person's profile
and will decay.

---

## 3. Where we disagree with the video, and how the design responds

These are the reasons several Phase 2 components exist. Do not remove them.

**The holdout was contaminated.** The video's first walk-forward result was weak
(roughly 3–5% a year). The AI then changed settings one at a time until it beat the
benchmark. Iterating against held-out results turns them into training data, which
likely inflates the headline return.
*Response:* a three-way split (research, validation, holdout), a holdout sealed in
code, and a rule that the walk-forward selection process is tuned only on
research + validation data.

**Thousands of candidates guarantee lucky winners.** Narrowing 1,500 candidates to a
handful will produce survivors by chance alone.
*Response:* the ledger records every attempt, and Phase 2 applies a multiple-testing
adjustment (the deflated Sharpe ratio) using that count.

**Survivorship bias in stock baskets.** Backtesting on today's large caps silently
drops companies that shrank, were acquired, or went bankrupt. Free data does not fix
this.
*Response:* see the universe decision in section 7; results from a biased universe
must be labeled as such on the dashboard.

**The news layer cannot be honestly backtested.** Any current LLM was trained on text
written after those Fed statements, including market reactions. Hiding dates and
names reduces but does not remove this leak.
*Response:* the news layer is forward-tested only (paper) and never counted in
backtest performance.

**The performance figures were marketing.** The video promotes a paid community.
Treat its numbers as unverified.

---

## 4. Architecture decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Hosting | GitHub Pages, static site at `<username>.github.io/<repo>/` | Free, accessible anywhere. Pages cannot run code. |
| Where Python runs | GitHub Actions for daily builds; the local machine for research | Actions has a 6-hour job limit and Yahoo rate-limits its servers, so long searches run locally. |
| Data flow | Python writes `site/data/results.json`; the dashboard only reads it | Keeps the site static and simple. |
| Engine style | Vectorized, daily bars, target weights per day | Fast enough for large searches; easy to test for timing errors. |
| AI agent | Tool-agnostic; rules live in `AGENTS.md` | Works with Claude Code (via `CLAUDE.md` importing `AGENTS.md`), Codex, or manual work. |
| Guardrails | Enforced in code and tests, not just instructions | An agent under pressure to find winners will bend written rules. |
| Privacy | Nothing account-specific is ever published | Pages sites are public even from private repos. |

---

## 5. Phase 1 status: complete

Delivered and tested (15 tests passing):

- `src/qrl/engine.py`: decide-at-close, execute-at-next-open engine with overnight and
  session legs, turnover costs, long-only and no-leverage checks, and an error on
  missing prices for held positions.
- `src/qrl/metrics.py`: CAGR, volatility, Sharpe, max drawdown, Calmar, trade days,
  turnover, exposure.
- `src/qrl/periods.py`: research 2005–2018, validation 2019–2022, holdout 2023 onward;
  holdout slicing raises unless explicitly unsealed.
- `src/qrl/criteria.py`: loads `config/criteria.yaml` with a short hash; evaluates
  minimum trades, Sharpe, max drawdown, and beating QQQ.
- `src/qrl/checks.py`: `assert_causal`, which replaces the future with a crash and a
  boom and fails any strategy whose past weights change.
- `src/qrl/data.py`: Yahoo Finance loader with retries and CSV cache; synthetic prices
  for offline work.
- Strategies: `core_trend` (QQQ/GLD 200-day rule) and `buy_and_hold` for benchmarks.
- `scripts/build_site.py` and `site/index.html`: dashboard with the next-open signal,
  growth and drawdown charts with shaded periods, metrics by period, and pass/fail.
- Workflows: tests on pull requests; build and deploy to Pages on push and weekdays
  at 22:30 UTC.

Not yet verified: the first real-data build (Yahoo was unreachable from the
environment where Phase 1 was written). Run `python scripts/build_site.py` locally
and fix any data issues before starting Phase 2.

---

## 6. Phase 2: the research machine

Goal: an agent can run an unattended search on the research period, every test is
recorded, survivors are validated honestly, and a core + sleeve portfolio is built and
shown on the dashboard.

Build the milestones in order. Each ends with passing tests and a commit.

### 2.0 Trader profile

- Add `config/profile.yaml`: goal, trades per week, holding period, overnight holds
  allowed, max tolerable drawdown, assets, core/sleeve capital split.
- Add `scripts/profile_check.py` that reports what the profile implies (daily vs
  intraday data, free vs paid data, which strategy families fit) and flags conflicts,
  such as intraday trading with daily-only data.
- **Acceptance:** the script runs on the example profile and flags at least one
  deliberately conflicting profile in a test.

### 2.1 Universe and data expansion

- Add a universe definition in `config/universe.yaml` (for example, a list of
  large-cap tickers) with a required `survivorship_biased: true|false` field.
- Extend `data.py` to load many tickers efficiently, store in Parquet (add `pyarrow`),
  and report missing-data coverage per ticker.
- Handle delistings: when a held stock's prices end, the strategy must exit before
  the last available close; the engine's missing-price error should catch mistakes.
- Add macro series from FRED (10-year minus 2-year yield spread, Baa corporate
  minus 10-year Treasury spread (BAA10Y; FRED's ICE high-yield history is too
  short), initial jobless claims) with release-date lags so they are never used
  before they were published.
- **Acceptance:** tests confirm macro series are lagged, and the build reports
  universe coverage.

### 2.2 Strategy templates

Parameterized families, each a function registered with a parameter space
(ranges and steps) in `src/qrl/strategies/`:

- `trend_pullback`: stock above a long moving average, closes down N days or X% below
  a short average; exit after K days or on recovery.
- `low_range_close`: stock in uptrend closes near the low of its daily range; exit on
  a close above the prior high or after K days.
- `quiet_pullback`: pullback in uptrend on below-average volatility or volume.
- `core_trend` variants: different lookbacks, risk-off assets (GLD, TLT, cash).

Cross-sectional sleeves need a ranking and position cap (hold at most M names, equal
weight within the sleeve's capital share).

- **Acceptance:** every template passes `assert_causal` across sampled parameter
  sets, and each has a hand-checked unit test on a tiny price series.

### 2.3 Ledger

SQLite at `research/ledger.sqlite` (gitignored), plus an export script that writes a
summary JSON for the dashboard and a committed CSV of top candidates.

Tables:

- `runs`: run id, start/end time, git commit, criteria hash, seed lane (A/B/C), seed
  description.
- `tests`: test id, run id, family, parameters (JSON), universe, period (always
  `research` in a search), metrics (JSON), passed flag, failure reasons, timestamp.
- `notes`: run id, batch number, free-text notes written by the agent between batches.
- `validation_events`: test id, metrics, timestamp, with a unique constraint so each
  candidate can be validated only once.
- `holdout_events`: what was unsealed, when, by which commit, and why.

The writer refuses to record a test if the criteria hash differs from the run's
starting hash.

- **Acceptance:** tests confirm the unique constraint on validation and the hash
  check.

### 2.4 Search loop

A CLI, `scripts/search.py`, that the agent drives:

- `search.py seed --lane A|B|C` starts a run from a seed.
  - Lane A: the user's existing strategies, varied within their families. Best
    results.
  - Lane B: a market and timeframe; the agent proposes fitting families with reasons
    and the user picks.
  - Lane C: only a trader profile. Least targeted; use sparingly.
- `search.py batch --n 200` tests a batch of variants on the research period only and
  writes them to the ledger.
- `search.py summary` prints what passed, near-misses, and exhausted regions, for
  the agent to read before choosing the next batch.

Agent protocol per batch: read the summary and prior notes, then mutate passing
candidates, recombine conditions that partly worked, stop exploring regions that
keep failing, write a note explaining the choices, and run the next batch. Stop at a
time or test budget.

The loop runs locally, overnight, with the agent. It does not run in Actions.

- **Acceptance:** a short synthetic-data run completes unattended, and the ledger
  contains every test including failures.

### 2.5 Validation and robustness

- Rank research-period survivors, then run each once on the validation period
  (recorded in `validation_events`).
- Compute the deflated Sharpe ratio using the total number of tests in the run.
  Candidates must pass it, not just the raw Sharpe floor.
- Neighborhood check: vary each parameter one step up and down; the candidate passes
  only if most neighbors also pass. A lone spike is rejected.
- Correlation filter: drop candidates whose daily returns correlate above a limit
  (add `max_correlation` to criteria) with a stronger survivor.
- **Acceptance:** a test shows a deliberately overfitted candidate failing the
  neighborhood or deflated Sharpe check.

### 2.6 Walk-forward sleeve selection

- Starting each quarter, select the sleeve using only data before that date, trade it
  for the quarter, then step forward and repeat. Stitch the quarters together.
- Meta-settings (number of strategies, lookback window, reselection frequency,
  eviction rules) are tuned only over research + validation dates. Every meta-setting
  tried is logged.
- Guard against over-eviction: the video's first version removed strategies after
  normal losing streaks. Require evictions to exceed a drawdown or underperformance
  threshold calibrated from each strategy's own backtest.
- The holdout is unsealed exactly once, for the final chosen process, with a
  `holdout_events` record.
- **Acceptance:** a test proves selection at each quarter uses no data from on or
  after that quarter's start.

### 2.7 Portfolio and dashboard

- Combine core and sleeve by the profile's capital split. Show the contribution of
  each component (core alone, core + sleeve) against benchmarks.
- Dashboard additions: current sleeve holdings and target weights, a research funnel
  (tested, passed research, passed validation, passed robustness, selected), the
  number of attempts behind the result, and a banner when the universe is
  survivorship-biased.
- Actions computes daily signals only for the chosen portfolio, never runs searches.

---

## 7. Phase 3: risk, monitoring, and execution

### 3.1 Risk sizing and leverage

- Add to criteria or profile: max loss per trade, max gross exposure, leverage
  ceiling, max open positions, borrowing cost.
- Engine support for leverage (weights summing above 1) with borrowing costs charged
  on the excess, plus per-position and portfolio caps.

### 3.2 Decay monitoring

- Daily: data arrived, signals computed, no errors.
- Monthly: live or paper returns versus the backtest's expected distribution.
- Quarterly: sleeve reselection through the walk-forward process.
- Kill rule: a strategy is removed if its live drawdown exceeds a set multiple of its
  worst backtested drawdown.
- When a strategy is removed, rerun the Phase 2 search on top of the existing ledger
  rather than starting over.

### 3.3 News layer (optional)

- An LLM reads each Fed statement and returns hold, gold, or cash, with low
  temperature and multiple runs checked for agreement.
- Forward-tested on paper only; never merged into backtest performance (see
  section 3).

### 3.4 Execution

- Semi-automated first: the daily build shows the orders to place; the user places
  them at any broker.
- Automated later through Alpaca's paper-trading API (or Interactive Brokers for
  futures). API keys in GitHub Secrets or a local untracked `.env`, never in the site.
- Mandatory: position caps, max open positions, and a kill switch that flattens
  everything and stops trading.
- Paper trade for at least one to two months before any real money.
- Execution state (positions, balances, orders) stays private and is never written to
  the public dashboard.

---

## 8. Open decisions for the owner

These need answers before or during Phase 2:

1. **Trader profile:** goal, trade frequency, overnight holds, and maximum drawdown
   you can tolerate.
2. **Core/sleeve split:** for example 80/20 for growth, lower sleeve for conservative.
3. **Stock universe:** accept a survivorship-biased free universe (labeled as such),
   pay for point-in-time constituent data, or keep the sleeve to ETFs.
4. **Seed lane:** do you have existing strategies (lane A), a market and timeframe
   (lane B), or only a profile (lane C)?
5. **Ledger storage:** keep SQLite local only (default), or commit exports to track
   research history on GitHub.
6. **News layer:** include it as a paper-only experiment, or skip it.

---

## 9. Starting Phase 2 with a coding agent

Suggested opening prompt:

> Read PLAN.md and AGENTS.md. Phase 1 is complete. First, run `pytest -q` and
> `python scripts/build_site.py` on real data and fix any data problems without
> changing the engine or criteria. Then start Phase 2, milestone 2.0. Work one
> milestone at a time; after each, run the tests, commit, and stop to summarize what
> changed and any decisions you need from me. Ask me the open decisions in section 8
> when they become relevant.
