from pathlib import Path

from qrl.site_core import build_core_comparison

ROOT = Path(__file__).resolve().parents[1]


def test_parses_committed_files():
    block = build_core_comparison(ROOT)
    assert block is not None
    assert block["sources"] == {
        "compare": "research/core_compare.md",
        "reveal": "research/core_reveal.md",
    }
    research = block["research"]
    assert [r["id"] for r in research] == list("ABCDEFG")
    assert research[0]["CAGR"] == "6.1%"
    assert research[0]["rule"].startswith("current:")

    reveal = block["reveal"]
    assert reveal["event_id"] == 1
    assert "VALIDATION-SEEN" in reveal["banner"]
    assert "covid_2020" in reveal["windows"]
    assert "inflation_2022" in reveal["windows"]
    assert reveal["cut_date"] == "2022-10-31"
    assert len(reveal["cells"]) == 14
    assert {c["id"] for c in reveal["cells"]} == {"E", "F", "G"}
    assert len(reveal["breaches"]) == 3
    assert [b["id"] for b in reveal["breaches"]] == ["E", "F", "G"]


def test_missing_files_are_omitted(tmp_path):
    assert build_core_comparison(tmp_path) is None


def test_only_compare_present(tmp_path):
    (tmp_path / "research").mkdir()
    src = (ROOT / "research" / "core_compare.md").read_text()
    (tmp_path / "research" / "core_compare.md").write_text(src)
    block = build_core_comparison(tmp_path)
    assert block is not None
    assert "reveal" not in block
    assert len(block["research"]) == 7
