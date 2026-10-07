"""Parse the committed core-comparison markdown files for the public dashboard.

CI only sees committed files, so the site reads `research/core_compare.md` and
`research/core_reveal.md` (rendered deterministically elsewhere) instead of
recomputing anything. Cell values stay as the display strings in the markdown.
"""

from __future__ import annotations

import re
from pathlib import Path

COMPARE_PATH = "research/core_compare.md"
REVEAL_PATH = "research/core_reveal.md"
FRAGILITY_PATH = "research/fragility.md"
DECISION_PATH = "research/decision.md"

_BULLET = re.compile(r"^- ([^:]+): (.*)$")
_EVENT_ID = re.compile(r"event id (\d+)")


def _sections(text: str) -> dict[str, list[str]]:
    """Split on `## ` headings; the key "" holds everything before the first."""
    out: dict[str, list[str]] = {"": []}
    current = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        else:
            out[current].append(line)
    return out


def _table(lines: list[str]) -> list[dict[str, str]]:
    """Rows of the first pipe table in `lines`, keyed by header cell."""
    rows = [ln.strip() for ln in lines if ln.strip().startswith("|")]
    if len(rows) < 2:
        return []

    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip("|").split("|")]

    header = cells(rows[0])
    return [dict(zip(header, cells(r), strict=False)) for r in rows[2:]]


def _bullets(lines: list[str]) -> dict[str, str]:
    out = {}
    for line in lines:
        m = _BULLET.match(line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip().strip("`")
    return out


def _parse_windows_and_cut_date(windows_str: str) -> tuple[list[str], str]:
    """Extract windows list and cut date from 'window1, window2 (data cut at YYYY-MM-DD)' format."""
    # Match the cut date pattern
    cut_match = re.search(r"\(data cut at ([^\)]+)\)", windows_str)
    cut_date = cut_match.group(1) if cut_match else ""

    # Remove the cut date part and split by comma
    windows_part = re.sub(r"\s*\(data cut at [^\)]+\)", "", windows_str).strip()
    windows = [w.strip() for w in windows_part.split(",") if w.strip()]

    return windows, cut_date


def parse_compare(text: str) -> dict:
    sections = _sections(text)
    header = _bullets(sections[""])
    return {
        "header": header,
        "research": _table(sections.get("Research period", [])),
    }


def parse_reveal(text: str) -> dict:
    sections = _sections(text)
    banner = next((ln[2:].strip() for ln in sections[""] if ln.startswith("> ")), "")
    m = _EVENT_ID.search(banner)
    header = _bullets(sections[""])
    windows_str = header.get("windows revealed", "")
    windows, cut_date = _parse_windows_and_cut_date(windows_str)
    return {
        "banner": banner,
        "event_id": int(m.group(1)) if m else None,
        "windows": windows,
        "cut_date": cut_date,
        "header": header,
        "cells": _table(sections.get("Stress cells", [])),
        "breaches": _table(sections.get("Breaches", [])),
    }


def build_core_comparison(root: Path) -> dict | None:
    """The `core_comparison` block for results.json, or None if neither file exists."""
    block: dict = {"sources": {}}
    compare = root / COMPARE_PATH
    if compare.exists():
        parsed = parse_compare(compare.read_text())
        block["research"] = parsed["research"]
        block["header"] = parsed["header"]
        block["sources"]["compare"] = COMPARE_PATH
    reveal = root / REVEAL_PATH
    if reveal.exists():
        block["reveal"] = parse_reveal(reveal.read_text())
        block["sources"]["reveal"] = REVEAL_PATH
    return block if block["sources"] else None


def build_fragility(root: Path) -> dict | None:
    """The `fragility` block for results.json from the committed `research/fragility.md`
    (header bullets, class counts, the FRAGILE and WATCH table), or None if absent."""
    path = root / FRAGILITY_PATH
    if not path.exists():
        return None
    sections = _sections(path.read_text())
    return {
        "source": FRAGILITY_PATH,
        "header": _bullets(sections[""]),
        "summary": _table(sections.get("Summary", [])),
        "flagged": _table(sections.get("Fragile and watch", [])),
    }


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _parse_section(title: str, lines: list[str]) -> dict:
    """One `## ` section: its bullets, paragraphs and every pipe table in order.

    A `### ` heading titles the tables that follow it until the next heading.
    """
    bullets: list[str] = []
    paragraphs: list[str] = []
    tables: list[dict] = []
    sub: str | None = None
    pending: list[str] = []

    def flush() -> None:
        if len(pending) >= 2:
            tables.append(
                {
                    "title": sub,
                    "columns": _cells(pending[0]),
                    "rows": [_cells(r) for r in pending[2:]],
                }
            )
        pending.clear()

    for raw in lines:
        line = raw.strip()
        if line.startswith("|"):
            pending.append(line)
            continue
        flush()
        if line.startswith("### "):
            sub = line[4:].strip()
        elif line.startswith("- "):
            bullets.append(line[2:].strip())
        elif line:
            paragraphs.append(line)
    flush()
    return {"title": title, "bullets": bullets, "paragraphs": paragraphs, "tables": tables}


def build_decision(root: Path) -> dict | None:
    """The `decision` block for results.json from the committed `research/decision.md`,
    rendered generically (header bullets, then every `## ` section), or None if absent."""
    path = root / DECISION_PATH
    if not path.exists():
        return None
    sections = _sections(path.read_text())
    return {
        "source": DECISION_PATH,
        "header": _bullets(sections[""]),
        "sections": [_parse_section(t, ls) for t, ls in sections.items() if t],
    }
