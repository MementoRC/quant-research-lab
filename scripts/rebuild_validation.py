"""Read-only reconstruction of what `scripts/validate.py` printed for a run.

`validate.py` prints a funnel and a per-candidate stage/reason, but persists
only the neighbour evaluations (ordinary `tests` rows) and one
`validation_events` row per candidate that reached the validation period. This
script replays `qrl.validation.validate_survivors` against the stored rows to
recover the rest. It NEVER writes: the ledger is opened with a SQLite
`mode=ro` URI (no Ledger instance, so no migrations), and it never calls
`validate_survivors`, `record_test`, `record_validation`, or anything with
period="holdout".

Windowing assumptions (derived from validate_survivors; documented because
none of this is stored):

- An invocation is a cluster of the run's validation events with one
  `validation_config_hash` and consecutive `created_at` gaps <= --invocation-gap
  seconds. An invocation in which no candidate reached validation leaves no
  event and is invisible (only its neighbour rows remain).
- Survivors are chosen at invocation start from the run's rows that already
  existed (ledger.top_candidates: passed rows, ranked by rank_by, stable on
  test_id, top N). The true start is unobservable, so the replay tries start
  points (a count of leading rows) from latest to earliest and keeps the first
  fully consistent one: every candidate's neighbour rows found, and the set of
  candidates reaching validation equals the stored events.
- Per candidate, in rank order, one-step neighbours are recomputed with the
  row's own universe; each neighbour's row is the next row (by test_id, after
  the previous candidate's last consumed row) with that candidate_key and
  created_at <= the candidate's validation event (or, for a candidate rejected
  before validation, the next later candidate's event). Missing rows give
  stage "unknown". A candidate with no neighbours passes vacuously.
- Candidates validated in earlier invocations are "already_validated".
- DSR trial set = every run row with created_at <= the candidate's validation
  event (ledger.trial_sharpes at that moment; 0.0 when `sharpe` is absent).
- Concurrent writers to the same run during an invocation would break the
  contiguity assumption; it is reported as "unknown"/integrity diffs, never
  guessed.
- Standalone runs only: a run seeded with the combined pass rule (milestone
  2.5, amendment 2026-10-01) is refused with exit 2.

Usage:
    python scripts/rebuild_validation.py --run 3 --synthetic
    python scripts/rebuild_validation.py --run 3 --no-backtest --timeline
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from validate import (  # noqa: E402
    DEFAULT_UNIVERSE_TICKERS,
    SEARCHABLE_SPACES,
    _print_funnel,
)

from qrl.criteria import load_criteria  # noqa: E402
from qrl.ledger import DEFAULT_LEDGER_PATH, candidate_key, data_source_fingerprint  # noqa: E402
from qrl.search import SearchData, compute_benchmark_metrics, evaluate_candidate  # noqa: E402
from qrl.universe import load_universe  # noqa: E402
from qrl.validation import (  # noqa: E402
    _one_step_neighbours,
    correlation_filter,
    deflated_sharpe_ratio,
    load_validation_config,
)

CROSS_CHECK_KEYS = ("sharpe", "total_return", "max_drawdown", "days")
FUNNEL_KEYS = (
    "survivors",
    "passed_neighbourhood",
    "validated",
    "passed_deflated_sharpe",
    "passed_correlation",
    "accepted",
)


@dataclass
class Row:
    test_id: int
    family: str
    params: dict
    universe: str
    passed: bool
    reasons: str | None
    key: str
    created_at: datetime
    metrics: dict


@dataclass
class Event:
    test_id: int
    metrics: dict
    config_hash: str | None
    created_at: datetime


@dataclass
class Planned:
    row: Row
    status: str  # already_validated | nbr_passed | nbr_failed | unknown
    fraction: float = 1.0
    consumed: list[int] = field(default_factory=list)
    event: Event | None = None


def connect_ro(path: str | Path) -> sqlite3.Connection:
    """Open `path` strictly read-only; fails if it does not exist."""
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_rows(conn: sqlite3.Connection, run_id: int) -> list[Row]:
    cur = conn.execute(
        "SELECT test_id, family, params_json, universe, passed, failure_reasons, "
        "candidate_key, created_at, metrics_json FROM tests WHERE run_id = ? ORDER BY test_id",
        (run_id,),
    )
    return [
        Row(
            r["test_id"],
            r["family"],
            json.loads(r["params_json"]),
            r["universe"],
            bool(r["passed"]),
            r["failure_reasons"],
            r["candidate_key"],
            datetime.fromisoformat(r["created_at"]),
            json.loads(r["metrics_json"]),
        )
        for r in cur.fetchall()
    ]


def load_events(conn: sqlite3.Connection, run_id: int) -> list[Event]:
    cur = conn.execute(
        "SELECT v.test_id, v.metrics_json, v.validation_config_hash, v.created_at "
        "FROM validation_events v JOIN tests t USING (test_id) WHERE t.run_id = ?",
        (run_id,),
    )
    events = [
        Event(
            r["test_id"],
            json.loads(r["metrics_json"]),
            r["validation_config_hash"],
            datetime.fromisoformat(r["created_at"]),
        )
        for r in cur.fetchall()
    ]
    events.sort(key=lambda e: (e.created_at, e.test_id))
    return events


def cluster_events(events: list[Event], gap_seconds: float) -> list[list[Event]]:
    clusters: list[list[Event]] = []
    for ev in events:
        if clusters:
            last = clusters[-1][-1]
            same_hash = last.config_hash == ev.config_hash
            if same_hash and (ev.created_at - last.created_at).total_seconds() <= gap_seconds:
                clusters[-1].append(ev)
                continue
        clusters.append([ev])
    return clusters


def pick_survivors(rows: list[Row], n_before: int, top_n: int, rank_by: str) -> list[Row]:
    pool = [r for r in rows[:n_before] if r.passed and rank_by in r.metrics]
    pool.sort(key=lambda r: r.metrics[rank_by], reverse=True)
    return pool[:top_n]


def _match_neighbours(
    rows: list[Row],
    key_pos: dict[str, list[int]],
    start: int,
    row: Row,
    neighbours: list[dict],
    upper: datetime | None,
) -> tuple[list[Row], bool, int]:
    """Find each neighbour's row, in order, at or after list index `start`.
    Returns (found rows, all_found, next start index)."""
    found: list[Row] = []
    complete = True
    pos = start
    for params in neighbours:
        positions = key_pos.get(candidate_key(row.family, params, row.universe), [])
        i = bisect.bisect_left(positions, pos)
        if i >= len(positions) or (upper is not None and rows[positions[i]].created_at > upper):
            complete = False
            continue
        found.append(rows[positions[i]])
        pos = positions[i] + 1
    return found, complete, pos


def plan_invocation(
    rows: list[Row],
    key_pos: dict[str, list[int]],
    n_before: int,
    events: dict[int, Event],
    prior_validated: set[int],
    cfg: dict,
    spaces: dict[str, dict[str, list]],
) -> list[Planned]:
    survivors = pick_survivors(rows, n_before, cfg["top_n_to_validate"], cfg["rank_by"])
    times = [events[s.test_id].created_at if s.test_id in events else None for s in survivors]
    plans: list[Planned] = []
    pos = n_before
    for i, s in enumerate(survivors):
        if s.test_id in prior_validated:
            plans.append(Planned(s, "already_validated"))
            continue
        upper = next((t for t in times[i:] if t is not None), None)
        nbrs = _one_step_neighbours(s.params, spaces.get(s.family, {}))
        found, complete, pos = _match_neighbours(rows, key_pos, pos, s, nbrs, upper)
        plan = Planned(
            s, "unknown", consumed=[r.test_id for r in found], event=events.get(s.test_id)
        )
        if not nbrs:
            plan.status = "nbr_passed"
        elif complete:
            plan.fraction = sum(1 for r in found if r.passed) / len(found)
            ok = plan.fraction >= cfg["neighborhood"]["fraction_required"]
            plan.status = "nbr_passed" if ok else "nbr_failed"
        plans.append(plan)
    return plans


def _reached(plans: list[Planned]) -> set[int]:
    return {p.row.test_id for p in plans if p.status == "nbr_passed"}


def choose_start(
    rows: list[Row],
    key_pos: dict[str, list[int]],
    cluster: list[Event],
    prior_validated: set[int],
    cfg: dict,
    spaces: dict[str, dict[str, list]],
) -> tuple[int, list[Planned]]:
    """Latest start point whose replay is fully consistent (else the best)."""
    events = {e.test_id: e for e in cluster}
    index = {r.test_id: i for i, r in enumerate(rows)}
    lowest = max(index[t] for t in events) + 1
    first_time = cluster[0].created_at
    highest = sum(1 for r in rows if r.created_at <= first_time)
    best: tuple[tuple[int, int], int, list[Planned]] | None = None
    for n_before in range(max(highest, lowest), lowest - 1, -1):
        plans = plan_invocation(rows, key_pos, n_before, events, prior_validated, cfg, spaces)
        unknown = sum(1 for p in plans if p.status == "unknown")
        diff = len(_reached(plans) ^ set(events))
        if best is None or (unknown, diff) < best[0]:
            best = ((unknown, diff), n_before, plans)
        if (unknown, diff) == (0, 0):
            break
    if best is None:
        return lowest, plan_invocation(rows, key_pos, lowest, events, prior_validated, cfg, spaces)
    return best[1], best[2]


def cross_check(recomputed: dict, stored: dict) -> list[str]:
    """Differing metric names between a recomputed and a stored validation."""
    bad = []
    for key in CROSS_CHECK_KEYS:
        a, b = recomputed.get(key), stored.get(key)
        if a is None and b is None:
            continue
        if a is None or b is None or not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12):
            bad.append(key)
    return bad


@dataclass
class Replay:
    funnel: dict
    candidates: list[dict]
    corr_unknown: int = 0


def _trial_sharpes(rows: list[Row], at: datetime) -> list[float]:
    return [float(r.metrics.get("sharpe", 0.0)) for r in rows if r.created_at <= at]


def finalize(
    plans: list[Planned],
    rows: list[Row],
    cfg: dict,
    *,
    backtest: bool,
    data: SearchData | None,
    criteria: dict,
    bench: dict | None,
) -> Replay:
    funnel: dict = dict.fromkeys(FUNNEL_KEYS, 0)
    funnel["survivors"] = len(plans)
    out = Replay(funnel, [])
    accepted_returns: list = []
    corr_reliable = backtest
    fraction_required = cfg["neighborhood"]["fraction_required"]
    for pl in plans:
        c = {"test_id": pl.row.test_id, "family": pl.row.family, "tag": "exact"}
        out.candidates.append(c)
        if pl.status == "already_validated":
            c["stage"] = "already_validated"
            c["reason"] = "test already has a validation event; skipped, never re-validated"
        elif pl.status == "unknown":
            c["stage"], c["tag"] = "unknown", "unknown"
            c["reason"] = "neighbour rows not found in the ledger at that time"
        elif pl.status == "nbr_failed":
            c["stage"] = "neighbourhood"
            c["reason"] = (
                f"only {pl.fraction:.0%} of neighbours passed research criteria "
                f"(need {fraction_required:.0%})"
            )
        elif pl.event is None:
            funnel["passed_neighbourhood"] += 1
            c["stage"], c["tag"] = "unknown", "unknown"
            c["reason"] = "replay says it reached validation but no validation event is stored"
        else:
            funnel["passed_neighbourhood"] += 1
            funnel["validated"] += 1
            corr_reliable = _finish_validated(
                pl,
                rows,
                cfg,
                c,
                funnel,
                accepted_returns,
                corr_reliable,
                out,
                backtest,
                data,
                criteria,
                bench,
            )
    if out.corr_unknown or not backtest:
        for key in ("passed_correlation", "accepted"):
            funnel[key] = f"{funnel[key]} (+{out.corr_unknown} unknown)"
    return out


def _finish_validated(
    pl: Planned,
    rows: list[Row],
    cfg: dict,
    c: dict,
    funnel: dict,
    accepted_returns: list,
    corr_reliable: bool,
    out: Replay,
    backtest: bool,
    data: SearchData | None,
    criteria: dict,
    bench: dict | None,
) -> bool:
    """DSR + correlation for a candidate that reached validation. Returns the
    updated `corr_reliable` flag."""
    event = pl.event
    assert event is not None
    returns = None
    sharpe = event.metrics.get("sharpe")
    n_obs = int(event.metrics.get("days", 0))
    skew, kurt = 0.0, 3.0
    c["tag"] = "approx"
    if backtest and data is not None:
        outcome = evaluate_candidate(
            pl.row.family, pl.row.params, data, criteria, bench, period="validation"
        )
        bad = cross_check(outcome["metrics"], event.metrics)
        c["check"] = "MATCH" if not bad else f"MISMATCH ({', '.join(bad)})"
        if not bad:
            returns = outcome["returns"].dropna()
            sharpe = outcome["metrics"].get("sharpe")
            n_obs = len(returns)
            skew = float(returns.skew()) if n_obs >= 3 else 0.0
            kurt = float(returns.kurtosis()) + 3.0 if n_obs >= 3 else 3.0
            c["tag"] = "exact"
        else:
            corr_reliable = False
    if sharpe is None or n_obs < 3:
        c["stage"] = "deflated_sharpe"
        c["reason"] = "validation period had too few observations to compute a Sharpe"
        return corr_reliable
    trials = _trial_sharpes(rows, event.created_at)
    dsr = deflated_sharpe_ratio(sharpe, trials, n_obs, skew, kurt)
    c.update(dsr=dsr, threshold=cfg["min_deflated_sharpe"], trials=len(trials), n_obs=n_obs)
    if dsr < cfg["min_deflated_sharpe"]:
        c["stage"] = "deflated_sharpe"
        c["reason"] = f"deflated Sharpe {dsr:.3f} < required {cfg['min_deflated_sharpe']}"
        return corr_reliable
    funnel["passed_deflated_sharpe"] += 1
    if returns is None or not corr_reliable:
        out.corr_unknown += 1
        c["stage"], c["tag"] = "unknown", "unknown"
        c["reason"] = "passed deflated Sharpe; correlation filter needs exact returns"
        return corr_reliable
    corr = correlation_filter(returns, accepted_returns, cfg["max_correlation"])
    c["correlation"] = corr["correlation"]
    if not corr["passed"]:
        c["stage"] = "correlation"
        c["reason"] = (
            f"correlates {corr['correlation']:.2f} with an accepted survivor "
            f"(limit {cfg['max_correlation']})"
        )
        return corr_reliable
    funnel["passed_correlation"] += 1
    funnel["accepted"] += 1
    c["stage"], c["reason"] = "accepted", None
    accepted_returns.append(returns)
    return corr_reliable


def rebuild(
    rows: list[Row],
    events: list[Event],
    cfg: dict,
    spaces: dict[str, dict[str, list]],
    *,
    backtest: bool,
    data: SearchData | None,
    criteria: dict,
    bench: dict | None,
    invocation_gap: float,
) -> list[dict]:
    """One result per invocation: funnel, candidates, integrity, neighbour ids."""
    key_pos: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        key_pos.setdefault(r.key, []).append(i)
    prior: set[int] = set()
    results = []
    for cluster in cluster_events(events, invocation_gap):
        n_before, plans = choose_start(rows, key_pos, cluster, prior, cfg, spaces)
        replay = finalize(
            plans, rows, cfg, backtest=backtest, data=data, criteria=criteria, bench=bench
        )
        stored = {e.test_id for e in cluster}
        reached = _reached(plans)
        results.append(
            {
                "config_hash": cluster[0].config_hash,
                "first": cluster[0].created_at,
                "last": cluster[-1].created_at,
                "rows_before": n_before,
                "funnel": replay.funnel,
                "candidates": replay.candidates,
                "missing_from_replay": sorted(stored - reached),
                "extra_in_replay": sorted(reached - stored),
                "neighbour_ids": {i for p in plans for i in p.consumed},
            }
        )
        prior |= stored
    return results


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------


def _print_candidates(candidates: list[dict]) -> None:
    print("Per-candidate outcome:")
    if not candidates:
        print("  (no survivors to validate)")
        return
    for c in candidates:
        detail = "" if c["stage"] == "accepted" else f" -- {c['reason']}"
        print(f"  test {c['test_id']:<6} {c['family']:<16} {c['stage']}{detail} [{c['tag']}]")
        if "dsr" in c:
            line = (
                f"      DSR {c['dsr']:.3f} (threshold {c['threshold']}, trials {c['trials']}, "
                f"n_obs {c['n_obs']}) [{c['tag']}]"
            )
            if c.get("correlation") is not None:
                line += f"  max corr {c['correlation']:.2f}"
            print(line)
        if "check" in c:
            print(f"      backtest cross-check: {c['check']}")


def _print_invocation(i: int, res: dict, current_hash: str) -> None:
    print(
        f"\nInvocation {i}: {res['first'].isoformat()} .. {res['last'].isoformat()}, "
        f"validation config {res['config_hash']}, survivors drawn from the first "
        f"{res['rows_before']} run rows"
    )
    if res["config_hash"] != current_hash:
        print(f"  WARNING: stored config hash {res['config_hash']} != current {current_hash}")
    _print_funnel(res["funnel"])
    _print_candidates(res["candidates"])
    if res["missing_from_replay"] or res["extra_in_replay"]:
        print(
            f"  Integrity: DIFF stored-not-replayed {res['missing_from_replay']}, "
            f"replayed-not-stored {res['extra_in_replay']}"
        )
    else:
        print("  Integrity: OK (replayed validation set == stored validation_events)")


def cluster_rows(rows: list[Row], gap_seconds: float) -> list[list[Row]]:
    clusters: list[list[Row]] = []
    for r in rows:
        if clusters and (r.created_at - clusters[-1][-1].created_at).total_seconds() <= gap_seconds:
            clusters[-1].append(r)
        else:
            clusters.append([r])
    return clusters


def _print_timeline(
    rows: list[Row], events: list[Event], notes: list[sqlite3.Row], nbr_ids: set[int], gap: float
) -> None:
    print(f"\nTimeline (test rows clustered by created_at gaps > {gap:g}s):")
    prev_end = None
    for n, cl in enumerate(cluster_rows(rows, gap), 1):
        nbr = sum(1 for r in cl if r.test_id in nbr_ids)
        passed = sum(1 for r in cl if r.passed)
        n_ev = sum(1 for e in events if cl[0].created_at <= e.created_at <= cl[-1].created_at)
        gap_txt = (
            ""
            if prev_end is None
            else f" (gap {(cl[0].created_at - prev_end).total_seconds():.0f}s)"
        )
        print(
            f"  cluster {n}{gap_txt}: {len(cl)} rows, tests {cl[0].test_id}-{cl[-1].test_id}, "
            f"{cl[0].created_at.isoformat()} .. {cl[-1].created_at.isoformat()}, passed {passed}, "
            f"validation-neighbour rows {nbr}, search-batch rows {len(cl) - nbr}, "
            f"validation events inside {n_ev}"
        )
        reasons = Counter(r.reasons for r in cl if not r.passed and r.reasons)
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"      {reason:<30} {count}")
        prev_end = cl[-1].created_at
    print("Notes (batch -> created_at):")
    for note in notes:
        print(f"  [batch {note['batch_no']}] {note['created_at']}  {note['text'][:80]}")
    if not notes:
        print("  (none)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _verify(
    conn: sqlite3.Connection, args: argparse.Namespace, criteria_hash: str, universe: dict
) -> tuple[dict | None, int | None]:
    run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (args.run,)).fetchone()
    if run is None:
        print(f"Unknown run {args.run}", file=sys.stderr)
        return None, 2
    if run["criteria_hash"] != criteria_hash:
        print(
            f"WARNING: criteria hash mismatch: run {run['criteria_hash']} vs file {criteria_hash}",
            file=sys.stderr,
        )
    expected = data_source_fingerprint(args.synthetic, universe["name"], list(universe["tickers"]))
    recorded = json.loads(run["data_source"]) if run["data_source"] else None
    if recorded is None:
        print("WARNING: run has no recorded data source; cannot verify flags.", file=sys.stderr)
    elif recorded != expected:
        print(
            f"WARNING: DATA SOURCE MISMATCH: run {recorded!r}, flags {expected!r}", file=sys.stderr
        )
        if not args.no_backtest:
            print("Refusing to recompute backtests on different data.", file=sys.stderr)
            return None, 2
    return dict(run), None


def cmd_rebuild(args: argparse.Namespace) -> int:
    criteria, criteria_hash = load_criteria(args.criteria)
    cfg, config_hash = load_validation_config(args.validation_config)
    if args.top is not None:
        cfg = {**cfg, "top_n_to_validate": args.top}
    universe = load_universe(args.universe)

    conn = connect_ro(args.ledger)
    try:
        run, code = _verify(conn, args, criteria_hash, universe)
        if code is not None:
            return code
        if run is not None and run.get("pass_rule") in ("combined", "combined_null"):
            print(
                f"Run {args.run} uses the combined pass rule; rebuild_validation is "
                "not supported for combined runs yet.",
                file=sys.stderr,
            )
            return 2
        rows = load_rows(conn, args.run)
        events = load_events(conn, args.run)
        notes = conn.execute(
            "SELECT batch_no, text, created_at FROM notes WHERE run_id = ? ORDER BY note_id",
            (args.run,),
        ).fetchall()
    finally:
        conn.close()

    data = bench = None
    backtest = not args.no_backtest
    if backtest and events:
        needed = set(universe["tickers"]) | set(DEFAULT_UNIVERSE_TICKERS)
        needed |= set(criteria["benchmarks"])
        data = SearchData.load(sorted(needed), synthetic=args.synthetic)
        bench = compute_benchmark_metrics(data, criteria)

    mode = "backtest" if backtest else "no-backtest (DSR [approx], correlation [unknown])"
    print(f"Run {args.run}: {len(rows)} test rows, {len(events)} validation events; mode {mode}")
    results = rebuild(
        rows,
        events,
        cfg,
        SEARCHABLE_SPACES,
        backtest=backtest,
        data=data,
        criteria=criteria,
        bench=bench,
        invocation_gap=args.invocation_gap,
    )
    for i, res in enumerate(results, 1):
        _print_invocation(i, res, config_hash)
    if not results:
        print("(no validation events stored for this run)")
    missing = sorted({t for r in results for t in r["missing_from_replay"]})
    extra = sorted({t for r in results for t in r["extra_in_replay"]})
    verdict = (
        "OK"
        if not (missing or extra)
        else f"DIFF stored-not-replayed {missing}, replayed-not-stored {extra}"
    )
    print(f"\nOverall integrity: {verdict}")
    if args.timeline:
        nbr_ids = {i for r in results for i in r["neighbour_ids"]}
        _print_timeline(rows, events, notes, nbr_ids, args.timeline_gap)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--top", type=int, default=None, help="override top_n_to_validate")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--no-backtest", action="store_true", help="skip recomputing validation runs")
    ap.add_argument("--timeline", action="store_true", help="print run row clusters and notes")
    ap.add_argument("--invocation-gap", type=float, default=900.0, help="seconds")
    ap.add_argument("--timeline-gap", type=float, default=300.0, help="seconds")
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--criteria", default=str(ROOT / "config" / "criteria.yaml"))
    ap.add_argument("--validation-config", default=str(ROOT / "config" / "validation.yaml"))
    ap.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    ap.set_defaults(func=cmd_rebuild)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
