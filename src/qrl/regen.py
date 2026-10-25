"""Pure logic for the local report-regeneration check (scripts/docs_regen.py).

Each committed report in research/ is either rebuilt into a temp dir and compared
(`SPECS`) or deliberately skipped with a reason (`SKIPPED`). No subprocess, no IO
beyond listing a directory: the CLI runs the commands and feeds the text in here.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = ROOT / "research"
REPORT_SUFFIXES = (".md", ".txt")

MATCH, DIFF, SKIP, ERROR = "MATCH", "DIFF", "SKIP", "ERROR"
DIFF_LINES_SHOWN = 40

_AS_OF = re.compile(r"as-of date:\s*(\d{4}-\d{2}-\d{2})")

# Builds the argv (script path relative to the repo root, then its arguments) from the
# temp dir and the committed report text (fragility needs its as-of date from it).
CommandBuilder = Callable[[Path, str], tuple[str, ...]]


@dataclass(frozen=True)
class ReportSpec:
    """How to rebuild one committed report.

    report: path relative to the repo root, e.g. "research/decision.md".
    command: builds the script argv from (tmp dir, committed text).
    output: file name inside the tmp dir that the command writes and we compare.
    volatile: regexes; any line matching one is dropped from both sides before comparing.
        Only for lines that legitimately change per run (e.g. a generation timestamp).
    needs: caches (paths relative to the repo root) that must exist, else SKIP.
    missing_reason: the SKIP reason when a `needs` path is absent.
    """

    report: str
    command: CommandBuilder
    output: str
    volatile: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    missing_reason: str = "cache missing"


@dataclass(frozen=True)
class Result:
    """Outcome for one report: status is MATCH, DIFF, SKIP or ERROR."""

    report: str
    status: str
    detail: str = ""
    diff: list[str] = field(default_factory=list)


def parse_as_of(text: str) -> str:
    """Return the YYYY-MM-DD from the report's 'as-of date: ...' line."""
    found = _AS_OF.search(text)
    if found is None:
        raise ValueError("no 'as-of date: YYYY-MM-DD' line in the committed report")
    return found.group(1)


def _strip_volatile(text: str, volatile: Sequence[str]) -> list[str]:
    patterns = [re.compile(v) for v in volatile]
    return [ln for ln in text.splitlines() if not any(p.search(ln) for p in patterns)]


def compare(committed: str, regenerated: str, volatile: Sequence[str] = ()) -> list[str]:
    """Empty list when the texts match once volatile lines are dropped; else a unified diff."""
    old = _strip_volatile(committed, volatile)
    new = _strip_volatile(regenerated, volatile)
    return list(difflib.unified_diff(old, new, "committed", "regenerated", lineterm=""))


def _simple(script: str, *extra: str, out_flag: str = "--out-md", out: str) -> CommandBuilder:
    def build(tmp: Path, _committed: str) -> tuple[str, ...]:
        return (script, *extra, out_flag, str(tmp / out))

    return build


def _core_compare(tmp: Path, _committed: str) -> tuple[str, ...]:
    return (
        "scripts/core_compare.py",
        "--offline",
        "--out-md",
        str(tmp / "core_compare.md"),
        "--out-json",
        str(tmp / "core_compare.json"),
    )


def _fragility(tmp: Path, committed: str) -> tuple[str, ...]:
    return (
        "scripts/fragility.py",
        "--as-of",
        parse_as_of(committed),
        "--out-md",
        str(tmp / "fragility.md"),
        "--out-json",
        str(tmp / "fragility.json"),
    )


def _pit_coverage(tmp: Path, _committed: str) -> tuple[str, ...]:
    return ("scripts/pit_universe.py", "coverage", "--out", str(tmp / "pit_coverage.txt"))


def _price_caches(*tickers: str) -> tuple[str, ...]:
    return tuple(f"data/cache/{t}.parquet" for t in tickers)


# decision/longrun load these (config/decision.yaml portfolios + SPY proxy) and CPI;
# load_ohlcv(refresh=False) would still download any ticker missing from the cache.
_DECISION_NEEDS = (
    *_price_caches("SPY", "QQQ", "GLD", "IEF", "TLT", "SHY", "RSP"),
    "data/cache/macro_CPIAUCNS.parquet",
)
_PRICE_MISSING = "price/macro cache missing (would need a download)"

SPECS: tuple[ReportSpec, ...] = (
    ReportSpec(
        "research/decision.md",
        _simple("scripts/decision.py", out="decision.md"),
        "decision.md",
        needs=_DECISION_NEEDS,
        missing_reason=_PRICE_MISSING,
    ),
    ReportSpec(
        "research/longrun.md",
        _simple("scripts/longrun.py", out="longrun.md"),
        "longrun.md",
        needs=_DECISION_NEEDS,
        missing_reason=_PRICE_MISSING,
    ),
    ReportSpec(
        "research/withdrawal_rules.md",
        _simple("scripts/withdrawal_rules.py", out="withdrawal_rules.md"),
        "withdrawal_rules.md",
        needs=_DECISION_NEEDS,
        missing_reason=_PRICE_MISSING,
    ),
    ReportSpec(
        "research/staged_entry.md",
        _simple("scripts/staged_entry.py", out="staged_entry.md"),
        "staged_entry.md",
        needs=_DECISION_NEEDS,
        missing_reason=_PRICE_MISSING,
    ),
    ReportSpec(
        "research/core_compare.md",
        _core_compare,
        "core_compare.md",
        needs=_price_caches("SPY", "QQQ", "GLD", "IEF", "TLT", "SHY"),
        missing_reason=_PRICE_MISSING,
    ),
    ReportSpec(
        "research/fragility.md",
        _fragility,
        "fragility.md",
        needs=("data/cache/sec/facts", "data/cache/pit/pool.csv"),
        missing_reason="SEC cache missing",
    ),
    ReportSpec(
        "research/pit_coverage.txt",
        _pit_coverage,
        "pit_coverage.txt",
        needs=("data/cache/pit/features.parquet",),
        missing_reason="PIT cache missing",
    ),
)

SKIPPED: dict[str, str] = {
    "research/core_reveal.md": "one-time reveal; it writes the ledger and has no render-only path",
    "research/international_main.md": (
        "sealed one-shot international test (event 1); regenerating is refused by design"
    ),
    "research/overlay.md": "renderer runs only after ledger writes; a render-only entry is a follow-up",
    "research/rsp_sleeve.md": "needs --validation-note free text that cannot be recovered",
    "research/run5_validation.txt": "captured validation output, a ledger step",
    "research/run3_validation_rebuilt.txt": "captured validation output, a ledger step",
    **{
        f"research/fragility_run{n}.md": (
            "historical run under an older config (see KNOWN_STALE in tests/test_docs_freshness.py)"
        )
        for n in range(1, 6)
    },
}


def unlisted_reports(research_dir: Path) -> list[str]:
    """Reports (*.md, *.txt) in `research_dir` that are neither in SPECS nor SKIPPED.

    Names are 'research/<file>' to match the keys above.
    """
    known = {s.report for s in SPECS} | set(SKIPPED)
    found = sorted(
        f"research/{p.name}"
        for p in research_dir.iterdir()
        if p.is_file() and p.suffix in REPORT_SUFFIXES
    )
    return [name for name in found if name not in known]


def summarize(results: Iterable[Result]) -> tuple[str, int]:
    """One line per report, a short diff under each DIFF; exit code 1 on any DIFF or ERROR."""
    lines: list[str] = []
    bad = False
    for r in results:
        lines.append(f"{r.status:<5} {r.report}" + (f"  {r.detail}" if r.detail else ""))
        if r.status in (DIFF, ERROR):
            bad = True
        if r.status == DIFF:
            lines.extend(f"    {ln}" for ln in r.diff[:DIFF_LINES_SHOWN])
            if len(r.diff) > DIFF_LINES_SHOWN:
                lines.append(f"    ... {len(r.diff) - DIFF_LINES_SHOWN} more diff lines")
    return "\n".join(lines), 1 if bad else 0
