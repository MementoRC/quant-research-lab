"""Markdown for the RSP sleeve result (spec: docs/methodology/rsp-sleeve.md,
step 9). Percentages only; written once, pass or fail."""

from __future__ import annotations

from .decision_report import _pct


def _row(label: str, m: dict, prefix: str) -> str:
    cells = [
        _pct(m[f"{prefix}cagr"]),
        f"{m[f'{prefix}sharpe']:.2f}",
        _pct(m[f"{prefix}max_drawdown"]),
    ]
    return "| " + " | ".join([label, *cells]) + " |"


def render_markdown(r: dict) -> str:
    m = r["metrics"]
    verdict = "PASSED" if r["passed"] else f"FAILED ({r['failure_reasons']})"
    return "\n".join(
        [
            "# RSP sleeve: 80% core + 20% RSP vs 100% core",
            "",
            "One fixed candidate (buy-and-hold RSP), no search. Spec: docs/methodology/rsp-sleeve.md.",
            "",
            f"- run: {r['run_id']}",
            "- attempts: 1",
            f"- verdict: {verdict}",
            f"- combined_fixed.yaml config hash: `{r['combined_config_hash']}`",
            "",
            "## Result",
            "",
            "Research period 2005-01-01 to 2018-12-31, costs from criteria.yaml.",
            "",
            "| portfolio | CAGR | Sharpe | max drawdown |",
            "|---|---|---|---|",
            _row("core alone (100%)", m, "core_"),
            _row("core 80% + RSP 20%", m, "combined_"),
            "",
            f"- Sharpe improvement over core alone: {m['improvement_sharpe']:.2f}",
            f"- RSP alone: CAGR {_pct(m['cagr'])}, Sharpe {m['sharpe']:.2f}, "
            f"max drawdown {_pct(m['max_drawdown'])}, {m['trades']} trade day(s)",
            "",
            "## Validation",
            "",
            r["validation_note"],
            "",
            "## Notes",
            "",
            "- The holdout (2023 onward) stays sealed.",
            "- Nothing was tuned or rerun. A retry needs a new dated, owner-approved amendment.",
            "",
        ]
    )
