"""qrl.broker and qrl.rebalance must import without hb-market-connector
(spec "Testing"): CI never installs it, and the adapter is broker-env only."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CODE = (
    "import sys\n"
    "import qrl.broker, qrl.rebalance\n"
    "leaked = sorted(m for m in sys.modules if m.split('.')[0] == 'market_connector')\n"
    "print(leaked)\n"
)


def test_importing_broker_and_rebalance_never_imports_market_connector():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    out = subprocess.run(
        [sys.executable, "-c", CODE], capture_output=True, text=True, check=True, env=env
    )
    assert out.stdout.strip() == "[]"


SCRIPT_CODE = (
    "import runpy, sys\n"
    f"runpy.run_path({str(ROOT / 'scripts' / 'rebalance.py')!r}, run_name='rebalance_cli')\n"
    "leaked = sorted(m for m in sys.modules if m.split('.')[0] == 'market_connector')\n"
    "print(leaked)\n"
)


def test_loading_the_rebalance_script_never_imports_market_connector():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    out = subprocess.run(
        [sys.executable, "-c", SCRIPT_CODE], capture_output=True, text=True, check=True, env=env
    )
    assert out.stdout.strip() == "[]"
