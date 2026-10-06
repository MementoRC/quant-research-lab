"""Balance-sheet fragility screen (EXPLORATION ONLY).

Spec: docs/superpowers/specs/2026-10-05-fragility-screen-design.md. Six
balance-sheet measures per company from SEC companyfacts, classified by the
pre-registered `config/fragility.yaml`. No price data and no returns are used.

Point-in-time rule (same as `qrl.fundamentals.pit_panel`): a fact is usable at
date t iff `filed < t`; per period end the latest filing wins (a restatement
counts once public); the latest fiscal year end must be within
`STALENESS_DAYS` of t. Flows are the latest fiscal year (annual duration), the
balance sheet is the instant at that same year end. Nothing is imputed: a
missing input makes the measure `n/a (reason)`.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from qrl import factor_data, pit_universe
from qrl import fundamentals as fd

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FRAGILITY_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "fragility.yaml"
LAG_TOLERANCE_DAYS = factor_data.ASSETS_LAG_TOLERANCE_DAYS

FRAGILE = "FRAGILE"
WATCH = "WATCH"
SOUND = "SOUND"
INSUFFICIENT = "INSUFFICIENT DATA"
NOT_APPLICABLE = "NOT APPLICABLE"
CLASS_ORDER = (FRAGILE, WATCH, SOUND, INSUFFICIENT, NOT_APPLICABLE)

MEASURE_KEYS = ("coverage", "net_debt_fcf", "maturities", "rate_trend", "altman_z", "piotroski")
MEASURE_LABELS = {
    "coverage": "interest coverage",
    "net_debt_fcf": "net debt / FCF",
    "maturities": "maturities / liquidity",
    "rate_trend": "rate trend (3y)",
    "altman_z": "Altman Z''",
    "piotroski": "Piotroski F",
}

_MAT = "LongTermDebtMaturitiesRepaymentsOfPrincipalIn"
MATURITY_TAGS = (_MAT + "NextTwelveMonths", _MAT + "YearTwo", _MAT + "YearThree")
MATURITY_LABELS = dict(
    zip(MATURITY_TAGS, ("debt due in 1y", "debt due in 2y", "debt due in 3y"), strict=True)
)
# Only annual reports DECIDE the fiscal year ends (a 10-Q can carry a 12-month flow that is not a
# fiscal year). Any filing may SUPPLY a value for those exact periods: SEC lists some fiscal-year
# figures only under a later filing that repeats them (proxy, 10-Q prior-year column).
ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})
DEBT_TOTAL = ("LongTermDebt",)
CASH = ("CashAndCashEquivalentsAtCarryingValue",)
SHORT_INVESTMENTS = ("ShortTermInvestments", "MarketableSecuritiesCurrent")
# Run 5 amendment (2026-10-05): InterestExpenseNonoperating appended; the debt fallbacks and the
# untagged no-debt rule below. Paid-cash and "costs incurred" tags are different concepts: not used.
DEBT_INCL_CURRENT = ("LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",)
DEBT_NONCURRENT_ALT = ("LongTermDebtAndCapitalLeaseObligations",)
DEBT_CURRENT_ALT = (
    "LongTermDebtAndCapitalLeaseObligationsCurrent",
    "LongTermDebtCurrent",
    "DebtCurrent",
)
DEBT_COMBINED = ("DebtLongtermAndShorttermCombinedAmount",)
# Fallback (d), convertible-only filers (added after an audit found DASH/PANW misread as no-debt).
CONVERTIBLE_NONCURRENT = (
    "ConvertibleDebtNoncurrent",
    "ConvertibleLongTermNotesPayable",
    "ConvertibleNotesPayable",
)
CONVERTIBLE_CURRENT = ("ConvertibleDebtCurrent", "ConvertibleNotesPayableCurrent")
# Every debt-family concept: any value at a fiscal year end blocks the untagged no-debt rule.
DEBT_FAMILY = (
    *DEBT_TOTAL,
    "LongTermDebtNoncurrent",
    "ShortTermBorrowings",
    *DEBT_INCL_CURRENT,
    *DEBT_NONCURRENT_ALT,
    *DEBT_CURRENT_ALT,
    *DEBT_COMBINED,
    "DebtInstrumentCarryingAmount",
    "LongTermNotesPayable",
    *CONVERTIBLE_NONCURRENT,
    *CONVERTIBLE_CURRENT,
    "NotesPayable",
    "CommercialPaper",
)
NO_DEBT_NOTE = "no debt tag; treated as no debt"
INTEREST = (
    "InterestExpense",
    "InterestExpenseDebt",
    "InterestAndDebtExpense",
    "InterestExpenseNonoperating",
)
PRETAX = (
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
)
CAPEX = ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets")
OCF = ("NetCashProvidedByUsedInOperatingActivities",)
ANCHORS = (*OCF, "NetIncomeLoss", "OperatingIncomeLoss")

# Balance-sheet items: a point in time at the fiscal year end.
INSTANT_CONCEPTS = frozenset(
    {
        *DEBT_TOTAL,
        *DEBT_FAMILY,
        *CASH,
        *SHORT_INVESTMENTS,
        *MATURITY_TAGS,
        "AssetsCurrent",
        "LiabilitiesCurrent",
        "Assets",
        "Liabilities",
        "RetainedEarningsAccumulatedDeficit",
        "StockholdersEquity",
    }
)

FRAGILITY_CONCEPTS: dict[str, Iterable[str]] = {
    "us-gaap": tuple(
        dict.fromkeys(
            [
                *INSTANT_CONCEPTS,
                *INTEREST,
                *PRETAX,
                *CAPEX,
                *ANCHORS,
                *fd.REVENUE_CONCEPTS,
                *pit_universe.COST_CONCEPTS,
                "GrossProfit",
                "WeightedAverageNumberOfSharesOutstandingBasic",
            ]
        )
    )
}


# --------------------------------------------------------------------------- config


@dataclass(frozen=True)
class FragilityConfig:
    version: int
    date: str
    decided_by: str
    breach_to_fragile: int
    min_available_for_sound: int
    interest_coverage_min: float
    net_debt_to_fcf_max: float
    maturities_to_liquidity_max: float
    altman_z_min: float
    piotroski_max_weak: float
    rate_rise_max_pp: float
    rate_trend_min_net_debt_to_assets: float
    not_applicable_sic: tuple[tuple[int, int], ...]
    not_applicable_tickers: tuple[str, ...]


_THRESHOLDS = (
    "interest_coverage_min",
    "net_debt_to_fcf_max",
    "maturities_to_liquidity_max",
    "altman_z_min",
    "piotroski_max_weak",
    "rate_rise_max_pp",
    "rate_trend_min_net_debt_to_assets",
)
_COUNTS = ("breach_to_fragile", "min_available_for_sound")
_CONFIG_KEYS = frozenset(
    {
        "version",
        "date",
        "decided_by",
        *_THRESHOLDS,
        *_COUNTS,
        "not_applicable_sic",
        "not_applicable_tickers",
    }
)


def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _positive(raw: Mapping, key: str) -> float:
    val = raw[key]
    if isinstance(val, bool) or not isinstance(val, int | float) or not val > 0:
        raise ValueError(f"fragility config: {key} must be a number > 0, got {val!r}")
    return float(val)


def _count(raw: Mapping, key: str) -> int:
    val = raw[key]
    if not _is_int(val) or not 1 <= val <= 6:
        raise ValueError(f"fragility config: {key} must be an integer in 1..6, got {val!r}")
    return int(val)


def _sic_ranges(val: object) -> tuple[tuple[int, int], ...]:
    if not isinstance(val, list):
        raise ValueError("fragility config: not_applicable_sic must be a list of [low, high]")
    out = []
    for item in val:
        ok = isinstance(item, list) and len(item) == 2 and all(_is_int(x) for x in item)
        if not ok or item[0] > item[1]:
            raise ValueError(f"fragility config: malformed or inverted SIC range {item!r}")
        out.append((int(item[0]), int(item[1])))
    return tuple(out)


def _override_tickers(val: object) -> tuple[str, ...]:
    if not isinstance(val, list) or not all(isinstance(t, str) for t in val):
        raise ValueError("fragility config: not_applicable_tickers must be a list of strings")
    norm = [fd.normalize_ticker(t) for t in val]
    dupes = [t for t, n in Counter(norm).items() if n > 1]
    if dupes:
        raise ValueError(f"fragility config: duplicate not_applicable_tickers {dupes}")
    return tuple(norm)


def load_fragility_config(
    path: str | Path = FRAGILITY_CONFIG_PATH,
) -> tuple[FragilityConfig, str]:
    """(config, sha256 of the file). Raises ValueError on any malformed or missing value."""
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("fragility config must be a mapping")
    missing = sorted(_CONFIG_KEYS - set(raw))
    if missing:
        raise ValueError(f"fragility config: missing keys {missing}")
    unknown = sorted(set(raw) - _CONFIG_KEYS)
    if unknown:
        raise ValueError(f"fragility config: unknown keys {unknown}")
    if raw["version"] != 1 or isinstance(raw["version"], bool):
        raise ValueError(f"fragility config: unsupported version {raw['version']!r}")
    for key in ("date", "decided_by"):
        if not isinstance(raw[key], str) or not raw[key]:
            raise ValueError(f"fragility config: {key} must be a non-empty string")
    cfg = FragilityConfig(
        version=1,
        date=raw["date"],
        decided_by=raw["decided_by"],
        not_applicable_sic=_sic_ranges(raw["not_applicable_sic"]),
        not_applicable_tickers=_override_tickers(raw["not_applicable_tickers"]),
        breach_to_fragile=_count(raw, "breach_to_fragile"),
        min_available_for_sound=_count(raw, "min_available_for_sound"),
        interest_coverage_min=_positive(raw, "interest_coverage_min"),
        net_debt_to_fcf_max=_positive(raw, "net_debt_to_fcf_max"),
        maturities_to_liquidity_max=_positive(raw, "maturities_to_liquidity_max"),
        altman_z_min=_positive(raw, "altman_z_min"),
        piotroski_max_weak=_positive(raw, "piotroski_max_weak"),
        rate_rise_max_pp=_positive(raw, "rate_rise_max_pp"),
        rate_trend_min_net_debt_to_assets=_positive(raw, "rate_trend_min_net_debt_to_assets"),
    )
    return cfg, pit_universe.file_sha256(Path(path))


# --------------------------------------------------------------------------- facts view


class _View:
    """One company's facts as known at `date`: end -> value per concept, latest filing per end."""

    def __init__(self, facts: pd.DataFrame, ticker: str, date: pd.Timestamp) -> None:
        sub = facts[facts["ticker"] == ticker].dropna(subset=["val", "end", "filed"])
        sub = sub[sub["filed"] < date]
        anchors = sub[sub["concept"].isin(ANCHORS) & sub["form"].isin(ANNUAL_FORMS)]
        anchor_ends: set[pd.Timestamp] = set()
        for _, grp in anchors.groupby("concept"):
            anchor_ends |= set(fd.filter_duration(grp, "annual")["end"])
        self._fiscal_ends = sorted(anchor_ends)
        self._by: dict[str, dict[pd.Timestamp, float]] = {}
        self.used: dict[str, float] = {}
        self.untagged_no_debt: set[pd.Timestamp] = set()
        for concept, grp in sub.groupby("concept"):
            kind = "instant" if concept in INSTANT_CONCEPTS else "annual"
            grp = fd.filter_duration(grp, kind)
            # annual-report values win; other forms only fill gaps; latest filed wins within each
            grp = grp.assign(_annual=grp["form"].isin(ANNUAL_FORMS)).sort_values(
                ["_annual", "filed"], kind="stable"
            )
            self._by[str(concept)] = {
                end: float(val) for end, val in zip(grp["end"], grp["val"], strict=True)
            }

    def get(self, concepts: Iterable[str], end: pd.Timestamp | None) -> float | None:
        """Value at exactly `end` of the first concept that has one (priority order)."""
        if end is None:
            return None
        for concept in concepts:
            val = self._by.get(concept, {}).get(end)
            if val is not None:
                self.used[f"{concept}@{end:%Y-%m-%d}"] = val
                return val
        return None

    def any_value(self, concepts: Iterable[str], end: pd.Timestamp) -> bool:
        return any(end in self._by.get(c, {}) for c in concepts)

    def any_positive(self, concepts: Iterable[str], end: pd.Timestamp) -> bool:
        return any(self._by.get(c, {}).get(end, 0.0) > 0 for c in concepts)

    def fiscal_ends(self) -> list[pd.Timestamp]:
        return list(self._fiscal_ends)


def _prior_end(ends: Sequence[pd.Timestamp], end: pd.Timestamp | None) -> pd.Timestamp | None:
    """The fiscal year end about one year before `end` (within the lag tolerance)."""
    if end is None:
        return None
    target = end - pd.DateOffset(years=1)
    tol = pd.Timedelta(days=LAG_TOLERANCE_DAYS)
    near = sorted((abs(e - target), e) for e in ends if e < end and abs(e - target) <= tol)
    return near[0][1] if near else None


def _chain(view: _View, date: pd.Timestamp) -> list[pd.Timestamp | None]:
    """[E, E-1y, ..., E-4y] fiscal year ends; [] when none known or the latest is stale."""
    ends = view.fiscal_ends()
    if not ends or (date - ends[-1]).days > fd.STALENESS_DAYS:
        return []
    chain: list[pd.Timestamp | None] = [ends[-1]]
    for _ in range(4):
        chain.append(_prior_end(ends, chain[-1]))
    return chain


# --------------------------------------------------------------------------- measures


@dataclass(frozen=True)
class Measure:
    status: str  # "ok" | "breach" | "n/a"
    display: str
    value: float | None = None
    detail: str = ""


_NO_DEBT = Measure("ok", "no debt")


def _na(reason: str) -> Measure:
    return Measure("n/a", f"n/a ({reason})")


def _need(items: Mapping[str, float | None]) -> tuple[dict[str, float], str]:
    """(the inputs that are present, comma-joined names of those missing)."""
    got = {k: x for k, x in items.items() if x is not None}
    return got, ", ".join(k for k, x in items.items() if x is None)


def _fmt_vs(value: float, threshold: float, dp: int) -> tuple[str, str]:
    """Value and threshold text at one precision: more decimals (to 4) while they look equal,
    and no negative zero."""
    while dp < 4 and f"{value:.{dp}f}" == f"{threshold:.{dp}f}":
        dp += 1
    vtext = f"{value:.{dp}f}"
    while dp < 4 and vtext.startswith("-") and float(vtext) == 0:
        dp += 1
        vtext = f"{value:.{dp}f}"
    if vtext.startswith("-") and float(vtext) == 0:
        vtext = vtext[1:]
    return vtext, f"{threshold:.{dp}f}"


def _debt_primary(v: _View, e: pd.Timestamp) -> float | None:
    total = v.get(DEBT_TOTAL, e)
    if total is None:
        noncurrent = v.get(("LongTermDebtNoncurrent",), e)
        current = v.get(("LongTermDebtCurrent",), e)
        if noncurrent is None or current is None:
            return None
        total = noncurrent + current
    return total + (v.get(("ShortTermBorrowings",), e) or 0.0)


def _debt_fallback(v: _View, e: pd.Timestamp) -> float | None:
    """Run 5 fallbacks, tried after the primary chain: total incl. current maturities; else
    noncurrent + one current part; else the combined short + long total. DebtCurrent already
    includes short-term borrowings, so those are added only with the other current parts."""
    short = v.get(("ShortTermBorrowings",), e) or 0.0
    total = v.get(DEBT_INCL_CURRENT, e)
    if total is not None:
        return total + short
    noncurrent = v.get(DEBT_NONCURRENT_ALT, e)
    if noncurrent is not None:
        for tag in DEBT_CURRENT_ALT:
            current = v.get((tag,), e)
            if current is not None:
                return noncurrent + current + (0.0 if tag == "DebtCurrent" else short)
    combined = v.get(DEBT_COMBINED, e)
    if combined is not None:
        return combined
    return _debt_convertible(v, e, short)


def _debt_convertible(v: _View, e: pd.Timestamp, short: float) -> float | None:
    """Fallback (d): convertible-only filers; the noncurrent convertible is required."""
    noncurrent = v.get(CONVERTIBLE_NONCURRENT, e)
    if noncurrent is None:
        return None
    return noncurrent + (v.get(CONVERTIBLE_CURRENT, e) or 0.0) + short


def _untagged_no_debt(v: _View, e: pd.Timestamp) -> bool:
    """Rule 3: a real balance sheet, no debt-family value, and no positive interest expense."""
    return (
        not v.any_value(DEBT_FAMILY, e)
        and v.any_value(("Assets",), e)
        and v.any_value(("Liabilities",), e)
        and not v.any_positive(INTEREST, e)
    )


def _debt(v: _View, e: pd.Timestamp | None) -> float | None:
    if e is None:
        return None
    debt = _debt_primary(v, e)
    if debt is None:
        debt = _debt_fallback(v, e)
    if debt is None and _untagged_no_debt(v, e):
        v.untagged_no_debt.add(e)
        return 0.0
    return debt


def _cash(v: _View, e: pd.Timestamp | None) -> float | None:
    cash = v.get(CASH, e)
    if cash is None:
        return None
    return cash + (v.get(SHORT_INVESTMENTS, e) or 0.0)


def _ebit(v: _View, e: pd.Timestamp | None) -> float | None:
    ebit = v.get(("OperatingIncomeLoss",), e)
    if ebit is not None:
        return ebit
    pretax = v.get(PRETAX, e)
    interest = v.get(INTEREST, e)
    return None if pretax is None or interest is None else pretax + interest


def _fcf(v: _View, e: pd.Timestamp | None) -> float | None:
    ocf = v.get(OCF, e)
    capex = v.get(CAPEX, e)
    return None if ocf is None or capex is None else ocf - capex


def _measure_coverage(v: _View, ends: list, cfg: FragilityConfig) -> Measure:
    e = ends[0]
    if _debt(v, e) == 0:
        return _NO_DEBT
    got, miss = _need({"EBIT": _ebit(v, e), "interest expense": v.get(INTEREST, e)})
    if miss:
        return _na(f"missing {miss}")
    if got["interest expense"] <= 0:
        return _na("interest expense <= 0")
    cov = got["EBIT"] / got["interest expense"]
    val, thr = _fmt_vs(cov, cfg.interest_coverage_min, 1)
    text = f"{val}x"
    if cov < cfg.interest_coverage_min:
        detail = f"coverage {text} < {thr}x"
        return Measure("breach", text, cov, detail)
    return Measure("ok", text, cov)


def _measure_net_debt(v: _View, ends: list, cfg: FragilityConfig) -> Measure:
    e = ends[0]
    if _debt(v, e) == 0:
        return _NO_DEBT
    got, miss = _need({"debt": _debt(v, e), "cash": _cash(v, e), "FCF": _fcf(v, e)})
    if miss:
        return _na(f"missing {miss}")
    net, fcf = got["debt"] - got["cash"], got["FCF"]
    if net <= 0:
        return Measure("ok", "net cash", 0.0)
    if fcf <= 0:
        return Measure("breach", "FCF <= 0", None, "net debt / FCF: FCF <= 0 with net debt > 0")
    ratio = net / fcf
    val, thr = _fmt_vs(ratio, cfg.net_debt_to_fcf_max, 1)
    text = f"{val}x"
    if ratio > cfg.net_debt_to_fcf_max:
        detail = f"net debt / FCF {text} > {thr}x"
        return Measure("breach", text, ratio, detail)
    return Measure("ok", text, ratio)


def _measure_maturities(v: _View, ends: list, cfg: FragilityConfig) -> Measure:
    e = ends[0]
    due = {label: v.get((tag,), e) for tag, label in MATURITY_LABELS.items()}
    got, miss = _need({**due, "cash": _cash(v, e), "FCF": _fcf(v, e)})
    if miss:
        return _na(f"missing {miss}")
    total = sum(got[label] for label in MATURITY_LABELS.values())
    if total <= 0:
        return Measure("ok", "0.0x", 0.0)
    liquidity = got["cash"] + got["FCF"]
    if liquidity <= 0:
        return Measure(
            "breach", "no liquidity", None, "maturities due with no liquidity (cash + FCF <= 0)"
        )
    ratio = total / liquidity
    val, thr = _fmt_vs(ratio, cfg.maturities_to_liquidity_max, 1)
    text = f"{val}x"
    if ratio > cfg.maturities_to_liquidity_max:
        detail = f"maturities {text} > {thr}x of liquidity"
        return Measure("breach", text, ratio, detail)
    return Measure("ok", text, ratio)


def _little_net_debt(v: _View, e: pd.Timestamp | None, cfg: FragilityConfig) -> Measure | None:
    """An ok measure when net debt is at most the configured share of assets (net cash
    included), else None: also None when debt, cash or assets is missing (no imputation)."""
    debt, cash, assets = _debt(v, e), _cash(v, e), v.get(("Assets",), e)
    if debt is None or cash is None or assets is None or assets <= 0:
        return None
    share = (debt - cash) / assets
    if share > cfg.rate_trend_min_net_debt_to_assets:
        return None
    return Measure("ok", f"little net debt: {share * 100:.1f}% of assets", share)


def _measure_rate_trend(v: _View, ends: list, cfg: FragilityConfig) -> Measure:
    e0, e1, e3, e4 = ends[0], ends[1], ends[3], ends[4]
    if _debt(v, e0) == 0:
        return _NO_DEBT
    little = _little_net_debt(v, e0, cfg)
    if little is not None:
        return little
    if None in (e1, e3, e4):
        return _na("missing fiscal years")
    got, miss = _need(
        {
            "debt (latest)": _debt(v, e0),
            "debt (1y back)": _debt(v, e1),
            "debt (3y back)": _debt(v, e3),
            "debt (4y back)": _debt(v, e4),
            "interest (latest)": v.get(INTEREST, e0),
            "interest (3y back)": v.get(INTEREST, e3),
        }
    )
    if miss:
        return _na(f"missing {miss}")
    now_debt = (got["debt (latest)"] + got["debt (1y back)"]) / 2
    then_debt = (got["debt (3y back)"] + got["debt (4y back)"]) / 2
    if now_debt <= 0 or then_debt <= 0:
        return _na("average debt <= 0")
    change = (got["interest (latest)"] / now_debt - got["interest (3y back)"] / then_debt) * 100
    val, thr = _fmt_vs(change, cfg.rate_rise_max_pp, 1)
    text = f"{'' if val.startswith('-') else '+'}{val} pp"
    if change > cfg.rate_rise_max_pp:
        detail = f"rate {text} > {thr} pp in 3y"
        return Measure("breach", text, change, detail)
    return Measure("ok", text, change)


def _measure_altman(v: _View, ends: list, cfg: FragilityConfig) -> Measure:
    e = ends[0]
    assets = v.get(("Assets",), e)
    equity = v.get(("StockholdersEquity",), e)
    liabilities = v.get(("Liabilities",), e)
    if liabilities is None and assets is not None and equity is not None:
        liabilities = assets - equity
    p, miss = _need(
        {
            "current assets": v.get(("AssetsCurrent",), e),
            "current liabilities": v.get(("LiabilitiesCurrent",), e),
            "assets": assets,
            "retained earnings": v.get(("RetainedEarningsAccumulatedDeficit",), e),
            "equity": equity,
            "liabilities": liabilities,
            "EBIT": _ebit(v, e),
        }
    )
    if miss:
        return _na(f"missing {miss}")
    a, li = p["assets"], p["liabilities"]
    if a <= 0 or li <= 0:
        return _na("assets or liabilities <= 0")
    z = (
        6.56 * (p["current assets"] - p["current liabilities"]) / a
        + 3.26 * p["retained earnings"] / a
        + 6.72 * p["EBIT"] / a
        + 1.05 * p["equity"] / li
        + 3.25
    )
    text, thr = _fmt_vs(z, cfg.altman_z_min, 2)
    if z < cfg.altman_z_min:
        return Measure("breach", text, z, f"Altman Z'' {text} < {thr}")
    return Measure("ok", text, z)


def _pio_year(v: _View, e: pd.Timestamp | None) -> dict[str, float | None]:
    revenue = v.get(fd.REVENUE_CONCEPTS, e)
    gross = v.get(("GrossProfit",), e)
    if gross is None:
        cost = v.get(pit_universe.COST_CONCEPTS, e)
        gross = None if revenue is None or cost is None else revenue - cost
    return {
        "net income": v.get(("NetIncomeLoss",), e),
        "assets": v.get(("Assets",), e),
        "operating cash flow": v.get(OCF, e),
        "debt": _debt(v, e),
        "current assets": v.get(("AssetsCurrent",), e),
        "current liabilities": v.get(("LiabilitiesCurrent",), e),
        "shares": v.get(("WeightedAverageNumberOfSharesOutstandingBasic",), e),
        "gross profit": gross,
        "revenue": revenue,
    }


def _pio_signals(cur: dict[str, float], prev: dict[str, float], assets_before: float) -> list[bool]:
    def roa(y: dict[str, float]) -> float:
        return y["net income"] / y["assets"]

    lev_cur = cur["debt"] / ((cur["assets"] + prev["assets"]) / 2)
    lev_prev = prev["debt"] / ((prev["assets"] + assets_before) / 2)
    return [
        roa(cur) > 0,
        cur["operating cash flow"] > 0,
        roa(cur) > roa(prev),
        cur["operating cash flow"] > cur["net income"],
        lev_cur < lev_prev,
        cur["current assets"] / cur["current liabilities"]
        > prev["current assets"] / prev["current liabilities"],
        cur["shares"] <= prev["shares"],
        cur["gross profit"] / cur["revenue"] > prev["gross profit"] / prev["revenue"],
        cur["revenue"] / cur["assets"] > prev["revenue"] / prev["assets"],
    ]


def _measure_piotroski(v: _View, ends: list, cfg: FragilityConfig) -> Measure:
    if ends[1] is None or ends[2] is None:
        return _na("needs two consecutive fiscal years")
    cur, prev = _pio_year(v, ends[0]), _pio_year(v, ends[1])
    assets_before = v.get(("Assets",), ends[2])
    got, miss = _need(
        {
            **{f"{k} (latest)": x for k, x in cur.items()},
            **{f"{k} (1y back)": x for k, x in prev.items()},
            "assets (2y back)": assets_before,
        }
    )
    if miss:
        return _na(f"missing {miss}")
    try:
        score = sum(
            _pio_signals(
                {k: got[f"{k} (latest)"] for k in cur},
                {k: got[f"{k} (1y back)"] for k in prev},
                got["assets (2y back)"],
            )
        )
    except ZeroDivisionError:
        return _na("zero denominator")
    if score <= cfg.piotroski_max_weak:
        detail = f"Piotroski F {score} <= {cfg.piotroski_max_weak:g}"
        return Measure("breach", str(score), float(score), detail)
    return Measure("ok", str(score), float(score))


_MEASURE_FUNCS: dict[str, Callable[[_View, list, FragilityConfig], Measure]] = {
    "coverage": _measure_coverage,
    "net_debt_fcf": _measure_net_debt,
    "maturities": _measure_maturities,
    "rate_trend": _measure_rate_trend,
    "altman_z": _measure_altman,
    "piotroski": _measure_piotroski,
}


# --------------------------------------------------------------------------- classification


_FCF_PAIR = ("net_debt_fcf", "maturities")


def classify(measures: Mapping[str, Measure], cfg: FragilityConfig) -> str:
    """FRAGILE if breaches >= N; WATCH if 1 <= breaches < N (empty at N = 1); net debt / FCF
    and maturities breached together count as one breach; SOUND if no
    breach and >= K measures available; else INSUFFICIENT DATA. (NOT APPLICABLE is decided
    by industry before any measure is computed.)"""
    breaches = sum(m.status == "breach" for m in measures.values())
    if all(measures.get(k) is not None and measures[k].status == "breach" for k in _FCF_PAIR):
        breaches -= 1  # net debt / FCF and maturities both lean on FCF: one breach
    available = sum(m.status != "n/a" for m in measures.values())
    if breaches >= cfg.breach_to_fragile:
        return FRAGILE
    if breaches >= 1:
        return WATCH
    if available >= cfg.min_available_for_sound:
        return SOUND
    return INSUFFICIENT


@dataclass
class CompanyResult:
    ticker: str
    cls: str
    measures: dict[str, Measure]
    fy_end: pd.Timestamp | None = None
    sic: int | None = None
    note: str = ""
    inputs: dict[str, float] = field(default_factory=dict)

    @property
    def breached(self) -> list[str]:
        return [k for k in MEASURE_KEYS if self.measures[k].status == "breach"]


def _is_financial(ticker: str, sic: int | None, cfg: FragilityConfig) -> bool:
    if fd.normalize_ticker(ticker) in cfg.not_applicable_tickers:
        return True
    return sic is not None and any(lo <= sic <= hi for lo, hi in cfg.not_applicable_sic)


def fragility_as_of(
    ticker: str,
    date: pd.Timestamp | str,
    facts: pd.DataFrame,
    cfg: FragilityConfig,
    sic: int | None = None,
) -> CompanyResult:
    """The screen for one company at `date`, from facts with filed < date only."""
    when = pd.Timestamp(date)
    if _is_financial(ticker, sic, cfg):
        measures = {k: Measure("n/a", NOT_APPLICABLE) for k in MEASURE_KEYS}
        return CompanyResult(ticker, NOT_APPLICABLE, measures, sic=sic, note="financial firm")
    view = _View(facts, ticker, when)
    ends = _chain(view, when)
    if not ends:
        reason = "no fiscal year known (no filing, or stale)"
        measures = {k: _na(reason) for k in MEASURE_KEYS}
        note = reason if sic is not None else f"{reason}; industry unknown"
        return CompanyResult(ticker, INSUFFICIENT, measures, sic=sic, note=note)
    measures = {k: _MEASURE_FUNCS[k](view, ends, cfg) for k in MEASURE_KEYS}
    cls, note = classify(measures, cfg), ""
    if ends[0] in view.untagged_no_debt:
        note = NO_DEBT_NOTE
    if sic is None:
        cls, note = INSUFFICIENT, "; ".join(n for n in (note, "industry unknown") if n)
    return CompanyResult(ticker, cls, measures, ends[0], sic, note, dict(view.used))


def members_as_of(
    membership: pd.DataFrame, date: pd.Timestamp | str
) -> tuple[pd.Timestamp | None, list[str]]:
    """(month-end, sorted tickers) of the latest month-end strictly before `date`, the rule of
    `pit_universe.membership_mask`; (None, []) before the first month-end."""
    ends = pd.DatetimeIndex(sorted(membership["month_end"].unique()))
    pos = int(ends.searchsorted(pd.Timestamp(date), side="left")) - 1
    if pos < 0:
        return None, []
    month_end = ends[pos]
    rows = membership[membership["month_end"] == month_end]
    return month_end, sorted(rows["ticker"])


def screen(
    date: pd.Timestamp | str,
    tickers: Sequence[str],
    facts: pd.DataFrame,
    sics: Mapping[str, int | None],
    cfg: FragilityConfig,
) -> list[CompanyResult]:
    return [fragility_as_of(t, date, facts, cfg, sic=sics.get(t)) for t in tickers]


def excluded_tickers(
    date: pd.Timestamp | str,
    membership: pd.DataFrame,
    facts: pd.DataFrame,
    cfg: FragilityConfig,
    sics: Mapping[str, int | None],
) -> set[str]:
    """FRAGILE tickers among the members of the latest month-end strictly before `date`.
    Not wired into any run, strategy or config (spec: Point-in-time filter)."""
    _, tickers = members_as_of(membership, date)
    return {r.ticker for r in screen(date, tickers, facts, sics, cfg) if r.cls == FRAGILE}


# --------------------------------------------------------------------------- loaders


def load_pool_ciks(pool_path: Path | None = None) -> dict[str, int]:
    pool = pd.read_csv(pool_path or pit_universe.PIT_CACHE_DIR / "pool.csv")
    return dict(zip(pool["ticker"], pool["cik"].astype(int), strict=True))


def load_fragility_facts(
    tickers: Sequence[str],
    pool_path: Path | None = None,
    sec_dir: Path | None = None,
) -> pd.DataFrame:
    """Like `factor_data.load_factor_facts` but parsing `FRAGILITY_CONCEPTS`: local cache only,
    ticker -> CIK from `pool.csv`, plus `CIK_PREDECESSORS` histories."""
    ciks = load_pool_ciks(pool_path)
    sec = sec_dir or fd.SEC_CACHE_DIR
    frames = []
    for t in tickers:
        payload = factor_data._read_cached_payload(ciks[t], sec) if t in ciks else None
        if payload is None:
            continue
        facts = fd.parse_companyfacts(t, payload, FRAGILITY_CONCEPTS)
        for old_cik in pit_universe.CIK_PREDECESSORS.get(t, []):
            old = factor_data._read_cached_payload(old_cik, sec)
            if old is not None:
                old_facts = fd.parse_companyfacts(t, old, FRAGILITY_CONCEPTS)
                facts = pit_universe.merge_predecessor_facts(facts, old_facts)
        frames.append(facts)
    if not frames:
        return pd.DataFrame(columns=fd.FACT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def make_fetcher(config_path: Path = fd.SEC_CONFIG_PATH) -> Callable[[str], bytes]:
    """Fetcher with the SEC User-Agent; `fd._http_get` enforces the host allowlist."""
    ua = fd.sec_user_agent(config_path)
    return lambda url: fd._http_get(url, ua)


def refresh_facts(
    tickers: Sequence[str],
    pool_path: Path | None,
    sec_dir: Path,
    fetch: Callable[[str], bytes],
) -> int:
    """Re-download companyfacts (and predecessor CIKs) for `tickers`; returns files fetched."""
    ciks = load_pool_ciks(pool_path)
    wanted: set[int] = set()
    for t in tickers:
        if t in ciks:
            wanted |= {ciks[t], *pit_universe.CIK_PREDECESSORS.get(t, [])}
    for cik in sorted(wanted):
        path = sec_dir / "facts" / f"CIK{cik:010d}.json"
        fd._cached_json(path, fd.FACTS_URL.format(cik=cik), True, fetch)
    return len(wanted)


def load_sic(cik: int, sec_dir: Path, fetch: Callable[[str], bytes] | None = None) -> int | None:
    """SIC from the cached submissions JSON; downloaded only when `fetch` is given.
    None when unknown (no cache and no fetch, 404, or blank)."""
    path = sec_dir / "submissions" / f"CIK{cik:010d}.json"
    if fetch is None:
        payload: dict | None = json.loads(path.read_text()) if path.exists() else None
    else:
        payload = fd._cached_json(path, SUBMISSIONS_URL.format(cik=cik), False, fetch)
    try:
        return int(str((payload or {}).get("sic")))
    except ValueError:
        return None


# --------------------------------------------------------------------------- report


def _company_row(r: CompanyResult) -> dict[str, Any]:
    return {
        "ticker": r.ticker,
        "class": r.cls,
        "fy_end": None if r.fy_end is None else f"{r.fy_end:%Y-%m-%d}",
        "sic": r.sic,
        "note": r.note,
        "breached": r.breached,
        "measures": {
            k: {"status": m.status, "display": m.display, "value": m.value, "detail": m.detail}
            for k, m in r.measures.items()
        },
        "inputs": dict(sorted(r.inputs.items())),
    }


def build_report(
    results: Sequence[CompanyResult],
    *,
    as_of: pd.Timestamp,
    month_end: pd.Timestamp | None,
    facts: pd.DataFrame,
    cfg: FragilityConfig,
    config_sha256: str,
    universe_sha256: str,
) -> dict[str, Any]:
    """Deterministic report dict (sorted by class, then ticker); the markdown renders from it."""
    seen = facts.loc[facts["filed"] < as_of, "filed"] if len(facts) else pd.Series(dtype="object")
    newest = seen.max() if len(seen) else None
    rows = sorted(
        (_company_row(r) for r in results),
        key=lambda c: (CLASS_ORDER.index(c["class"]), c["ticker"]),
    )
    counts = Counter(c["class"] for c in rows)
    return {
        "as_of": f"{as_of:%Y-%m-%d}",
        "month_end": None if month_end is None else f"{month_end:%Y-%m-%d}",
        "universe_size": len(rows),
        "newest_filing": None if newest is None or pd.isna(newest) else f"{newest:%Y-%m-%d}",
        "config_sha256": config_sha256,
        "universe_sha256": universe_sha256,
        "breach_to_fragile": cfg.breach_to_fragile,
        "min_available_for_sound": cfg.min_available_for_sound,
        "thresholds": {k: getattr(cfg, k) for k in _THRESHOLDS},
        "summary": {c: counts.get(c, 0) for c in CLASS_ORDER},
        "companies": rows,
    }


def _cell(text: object) -> str:
    return str(text).replace("|", "/")


def _table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return out


def render_markdown(report: Mapping[str, Any]) -> str:
    """research/fragility.md: header bullets, Summary, Fragile and watch, All companies."""
    companies = report["companies"]
    th = report["thresholds"]
    lines = [
        "# Balance-sheet fragility screen (exploration only)",
        "",
        "> Not a return signal and not a recommendation. Latest fiscal-year filings only;"
        " banks, insurers, brokers and property trusts are not applicable.",
        "",
        f"- as-of date: {report['as_of']}",
        f"- membership month-end: {report['month_end'] or 'none'}",
        f"- universe size: {report['universe_size']}",
        f"- newest filing date seen: {report['newest_filing'] or 'none'}",
        f"- config/fragility.yaml sha256: `{report['config_sha256']}`",
        f"- universe membership sha256: `{report['universe_sha256']}`",
        f"- breach_to_fragile (N): {report['breach_to_fragile']}",
        f"- min_available_for_sound (K): {report['min_available_for_sound']}",
        "- thresholds: " + ", ".join(f"{k} {v:g}" for k, v in th.items()),
        "",
        "## Summary",
        "",
        *_table(["class", "count"], report["summary"].items()),
        "",
        "## Fragile and watch",
        "",
    ]
    flagged = [c for c in companies if c["class"] in (FRAGILE, WATCH)]
    lines += _table(
        ["ticker", "class", "breached measures", "fiscal year end"],
        (
            (
                c["ticker"],
                c["class"],
                "; ".join(c["measures"][k]["detail"] or k for k in c["breached"]),
                c["fy_end"] or "n/a",
            )
            for c in flagged
        ),
    )
    lines += ["", "## All companies", ""]
    lines += _table(
        ["ticker", "class", "fiscal year end", *(MEASURE_LABELS[k] for k in MEASURE_KEYS), "note"],
        (
            (
                c["ticker"],
                c["class"],
                c["fy_end"] or "n/a",
                *(c["measures"][k]["display"] for k in MEASURE_KEYS),
                c["note"],
            )
            for c in companies
        ),
    )
    return "\n".join(lines) + "\n"
