"""What-if shock (spec: docs/methodology/whatif-shock.md): an owner-defined
stretch of bad years put in front of each start year's real history, then the
decision report's own withdrawal code. The only new calculations are the stretch
returns, the synthetic CPI and the splice factor. Pure functions; the script does
the IO. Every price and CPI frame is cut at the research end (2018-12-31) as
`qrl.decision.withdrawal_rows` cuts it, and nothing is ever unsealed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

from .decision_config import ID_PATTERN

GROUPS = ("stocks", "gold", "long_bonds", "short_bonds")
YEAR_KEYS = (*GROUPS, "inflation")
FILE_KEYS = ("name", "years")
MAX_YEARS = 10
MAX_RETURN = 2.0  # +200%
MIN_INFLATION, MAX_INFLATION = -0.10, 0.30


@dataclass(frozen=True)
class Shock:
    name: str
    years: tuple[dict[str, float], ...]  # in order; each has exactly YEAR_KEYS


def _exact_keys(raw: object, keys: tuple[str, ...], what: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"{what} must be a mapping with exactly the keys {list(keys)}")
    unknown = sorted(str(k) for k in raw if k not in keys)
    missing = [k for k in keys if k not in raw]
    if unknown or missing:
        raise ValueError(f"{what}: unknown key(s) {unknown}, missing key(s) {missing}")
    return raw


def _number(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"{what}: {value!r} is not a finite number")
    return float(value)


def _year(raw: object, k: int) -> dict[str, float]:
    what = f"shock year {k}"
    entry = _exact_keys(raw, YEAR_KEYS, what)
    year = {key: _number(entry[key], f"{what} {key}") for key in YEAR_KEYS}
    for group in GROUPS:
        if not -1 < year[group] <= MAX_RETURN:
            raise ValueError(
                f"{what} {group} {year[group]:g} must be above -1 and at most {MAX_RETURN:g}"
            )
    if not MIN_INFLATION <= year["inflation"] <= MAX_INFLATION:
        raise ValueError(
            f"{what} inflation {year['inflation']:g} must be in "
            f"[{MIN_INFLATION:g}, {MAX_INFLATION:g}]"
        )
    return year


def load_shock(path: str | Path) -> Shock:
    """Parse and validate a shock file (read only). Raises ValueError (a refusal)
    on a missing or unreadable file, invalid YAML, keys other than exactly `name`
    and `years`, a name not matching [A-Za-z0-9_-]+, `years` not a list of 1 to 10
    entries, a year whose keys are not exactly the four groups plus `inflation`,
    a value that is not a finite number (booleans and strings refused), a return
    not in (-1, 2] or an inflation not in [-0.10, 0.30]."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError(f"shock file {path} cannot be read ({exc.strerror or exc})") from exc
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"shock file is not valid YAML ({exc})") from exc
    doc = _exact_keys(doc, FILE_KEYS, "shock file")
    name = doc["name"]
    if not isinstance(name, str) or not ID_PATTERN.fullmatch(name):
        raise ValueError(f"shock name {name!r} must match [A-Za-z0-9_-]+")
    years = doc["years"]
    if not isinstance(years, list) or not 1 <= len(years) <= MAX_YEARS:
        raise ValueError(f"shock `years` must be a list of 1 to {MAX_YEARS} entries")
    return Shock(name, tuple(_year(entry, k) for k, entry in enumerate(years, 1)))
