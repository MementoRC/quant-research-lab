"""Report what a trader profile implies and flag conflicts with it or with criteria.

Usage:
    python scripts/profile_check.py                       # example profile + criteria
    python scripts/profile_check.py --profile my.yaml
    python scripts/profile_check.py --criteria other.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl.criteria import load_criteria  # noqa: E402
from qrl.profile import ProfileReport, analyze_profile, load_profile  # noqa: E402


def _print_section(title: str, lines: list[str]) -> None:
    print(f"{title}:")
    if not lines:
        print("  (none)")
        return
    for line in lines:
        print(f"  - {line}")


def _print_report(report: ProfileReport) -> None:
    _print_section("Implications", report.implications)
    print()
    _print_section("Warnings", report.warnings)
    print()
    _print_section("Conflicts", report.conflicts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", default=str(ROOT / "config" / "profile.yaml"))
    ap.add_argument("--criteria", default=str(ROOT / "config" / "criteria.yaml"))
    args = ap.parse_args(argv)

    profile = load_profile(args.profile)
    criteria, _ = load_criteria(args.criteria)
    report = analyze_profile(profile, criteria)
    _print_report(report)
    return 1 if not report.ok else 0


if __name__ == "__main__":
    sys.exit(main())
