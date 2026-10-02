"""Unattended search-loop CLI (milestone 2.4): seed a run, test batches of
candidates against the research period only, and summarize progress for the
agent driving the loop between batches. See AGENTS.md's "Unattended search
protocol" for the exact command sequence.

Usage:
    python scripts/search.py seed --lane A --synthetic
    python scripts/search.py seed --lane B --families trend_pullback,quiet_pullback --synthetic
    python scripts/search.py seed --lane C --confirm-lane-c --synthetic
    python scripts/search.py seed --lane A --universe config/universe.yaml
    python scripts/search.py seed --lane A --pass-rule combined --description "..."
    python scripts/search.py batch --run 1 --n 200 --synthetic
    python scripts/search.py batch --run 1 --n 200 --max-seconds 1800
    python scripts/search.py summary --run 1
    python scripts/search.py note --run 1 --batch 2 --text "mutated the winners"

Every `seed` records a data-source fingerprint (`--synthetic` + `--universe`);
a later `batch` (and `validate.py`/`walkforward.py`) against the same run
must match it, or the ledger refuses to continue -- see
`qrl.ledger.data_source_fingerprint` and `Ledger.check_data_source`.

`seed --pass-rule combined` (default `standalone`) pre-registers the combined
pass rule for the run (PLAN.md 2.5, amendment 2026-10-01; `qrl.combined`):
candidates are graded by whether they improve core + sleeve over the core
alone, and every later `batch` refuses if `config/combined.yaml`, the
profile's capital split, or the portfolio's core has changed since seeding.

`seed --pass-rule combined_null` (PLAN.md 2.5, amendment 2026-10-02, run 5)
pre-registers the "beat the null" rule: same, but graded against core + the
equal-weight null sleeve over the run's universe, with thresholds in
`config/combined_null.yaml` (the default `--combined-config` for such runs).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.combined import (  # noqa: E402
    PASS_RULES,
    combined_config_for_run,
    config_path_for,
    core_tickers,
    load_rule_config,
)
from qrl.criteria import load_criteria  # noqa: E402
from qrl.ledger import (  # noqa: E402
    DEFAULT_LEDGER_PATH,
    SEED_LANES,
    Ledger,
    LedgerError,
    candidate_key,
    data_source_fingerprint,
)
from qrl.profile import ProfileReport, analyze_profile, load_profile  # noqa: E402
from qrl.search import (  # noqa: E402
    SearchData,
    compute_benchmark_metrics,
    evaluate_candidate,
    propose_batch,
    pruned_regions,
)
from qrl.strategies import REGISTRY, SLEEVE_REGISTRY  # noqa: E402
from qrl.universe import load_universe  # noqa: E402

LANE_A_FAMILIES = tuple(SLEEVE_REGISTRY)
SEARCHABLE_SPACES: dict[str, dict[str, list]] = {
    **{name: spec.space for name, spec in SLEEVE_REGISTRY.items()},
    "core_trend": REGISTRY["core_trend"].space,
}
DEFAULT_UNIVERSE_TICKERS = ("QQQ", "GLD", "TLT")


def _parse_families(raw: str) -> list[str]:
    return [f.strip() for f in raw.split(",") if f.strip()]


def _encode_seed_description(description: str, families: list[str]) -> str:
    return json.dumps({"description": description, "families": families})


def _decode_seed_description(raw: str) -> tuple[str, list[str]]:
    try:
        payload = json.loads(raw)
        return payload.get("description", ""), list(payload.get("families", []))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return raw, []


def _get_run(ledger: Ledger, run_id: int) -> dict | None:
    for run in ledger.list_runs():
        if run["run_id"] == run_id:
            return run
    return None


def _check_data_source(ledger: Ledger, run_id: int, data_source: dict) -> int | None:
    """Returns an exit code if the check fails outright, or None if the
    caller should proceed (a match, or a legacy run with no recorded data
    source, which is unverifiable rather than a mismatch)."""
    try:
        matched = ledger.check_data_source(run_id, data_source)
    except LedgerError as err:
        print(str(err), file=sys.stderr)
        return 2
    if not matched:
        print(
            f"Run {run_id} has no recorded data source (seeded before it was tracked); "
            "cannot verify --synthetic/--universe match.",
            file=sys.stderr,
        )
    return None


def _lane_c_fit(report: ProfileReport) -> list[str]:
    prefix = "Strategy families that fit:"
    for line in report.implications:
        if line.startswith(prefix):
            names = line[len(prefix) :].rstrip(".").strip()
            return [n.strip() for n in names.split(",") if n.strip()]
    return []


def _print_lane_c_report(report: ProfileReport, families: list[str]) -> None:
    print("Lane C profile analysis:")
    for line in report.implications:
        print(f"  {line}")
    for line in report.conflicts:
        print(f"  CONFLICT: {line}")
    print(f"Families that fit and are searchable: {families}")


def _families_for_lane(lane: str, args: argparse.Namespace, criteria: dict) -> list[str] | None:
    """Resolve which families a seed should use. Returns None (after
    printing why) when the lane isn't ready to start a run yet."""
    if lane == "A":
        return _parse_families(args.families) if args.families else list(LANE_A_FAMILIES)
    if lane == "B":
        if not args.families:
            print("Lane B requires --families (comma-separated).", file=sys.stderr)
            return None
        return _parse_families(args.families)

    profile = load_profile(args.profile)
    report = analyze_profile(profile, criteria)
    families = [f for f in _lane_c_fit(report) if f in SEARCHABLE_SPACES]
    _print_lane_c_report(report, families)
    if not args.confirm_lane_c:
        print("Lane C is the least targeted seed; pass --confirm-lane-c to start a run.")
        return None
    return families


def cmd_seed(args: argparse.Namespace) -> int:
    criteria, criteria_hash = load_criteria(args.criteria)
    families = _families_for_lane(args.lane, args, criteria)
    if families is None:
        return 2
    unknown = sorted(set(families) - SEARCHABLE_SPACES.keys())
    if unknown:
        print(f"Unknown families: {unknown}", file=sys.stderr)
        return 2
    if not families:
        print("No families to seed.", file=sys.stderr)
        return 2

    universe = load_universe(args.universe)
    data_source = data_source_fingerprint(
        args.synthetic, universe["name"], list(universe["tickers"])
    )

    combined_hash = None
    if args.pass_rule != "standalone":
        config_path = config_path_for(args.pass_rule, args.combined_config, ROOT / "config")
        try:
            _, combined_hash = load_rule_config(
                args.pass_rule, config_path, args.profile, args.portfolio
            )
        except ValueError as err:
            print(str(err), file=sys.stderr)
            return 2

    description = args.description or f"lane {args.lane}: {', '.join(families)}"
    with Ledger(args.ledger) as ledger:
        run_id = ledger.start_run(
            criteria_hash,
            args.lane,
            _encode_seed_description(description, families),
            data_source=data_source,
            pass_rule=args.pass_rule,
            combined_config_hash=combined_hash,
        )
    data_label = "synthetic" if args.synthetic else "real"
    print(
        f"Started run {run_id} (lane {args.lane}, families: {', '.join(families)}, "
        f"data: {data_label}, universe {universe['name']})"
    )
    if combined_hash is not None:
        print(f"Pass rule: {args.pass_rule} (config hash {combined_hash})")
    return 0


def _resolve_families(run: dict, args: argparse.Namespace) -> list[str]:
    _, run_families = _decode_seed_description(run["seed_description"] or "")
    families = _parse_families(args.families) if args.families else run_families
    return [f for f in families if f in SEARCHABLE_SPACES]


def _test_one_candidate(
    ledger: Ledger,
    run_id: int,
    criteria_hash: str,
    universe_name: str,
    family: str,
    params: dict,
    data: SearchData,
    criteria: dict,
    bench: dict,
    history: list[dict],
    combined: tuple[dict, str] | None = None,
) -> bool:
    combined_cfg, combined_hash = combined if combined is not None else (None, None)
    outcome = evaluate_candidate(family, params, data, criteria, bench, combined_cfg=combined_cfg)
    ledger.record_test(
        run_id,
        criteria_hash,
        family,
        params,
        universe_name,
        outcome["metrics"],
        outcome["passed"],
        outcome["failure_reasons"],
        combined_config_hash=combined_hash,
    )
    history.append(
        {
            "family": family,
            "params": params,
            "passed": outcome["passed"],
            "failure_reasons": outcome["failure_reasons"],
            "candidate_key": candidate_key(family, params, universe_name, "research"),
        }
    )
    return bool(outcome["passed"])


def _deadline_hit(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _run_batch(
    ledger: Ledger,
    run_id: int,
    criteria: dict,
    criteria_hash: str,
    families: list[str],
    universe: dict,
    args: argparse.Namespace,
    combined: tuple[dict, str] | None = None,
) -> tuple[int, int, int]:
    spaces = {f: SEARCHABLE_SPACES[f] for f in families}
    sleeve_tickers = list(universe["tickers"])
    universe_name = universe["name"]

    needed = set(sleeve_tickers) | set(DEFAULT_UNIVERSE_TICKERS) | set(criteria["benchmarks"])
    if combined is not None:
        needed |= set(core_tickers(combined[0]["core"]))
    data = SearchData.load(sorted(needed), synthetic=args.synthetic)
    bench = compute_benchmark_metrics(data, criteria)
    history = ledger.list_tests(run_id)
    deadline = time.monotonic() + args.max_seconds if args.max_seconds is not None else None

    tested = passed = failed = 0
    while tested < args.n:
        if _deadline_hit(deadline):
            print(f"Stopping: time budget reached after {tested} candidate(s).")
            break
        proposals = propose_batch(
            history,
            spaces,
            args.n - tested,
            args.seed + tested,
            universe=universe_name,
            sleeve_tickers=sleeve_tickers,
        )
        if not proposals:
            print("No further unique candidates to propose; stopping early.")
            break
        for family, params in proposals:
            if _deadline_hit(deadline):
                print(f"Stopping: time budget reached after {tested} candidate(s).")
                return tested, passed, failed
            ok = _test_one_candidate(
                ledger,
                run_id,
                criteria_hash,
                universe_name,
                family,
                params,
                data,
                criteria,
                bench,
                history,
                combined,
            )
            tested += 1
            passed += int(ok)
            failed += int(not ok)
            if tested % 10 == 0:
                print(f"  ... {tested}/{args.n} tested ({passed} passed, {failed} failed)")
    return tested, passed, failed


def cmd_batch(args: argparse.Namespace) -> int:
    criteria, criteria_hash = load_criteria(args.criteria)
    universe = load_universe(args.universe)
    data_source = data_source_fingerprint(
        args.synthetic, universe["name"], list(universe["tickers"])
    )
    with Ledger(args.ledger) as ledger:
        run = _get_run(ledger, args.run)
        if run is None:
            print(f"Unknown run {args.run}", file=sys.stderr)
            return 2
        if run["criteria_hash"] != criteria_hash:
            print(
                "Criteria hash has changed since this run started; refusing to continue.",
                file=sys.stderr,
            )
            return 2
        rule = run.get("pass_rule") or "standalone"
        try:
            combined = combined_config_for_run(
                run,
                config_path_for(rule, args.combined_config, ROOT / "config"),
                args.profile,
                args.portfolio,
                universe_tickers=list(universe["tickers"]),
            )
        except ValueError as err:
            print(str(err), file=sys.stderr)
            return 2
        check_result = _check_data_source(ledger, args.run, data_source)
        if check_result is not None:
            return check_result
        families = _resolve_families(run, args)
        if not families:
            print("No searchable families for this run; pass --families.", file=sys.stderr)
            return 2
        tested, passed, failed = _run_batch(
            ledger, args.run, criteria, criteria_hash, families, universe, args, combined
        )
    print(f"Batch complete: tested {tested}, passed {passed}, failed {failed}.")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    with Ledger(args.ledger) as ledger:
        run = _get_run(ledger, args.run)
        if run is None:
            print(f"Unknown run {args.run}", file=sys.stderr)
            return 2
        summary = ledger.summary(run_id=args.run)
        history = ledger.list_tests(args.run)
        notes = ledger.list_notes(args.run)

    _, families = _decode_seed_description(run["seed_description"] or "")
    spaces = {f: SEARCHABLE_SPACES[f] for f in families if f in SEARCHABLE_SPACES}
    pruned = pruned_regions(history, spaces)

    print(
        f"Run {args.run} (lane {run['seed_lane']}): tested {summary['tested']}, "
        f"passed {summary['passed']}, validated {summary['validated']}"
    )
    data_source = run.get("data_source")
    if data_source:
        label = "synthetic" if data_source.get("synthetic") else "real"
        print(f"Data: {label}, universe {data_source.get('universe')}")
    else:
        print("Data: not recorded")
    pass_rule = run.get("pass_rule") or "standalone"
    if run.get("combined_config_hash"):
        print(f"Pass rule: {pass_rule} (config hash {run.get('combined_config_hash')})")
    else:
        print(f"Pass rule: {pass_rule}")
    print("By family:")
    for fam, counts in sorted(summary["by_family"].items()):
        print(f"  {fam:<16} tested {counts['tested']:>4}  passed {counts['passed']:>4}")
    print("Near-misses (failure reason -> count):")
    for reason, count in sorted(summary["near_misses"].items(), key=lambda kv: -kv[1]):
        print(f"  {reason:<30} {count}")
    print("Exhausted regions (family.parameter = value, all failures so far):")
    for family, key, value in sorted(pruned, key=lambda t: (t[0], t[1], str(t[2]))):
        print(f"  {family}.{key} = {value!r}")
    print("Notes:")
    for note in notes:
        print(f"  [batch {note['batch_no']}] {note['text']}")
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    with Ledger(args.ledger) as ledger:
        ledger.record_note(args.run, args.batch, args.text)
    print(f"Recorded note for run {args.run}, batch {args.batch}.")
    return 0


def _add_combined_args(parser: argparse.ArgumentParser, *, profile: bool) -> None:
    # Default: config/combined.yaml or config/combined_null.yaml per pass rule.
    parser.add_argument("--combined-config", default=None)
    parser.add_argument("--portfolio", default=str(ROOT / "config" / "portfolio.yaml"))
    if profile:
        parser.add_argument("--profile", default=str(ROOT / "config" / "profile.yaml"))


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--ledger", default=str(ROOT / DEFAULT_LEDGER_PATH))
    ap.add_argument("--criteria", default=str(ROOT / "config" / "criteria.yaml"))
    sub = ap.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Start a search run from a seed lane.")
    p_seed.add_argument("--lane", choices=SEED_LANES, required=True)
    p_seed.add_argument("--description", default=None)
    p_seed.add_argument("--families", default=None, help="comma-separated family names")
    p_seed.add_argument("--profile", default=str(ROOT / "config" / "profile.yaml"))
    p_seed.add_argument("--confirm-lane-c", action="store_true")
    # This seed pins the run's data source: every later `batch` (and
    # `validate.py`/`walkforward.py`) call against this run_id must pass a
    # matching --synthetic/--universe, or Ledger.check_data_source refuses to
    # continue (see qrl.ledger.data_source_fingerprint).
    p_seed.add_argument("--synthetic", action="store_true")
    p_seed.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    # Pre-registered per run (PLAN.md 2.5 amendment 2026-10-01): 'combined'
    # binds config/combined.yaml + the capital split + the core spec by hash;
    # 'combined_null' (amendment 2026-10-02, run 5) the same with combined_null.yaml.
    p_seed.add_argument("--pass-rule", choices=PASS_RULES, default="standalone")
    _add_combined_args(p_seed, profile=False)
    p_seed.set_defaults(func=cmd_seed)

    p_batch = sub.add_parser("batch", help="Propose, test, and record a batch of candidates.")
    p_batch.add_argument("--run", type=int, required=True)
    p_batch.add_argument("--n", type=int, required=True)
    p_batch.add_argument("--max-seconds", type=float, default=None)
    p_batch.add_argument("--seed", type=int, default=0)
    p_batch.add_argument("--synthetic", action="store_true")
    p_batch.add_argument("--universe", default=str(ROOT / "config" / "universe.yaml"))
    p_batch.add_argument("--families", default=None, help="override the run's seeded families")
    _add_combined_args(p_batch, profile=True)
    p_batch.set_defaults(func=cmd_batch)

    p_summary = sub.add_parser("summary", help="Print funnel, near-misses, pruned regions, notes.")
    p_summary.add_argument("--run", type=int, required=True)
    p_summary.set_defaults(func=cmd_summary)

    p_note = sub.add_parser("note", help="Record a between-batch note.")
    p_note.add_argument("--run", type=int, required=True)
    p_note.add_argument("--batch", type=int, required=True)
    p_note.add_argument("--text", required=True)
    p_note.set_defaults(func=cmd_note)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
