"""Keep the public docs honest: links, file names, status lines, commands, hashes.

Offline and fast; reads only committed files. Public docs are `README.md` and
`docs/methodology/*.md`. How to fix each failure:

- test_relative_links_resolve: fix the link target, or restore the file.
- test_backticked_repo_paths_exist: fix the path in the doc. If the doc names
  a removed file on purpose (history), add it to KNOWN_MISSING with a reason.
- test_methodology_docs_have_status: put `Status: <Draft|Approved|Implemented|
  Closed> ...` within the first 8 lines of the doc.
- test_index_lists_every_doc_with_matching_status: link the doc once in
  `docs/methodology/README.md` and write `(<keyword>...` in its entry, using
  the same keyword as the doc's Status line.
- test_index_links_exist: remove or fix the index entry that points nowhere.
- test_pixi_run_commands_exist: fix the task name, or add the task to pixi.toml.
- test_readme_schedule_matches_pages_workflow: make the README time equal the
  cron in `.github/workflows/pages.yml`.
- test_report_config_hashes_match: a report's recorded config hash differs
  from the config now. Never edit the report by hand. If the config changed
  on purpose after the report, record it in KNOWN_STALE with the reason; if
  not, restore the config.
- test_every_hash_line_is_checked: a report has a sha256/hash line that the
  checker cannot parse. Fix HASH_LINE (or the generator's format) so it is read.
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
import tomllib
from pathlib import Path

import pytest

from qrl.combined import load_combined_config
from qrl.criteria import load_criteria

ROOT = Path(__file__).resolve().parents[1]
METHODOLOGY = ROOT / "docs" / "methodology"
INDEX = METHODOLOGY / "README.md"

DOCS = [ROOT / "README.md", *sorted(METHODOLOGY.glob("*.md"))]
METHODOLOGY_DOCS = [p for p in sorted(METHODOLOGY.glob("*.md")) if p != INDEX]
REPORTS = sorted((ROOT / "research").glob("*.md"))

STATUS_KEYWORDS = {"draft", "approved", "implemented", "closed"}
STATUS_WINDOW = 8  # a Status line must appear within the first lines

REPO_PATH_PREFIXES = (
    "src/",
    "scripts/",
    "tests/",
    "config/",
    "research/",
    "docs/methodology/",
    ".github/",
)
# Ignored by design even if .gitignore is not read (a fresh clone lacks them).
IGNORED_BY_DESIGN = ("research/top_candidates.csv", "data/", "site/", "docs/superpowers/")

# {(doc, path): reason}: a doc names a file that no longer exists, on purpose.
KNOWN_MISSING: dict[tuple[str, str], str] = {
    ("docs/methodology/defensive-sleeve.md", "research/defensive_sleeve.md"): (
        "the doc states that this file is deliberately not created"
    ),
}

# {(report, config): reason}: the hash cannot be recomputed from a plain file.
NOT_PLAIN_HASH: dict[tuple[str, str], str] = {}

# {(report, config): reason}: the config changed after the report was written.
# Each fragility run is kept as its own report; the config moved on with the code.
KNOWN_STALE: dict[tuple[str, str], str] = {
    ("research/fragility_run1.md", "config/fragility.yaml"): (
        "config changed in 441ddf5 (N = 2) after run 1; run 1 used the 6874466 version"
    ),
    ("research/fragility_run2.md", "config/fragility.yaml"): (
        "config changed in 441ddf5 (N = 2) after run 2; run 2 used the 6874466 version"
    ),
    ("research/fragility_run3.md", "config/fragility.yaml"): (
        "config changed in a479f03 (rate-trend gate) after run 3"
    ),
    ("research/fragility_run4.md", "config/fragility.yaml"): (
        "config changed in 5253aff (XBRL fallbacks, run 5) after run 4"
    ),
    ("research/fragility_run5.md", "config/fragility.yaml"): (
        "config changed in fb80524 (same-concept fallbacks, run 6) after run 5"
    ),
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def rel(path: Path) -> str:
    """Repo-relative POSIX path, used in messages and dict keys."""
    return path.relative_to(ROOT).as_posix()


def numbered_lines(path: Path, *, skip_fences: bool = False) -> list[tuple[int, str]]:
    """(line number, text) pairs of a file; optionally without fenced code blocks."""
    result = []
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if skip_fences and in_fence:
            continue
        result.append((number, line))
    return result


def ignored_patterns() -> list[str]:
    """Positive patterns from .gitignore (negations and comments dropped)."""
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and ln[0] not in "#!"]


def is_ignored(path: str) -> bool:
    """True if a repo path is gitignored (or ignored by design)."""
    if path.startswith(IGNORED_BY_DESIGN):
        return True
    for pattern in ignored_patterns():
        if pattern.endswith("/") and path.startswith(pattern):
            return True
        if fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(Path(path).name, pattern):
            return True
    return False


def status_keyword(path: Path) -> str | None:
    """First word of the `Status: ` line in the first lines of a doc, lowercased.

    None if there is no such line.
    """
    for _, line in numbered_lines(path)[:STATUS_WINDOW]:
        if line.startswith("Status: "):
            words = line[len("Status: ") :].split()
            return words[0].rstrip(".,;:").lower() if words else ""
    return None


def index_entries() -> dict[str, str]:
    """Map each link target in the methodology index to its whole bullet text.

    A bullet is the `- ` line plus its indented continuation lines.
    """
    entries: dict[str, str] = {}
    bullet: list[str] = []

    def flush() -> None:
        text = " ".join(bullet)
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            entries[target] = text

    for _, line in numbered_lines(INDEX):
        if line.startswith("- "):
            flush()
            bullet = [line]
        elif bullet and line.startswith(" "):
            bullet.append(line.strip())
        else:
            flush()
            bullet = []
    flush()
    return entries


def pixi_tasks() -> set[str]:
    """Task names defined in pixi.toml, in [tasks] and [feature.*.tasks]."""
    config = tomllib.loads((ROOT / "pixi.toml").read_text(encoding="utf-8"))
    tasks = set(config.get("tasks", {}))
    for feature in config.get("feature", {}).values():
        tasks |= set(feature.get("tasks", {}))
    return tasks


def config_digest(config_name: str) -> str:
    """Hash of config/<name> exactly as the project computes it for reports.

    criteria.yaml and the combined_* files use the project's own loaders
    (12 characters); every other config is a plain sha256 of its bytes.
    """
    path = ROOT / "config" / config_name
    if config_name == "criteria.yaml":
        return load_criteria(path)[1]
    if config_name.startswith("combined"):
        profile, portfolio = ROOT / "config" / "profile.yaml", ROOT / "config" / "portfolio.yaml"
        return load_combined_config(path, profile, portfolio)[1]
    return hashlib.sha256(path.read_bytes()).hexdigest()


HASH_LINE = re.compile(
    r"^- (?:config/)?([\w.]+\.yaml) (?:config )?(?:sha256|hash): `([0-9a-f]{12,64})`"
)


def recorded_hashes() -> list[tuple[str, int, str, str]]:
    """(report, line, config, recorded hex) for hash lines naming an existing config."""
    found = []
    for report in REPORTS:
        for number, line in numbered_lines(report):
            match = HASH_LINE.match(line)
            if match and (ROOT / "config" / match.group(1)).is_file():
                found.append((rel(report), number, match.group(1), match.group(2)))
    return found


RECORDED_HASHES = recorded_hashes()


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


@pytest.mark.parametrize("doc", DOCS, ids=rel)
def test_relative_links_resolve(doc):
    """Every markdown link to a file points at something that exists."""
    problems = []
    for number, line in numbered_lines(doc, skip_fences=True):
        for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", line):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            file_part = target.split("#", 1)[0]
            if not (doc.parent / file_part).exists():
                problems.append(f"{rel(doc)}:{number}: broken link target {target!r}")
    assert not problems, "\n".join(problems)


def looks_like_repo_file(token: str) -> bool:
    """A backticked token that names a file under a known top-level folder."""
    if not token.startswith(REPO_PATH_PREFIXES):
        return False
    if re.search(r"[<>*{}?\s]", token):
        return False
    return bool(Path(token).suffix)


@pytest.mark.parametrize("doc", DOCS, ids=rel)
def test_backticked_repo_paths_exist(doc):
    """Every backticked repo file path in a doc exists (line suffixes ignored)."""
    problems = []
    for number, line in numbered_lines(doc):
        for token in re.findall(r"`([^`]+)`", line):
            path = re.sub(r"(::\w+|:\d+(-\d+)?)$", "", token)  # pytest node id or line suffix
            if not looks_like_repo_file(path) or is_ignored(path):
                continue
            if (ROOT / path).exists() or (rel(doc), path) in KNOWN_MISSING:
                continue
            problems.append(f"{rel(doc)}:{number}: `{token}` does not exist")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("doc", METHODOLOGY_DOCS, ids=rel)
def test_methodology_docs_have_status(doc):
    """Each methodology doc has `Status: <keyword> ...` near the top."""
    keyword = status_keyword(doc)
    assert keyword is not None, (
        f"{rel(doc)}: no line starting 'Status: ' in the first {STATUS_WINDOW} lines"
    )
    assert keyword in STATUS_KEYWORDS, (
        f"{rel(doc)}: Status starts with {keyword!r}, expected one of {sorted(STATUS_KEYWORDS)}"
    )


@pytest.mark.parametrize("doc", METHODOLOGY_DOCS, ids=rel)
def test_index_lists_every_doc_with_matching_status(doc):
    """The methodology index links the doc once, with '(<status keyword>' in its entry."""
    index_text = INDEX.read_text(encoding="utf-8")
    links = re.findall(rf"\]\({re.escape(doc.name)}(?:#[^)]*)?\)", index_text)
    assert len(links) == 1, f"{rel(INDEX)}: {doc.name} is linked {len(links)} times, expected 1"
    keyword = status_keyword(doc)
    entry = index_entries().get(doc.name, "")
    assert f"({keyword}" in entry.lower(), (
        f"{rel(INDEX)}: entry for {doc.name} lacks '({keyword}' (its Status keyword): {entry!r}"
    )


def test_index_links_exist():
    """Every methodology doc linked from the index exists."""
    problems = []
    for number, line in numbered_lines(INDEX):
        for target in re.findall(r"\]\(([^)\s]+\.md)\)", line):
            if not (METHODOLOGY / target).is_file():
                problems.append(f"{rel(INDEX)}:{number}: links missing doc {target!r}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("doc", DOCS, ids=rel)
def test_pixi_run_commands_exist(doc):
    """Every `pixi run <task>` in a doc names a task defined in pixi.toml."""
    tasks = pixi_tasks()
    command = re.compile(r"pixi run (?:(?:-e|--environment)[ =]\S+\s+)?([\w-]+)")
    problems = []
    for number, line in numbered_lines(doc):
        for task in command.findall(line):
            if task not in tasks:
                problems.append(f"{rel(doc)}:{number}: `pixi run {task}` is not a pixi.toml task")
    assert not problems, "\n".join(problems)


def test_readme_schedule_matches_pages_workflow():
    """Each 'HH:MM UTC' in the README equals a cron time in pages.yml."""
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    crons = {
        (int(hour), int(minute)) for minute, hour in re.findall(r'cron:\s*"(\d+) (\d+) ', workflow)
    }
    assert crons, "pages.yml: no 'cron:' line found"
    problems = []
    for number, line in numbered_lines(ROOT / "README.md"):
        for hour, minute in re.findall(r"\b(\d{1,2}):(\d{2}) UTC", line):
            if (int(hour), int(minute)) not in crons:
                problems.append(
                    f"README.md:{number}: '{hour}:{minute} UTC' not in pages.yml crons {crons}"
                )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    ("report", "line", "config", "recorded"),
    RECORDED_HASHES,
    ids=[f"{r}:{c}" for r, _, c, _ in RECORDED_HASHES],
)
def test_report_config_hashes_match(report, line, config, recorded):
    """A report's recorded config hash equals the config's hash now (or is known stale)."""
    key = (report, f"config/{config}")
    if key in NOT_PLAIN_HASH:
        pytest.skip(NOT_PLAIN_HASH[key])
    matches = config_digest(config).startswith(recorded)
    where = f"{report}:{line}: {config} hash `{recorded}`"
    if key in KNOWN_STALE:
        assert not matches, f"{where} now matches config/{config}; remove it from KNOWN_STALE"
    else:
        assert matches, f"{where} differs from config/{config} (add to KNOWN_STALE if intended)"


def test_every_hash_line_is_checked():
    """Each config-hash line in a report is parsed, so a format change can't hide it."""
    loose = re.compile(r"\b[\w.]+\.yaml\b.*\b(?:sha256|hash)\b.*`[0-9a-f]{12,64}`")
    parsed = {(report, line) for report, line, _, _ in RECORDED_HASHES}
    problems = []
    for report in REPORTS:
        for number, text in numbered_lines(report):
            if loose.search(text) and (rel(report), number) not in parsed:
                problems.append(f"{rel(report)}:{number}: hash line not parsed: {text.strip()!r}")
    assert not problems, "\n".join(problems)
