"""Local, read-only check that the committed research reports still match the code.

Rebuilds each safely-rebuildable report into a temp dir and compares it with the
committed file. Prints one line per report (MATCH / DIFF / SKIP / ERROR), a short diff
for each DIFF, and exits 1 on any DIFF or ERROR. Never writes into the repo and never
touches the ledger; it needs the local data cache (CI has none).

Usage:
    python scripts/docs_regen.py
    python scripts/docs_regen.py --only research/decision.md
    python scripts/docs_regen.py --list
"""

from __future__ import annotations

import argparse
import subprocess  # nosec B404 - fixed argv lists only, no shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl import regen  # noqa: E402

TIMEOUT_SECONDS = 1800
STDERR_LINES = 20


def run_spec(spec: regen.ReportSpec, tmp: Path) -> regen.Result:
    """Rebuild one report into `tmp` and compare it with the committed file."""
    committed_path = ROOT / spec.report
    if not committed_path.exists():
        return regen.Result(spec.report, regen.ERROR, f"committed report missing: {committed_path}")
    absent = [n for n in spec.needs if not (ROOT / n).exists()]
    if absent:
        return regen.Result(spec.report, regen.SKIP, f"{spec.missing_reason}: {absent[0]}")
    committed = committed_path.read_text(encoding="utf-8")
    try:
        argv = spec.command(tmp, committed)
    except ValueError as exc:
        return regen.Result(spec.report, regen.ERROR, f"{spec.report}: {exc}")
    try:
        proc = subprocess.run(  # nosec B603 - fixed list, no shell
            [sys.executable, str(ROOT / argv[0]), *argv[1:]],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return regen.Result(spec.report, regen.ERROR, f"timed out after {TIMEOUT_SECONDS}s")
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout).splitlines()[-STDERR_LINES:])
        return regen.Result(
            spec.report, regen.ERROR, f"{argv[0]} exited {proc.returncode}:\n{tail}"
        )
    out = tmp / spec.output
    if not out.exists():
        return regen.Result(spec.report, regen.ERROR, f"{argv[0]} did not write {out}")
    diff = regen.compare(committed, out.read_text(encoding="utf-8"), spec.volatile)
    if diff:
        return regen.Result(spec.report, regen.DIFF, f"{len(diff)} diff lines", diff)
    return regen.Result(spec.report, regen.MATCH)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--only", action="append", default=[], help="report to check (repeatable)")
    ap.add_argument("--list", action="store_true", help="print specs and skips, run nothing")
    args = ap.parse_args(argv)

    if args.list:
        for spec in regen.SPECS:
            print(f"CHECK {spec.report}")
        for report, reason in regen.SKIPPED.items():
            print(f"SKIP  {report}  {reason}")
        return 0

    known = {s.report for s in regen.SPECS}
    unknown = [o for o in args.only if o not in known]
    if unknown:
        print(f"ERROR unknown report(s) for --only: {unknown}; known: {sorted(known)}")
        return 1

    results: list[regen.Result] = []
    for name in regen.unlisted_reports(regen.RESEARCH_DIR):
        reason = "not in SPECS or SKIPPED in src/qrl/regen.py; list it"
        results.append(regen.Result(name, regen.ERROR, reason))
    with tempfile.TemporaryDirectory(prefix="docs-regen-") as tmp:
        for spec in regen.SPECS:
            if not args.only or spec.report in args.only:
                results.append(run_spec(spec, Path(tmp)))
    if not args.only:
        results.extend(regen.Result(r, regen.SKIP, why) for r, why in regen.SKIPPED.items())
    text, code = regen.summarize(results)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
