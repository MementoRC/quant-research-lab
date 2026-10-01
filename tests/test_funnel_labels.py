"""The research funnel must not call validation-evaluated candidates 'passed'."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_build_site():
    spec = importlib.util.spec_from_file_location(
        "build_site_labels", ROOT / "scripts" / "build_site.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_funnel_validation_stage_label(tmp_path):
    (tmp_path / "research.json").write_text(
        json.dumps(
            {"total_attempts": 5, "funnel": {"tested": 5, "passed_research": 3, "validated": 2}}
        )
    )
    funnel = _load_build_site()._research_funnel(tmp_path)
    labels = {s["key"]: s["label"] for s in funnel["stages"]}
    assert labels["passed_validation"] == "Evaluated on validation"
    assert "Passed validation" not in labels.values()


def test_index_html_does_not_claim_passed_validation():
    assert "Passed validation" not in (ROOT / "site" / "index.html").read_text()
