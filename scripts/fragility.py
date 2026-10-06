"""Balance-sheet fragility screen, EXPLORATION ONLY (spec:
docs/methodology/fragility-screen.md). Screens every member of the
point-in-time universe's latest month-end before --as-of with the pre-registered
config/fragility.yaml, from the local SEC cache. Writes research/fragility.md (committed)
and reports/fragility.json (gitignored). No price data, no returns, no config changes.

It never touches the network unless asked: --refresh-facts re-downloads companyfacts for
the universe members, --fetch-sic downloads the missing SIC codes (both via the
qrl.fundamentals HTTP helpers: host allowlist, SEC User-Agent, throttling).

Usage:
    python scripts/fragility.py
    python scripts/fragility.py --as-of 2026-10-05 --fetch-sic --refresh-facts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qrl import fragility as fr  # noqa: E402
from qrl import fundamentals as fd  # noqa: E402
from qrl import pit_universe as pu  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--fetch-sic", action="store_true", help="download missing SIC codes")
    ap.add_argument("--refresh-facts", action="store_true", help="re-download companyfacts")
    ap.add_argument("--out-md", default=str(ROOT / "research" / "fragility.md"))
    ap.add_argument("--out-json", default=str(ROOT / "reports" / "fragility.json"))
    ap.add_argument("--sec-dir", default=str(fd.SEC_CACHE_DIR), help="SEC cache directory")
    ap.add_argument("--pool", default=str(pu.PIT_CACHE_DIR / "pool.csv"), help="ticker -> CIK map")
    ap.add_argument("--universe", default=str(pu.UNIVERSE_PIT_PATH), help="PIT universe yaml")
    ap.add_argument("--config", default=str(fr.FRAGILITY_CONFIG_PATH))
    args = ap.parse_args(argv)

    as_of = pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp.today().normalize()
    sec_dir, pool = Path(args.sec_dir), Path(args.pool)
    cfg, config_sha = fr.load_fragility_config(args.config)
    meta, membership = pu.load_pit_universe(args.universe)
    month_end, members = fr.members_as_of(membership, as_of)

    fetch = fr.make_fetcher() if (args.refresh_facts or args.fetch_sic) else None
    if args.refresh_facts and fetch is not None:
        n = fr.refresh_facts(members, pool, sec_dir, fetch)
        print(f"re-fetched companyfacts for {n} CIKs")
    facts = fr.load_fragility_facts(members, pool_path=pool, sec_dir=sec_dir)

    ciks = fr.load_pool_ciks(pool)
    sic_fetch = fetch if args.fetch_sic else None
    sics = {t: fr.load_sic(ciks[t], sec_dir, sic_fetch) for t in members if t in ciks}

    results = fr.screen(as_of, members, facts, sics, cfg)
    report = fr.build_report(
        results,
        as_of=as_of,
        month_end=month_end,
        facts=facts,
        cfg=cfg,
        config_sha256=config_sha,
        universe_sha256=str(meta.get("membership_sha256", "")),
    )
    out_md, out_json = Path(args.out_md), Path(args.out_json)
    for out in (out_md, out_json):
        out.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(fr.render_markdown(report))
    out_json.write_text(json.dumps(report, indent=1, default=str) + "\n")

    print(f"as of {report['as_of']}, month-end {report['month_end']}, {len(members)} members")
    for cls, count in report["summary"].items():
        print(f"  {cls:<18} {count}")
    print(f"wrote {out_md} and {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
