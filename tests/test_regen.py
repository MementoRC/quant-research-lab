"""qrl.regen (the docs-regen check) and the defaults of the CLI flags it added.
Offline and fast: no generator is run."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest

from qrl import regen

ROOT = Path(__file__).resolve().parents[1]


class _ParsedError(Exception):
    def __init__(self, ns: argparse.Namespace) -> None:
        self.ns = ns


def _parsed_args(
    monkeypatch: pytest.MonkeyPatch, script: str, argv: list[str]
) -> argparse.Namespace:
    """Run the script's main(argv) and stop right after argparse, returning the namespace."""
    path = ROOT / "scripts" / script
    spec = importlib.util.spec_from_file_location(f"{path.stem}_regen_cli", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    real = argparse.ArgumentParser.parse_args

    def capture(self: argparse.ArgumentParser, args=None, namespace=None):  # noqa: ANN001, ANN202
        raise _ParsedError(real(self, args, namespace))

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture)
    with pytest.raises(_ParsedError) as caught:
        mod.main(argv)
    return caught.value.ns


# ---- compare


def test_compare_identical_is_empty():
    assert regen.compare("a\nb\n", "a\nb\n") == []


def test_compare_changed_line_shows_in_diff():
    diff = regen.compare("a\nb\n", "a\nc\n")
    assert any(ln == "+c" for ln in diff)
    assert any(ln == "-b" for ln in diff)


def test_compare_volatile_line_is_ignored():
    old, new = "x\ngenerated 2026-01-01\n", "x\ngenerated 2026-02-02\n"
    assert regen.compare(old, new, (r"^generated ",)) == []


def test_compare_volatile_does_not_mask_other_lines():
    old, new = "x\ngenerated 1\n", "y\ngenerated 2\n"
    diff = regen.compare(old, new, (r"^generated ",))
    assert "+y" in diff
    assert "-x" in diff
    assert not any(ln.startswith(("+generated", "-generated")) for ln in diff)


# ---- parse_as_of


def test_parse_as_of_found():
    assert regen.parse_as_of("# t\n- as-of date: 2026-10-04\n") == "2026-10-04"


def test_parse_as_of_missing_raises():
    with pytest.raises(ValueError, match="as-of date"):
        regen.parse_as_of("nothing here")


# ---- coverage rule


def test_unlisted_reports_flags_only_new_file(tmp_path: Path):
    listed = regen.SPECS[0].report
    skipped = next(iter(regen.SKIPPED))
    for rel in (listed, skipped, "research/brand_new.md"):
        (tmp_path / Path(rel).name).write_text("x")
    (tmp_path / "ignored.csv").write_text("x")
    assert regen.unlisted_reports(tmp_path) == ["research/brand_new.md"]


def test_every_real_report_is_listed_or_skipped():
    assert regen.unlisted_reports(ROOT / "research") == []


def test_specs_and_skips_exist_and_are_disjoint():
    spec_reports = [s.report for s in regen.SPECS]
    assert len(spec_reports) == len(set(spec_reports))
    assert not set(spec_reports) & set(regen.SKIPPED)
    for report in [*spec_reports, *regen.SKIPPED]:
        assert (ROOT / report).exists(), f"{report} is listed in qrl.regen but missing"


def test_spec_commands_write_into_tmp(tmp_path: Path):
    committed = "- as-of date: 2026-10-04\n"
    for spec in regen.SPECS:
        argv = spec.command(tmp_path, committed)
        assert (ROOT / argv[0]).exists()
        assert str(tmp_path / spec.output) in argv


# ---- summarize


def test_summarize_exit_codes():
    ok = [regen.Result("a", regen.MATCH), regen.Result("b", regen.SKIP, "why")]
    text, code = regen.summarize(ok)
    assert code == 0
    assert "MATCH" in text
    assert "why" in text
    assert regen.summarize([*ok, regen.Result("c", regen.DIFF, "1", ["-x", "+y"])])[1] == 1
    assert regen.summarize([*ok, regen.Result("d", regen.ERROR, "boom")])[1] == 1


def test_summarize_truncates_diff():
    diff = [f"+{i}" for i in range(100)]
    text, _ = regen.summarize([regen.Result("a", regen.DIFF, "", diff)])
    assert "+39" in text
    assert "+40" not in text
    assert "60 more" in text


# ---- new CLI flags keep their defaults


def test_core_compare_offline_defaults_off(monkeypatch: pytest.MonkeyPatch):
    assert _parsed_args(monkeypatch, "core_compare.py", []).offline is False
    assert _parsed_args(monkeypatch, "core_compare.py", ["--offline"]).offline is True


def test_pit_coverage_out_defaults_to_report_path(monkeypatch: pytest.MonkeyPatch):
    ns = _parsed_args(monkeypatch, "pit_universe.py", ["coverage"])
    assert ns.out == str(ROOT / "research" / "pit_coverage.txt")
