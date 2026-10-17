"""What-if mix (spec: docs/methodology/whatif-mix.md). Offline: the shipped
config/decision.yaml plus synthetic prices and CPI. Existing tests are untouched."""

from __future__ import annotations

from qrl import decision_config, decision_report


def test_whatif_public_aliases_are_the_private_objects():
    assert decision_config.blend_portfolio is decision_config._blend
    assert decision_config.check_full is decision_config._check_full
    assert decision_config.SUM_TOLERANCE == decision_config._EPS == 1e-9
    for name in (
        "pct",
        "signed",
        "portfolio_section",
        "return_section",
        "window_section",
        "scenario_section",
        "withdrawal_section",
        "year_one_section",
        "switching_note",
    ):
        assert getattr(decision_report, name) is getattr(decision_report, f"_{name}")
    for const in ("DOTCOM_PROXY_NOTE", "KNOWN_GAP_NOTE", "DRAWDOWN_NOTE"):
        assert isinstance(getattr(decision_report, const), str)
