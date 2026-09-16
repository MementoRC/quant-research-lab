# Quant Research Lab

A disciplined backtesting pipeline for systematic trading research, with a dashboard
that publishes itself to GitHub Pages after every market close.

The goal is not a magic strategy. It is a repeatable process: fixed rules, honest
tests, and a record of everything tried, so strategies can be found, checked, and
replaced as they stop working.

> This is a research and learning tool, not financial advice. Backtests do not predict
> future returns.

## How it works

```
 GitHub Actions (weekdays after the close)            GitHub Pages
 ┌─────────────────────────────────────────┐          ┌─────────────────────────┐
 │ 1. pytest: timing, costs, look-ahead    │          │ site/index.html         │
 │ 2. download prices (Yahoo Finance)      │  deploy  │ reads data/results.json │
 │ 3. run strategies + benchmarks          │ ───────▶ │ <you>.github.io/<repo>/ │
 │ 4. write site/data/results.json         │          └─────────────────────────┘
 └─────────────────────────────────────────┘
```

GitHub Pages only serves static files, so all Python runs in Actions. The site is plain
HTML and JavaScript and works on any device.

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q

python scripts/build_site.py              # real data, cached in data/cache/
python scripts/build_site.py --synthetic  # offline demo with random prices
python -m http.server -d site 8000        # open http://localhost:8000
```

Opening `site/index.html` directly from disk will not load the data; use the local server.

## Publish to GitHub Pages

1. Create an empty repository on GitHub (the repo name becomes the URL path).
2. Push this project:
   ```bash
   git remote add origin https://github.com/<username>/<repo>.git
   git push -u origin main
   ```
3. In the repo, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Go to **Actions → Build and deploy dashboard → Run workflow**.
5. When it finishes, the dashboard is live at `https://<username>.github.io/<repo>/`.

After that it rebuilds on every push to `main` and every weekday at 22:30 UTC.

## Project layout

```
config/criteria.yaml     Pass rules, periods, costs, benchmarks (locked; see AGENTS.md)
config/strategies.yaml   Which strategies to run, with parameters
src/qrl/engine.py        Backtest engine: decide at close, trade next open, costs always on
src/qrl/metrics.py       CAGR, Sharpe, drawdown, turnover, exposure
src/qrl/periods.py       Research / validation / holdout split, holdout sealed by default
src/qrl/criteria.py      Loads criteria (with a hash) and evaluates pass/fail
src/qrl/checks.py        assert_causal(): catches strategies that peek at future data
src/qrl/strategies/      Strategy functions and the registry
scripts/build_site.py    Runs everything and writes the dashboard data
site/index.html          The dashboard
tests/                   Engine, strategy, and criteria tests
```

## The rules this project enforces

**Timing.** A strategy's weights for day t may use only data through day t's close.
The engine executes them at day t+1's open. A test perturbs targets and verifies no
earlier return changes.

**Costs.** Every unit of turnover is charged `bps_per_unit_turnover` from the criteria file.

**Criteria first.** `config/criteria.yaml` is written before testing. The dashboard shows
its hash, so edits are visible.

**Sealed holdout.** Code refuses to slice the holdout period unless explicitly unsealed.
Fixed baselines (like the benchmarks and the core trend rule) may show it, since
nothing was tuned on it. Searched strategies must not.

**No look-ahead.** Every registered strategy is tested with `assert_causal`, which
replaces the future with a crash and a boom and checks that past weights stay identical.

## Adding a strategy

1. Write a function in `src/qrl/strategies/` that takes `close` plus parameters and
   returns target weights (NaN during warm-up, long-only, rows sum to at most 1).
2. Register it in `src/qrl/strategies/__init__.py`.
3. Add example parameters in `tests/test_strategies.py` and run `pytest`.
4. Add it to `config/strategies.yaml`.

## Known limitations

- Weights are rebalanced to target daily and cash earns 0%.
- Yahoo Finance sometimes rate-limits GitHub's servers. If a scheduled build fails,
  rerun it; the last good dashboard stays online.
- GitHub disables scheduled workflows after 60 days without repository activity.
- A GitHub Pages site is public even if the repository is private. Never publish
  account balances, positions, or API keys to it. Broker keys belong in GitHub Secrets.
- Individual-stock baskets need point-in-time index membership to avoid survivorship
  bias. Free data does not provide this.

## Roadmap

- **Phase 1 (this release):** data, engine, criteria, sealing, core trend baseline, dashboard.
- **Phase 2:** strategy templates, a SQLite ledger of every test, an agent-driven search
  loop on the research period, walk-forward sleeve selection, multiple-testing adjustment.
- **Phase 3:** risk sizing and leverage limits, decay monitoring and kill rules, paper
  trading through Alpaca with position caps and a kill switch.
