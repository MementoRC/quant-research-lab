"""RSP sleeve report writer and its dashboard block (spec:
docs/methodology/rsp-sleeve.md, "Tests" and step 9)."""

from __future__ import annotations

from qrl.rsp_report import render_markdown
from qrl.site_core import RSP_PATH, build_rsp_sleeve

REPORT = {
    "run_id": 9,
    "passed": False,
    "failure_reasons": "combined_sharpe_improvement",
    "metrics": {
        "trades": 1,
        "sharpe": 0.55,
        "cagr": 0.08,
        "max_drawdown": 0.5,
        "core_sharpe": 0.9,
        "core_cagr": 0.1,
        "core_max_drawdown": 0.2,
        "combined_sharpe": 0.92,
        "combined_cagr": 0.1,
        "combined_max_drawdown": 0.21,
        "improvement_sharpe": 0.1,
    },
    "validation_note": "not run: failed on the research period",
    "combined_config_hash": "abc123def456",
}


def test_render_markdown_states_the_verdict_and_both_portfolios():
    text = render_markdown(REPORT)
    assert text.startswith("# RSP sleeve: 80% core + 20% RSP vs 100% core")
    assert "- verdict: FAILED (combined_sharpe_improvement)" in text
    assert "- attempts: 1" in text
    assert "| core alone (100%) |" in text
    assert "| core 80% + RSP 20% |" in text
    assert "not run: failed on the research period" in text
    assert "holdout" in text
    assert "sealed" in text


def test_render_markdown_passed():
    text = render_markdown({**REPORT, "passed": True, "failure_reasons": None})
    assert "- verdict: PASSED" in text


def test_site_block_parses_the_report(tmp_path):
    assert build_rsp_sleeve(tmp_path) is None
    (tmp_path / "research").mkdir()
    (tmp_path / RSP_PATH).write_text(render_markdown(REPORT))
    block = build_rsp_sleeve(tmp_path)
    assert block is not None
    assert block["source"] == "research/rsp_sleeve.md"
    assert block["header"]["verdict"] == "FAILED (combined_sharpe_improvement)"
    assert [s["title"] for s in block["sections"]][0] == "Result"
