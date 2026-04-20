"""
scripts/test_critical_sites.py
-------------------------------
Tests the 3 most important tender sources:
  1. EasyTenders (all provinces)
  2. eTenders Portal (national)
  3. SA-Tenders.co.za

Run:
    cd backend
    python scripts/test_critical_sites.py
    python scripts/test_critical_sites.py --site easytenders
    python scripts/test_critical_sites.py --site etenders
    python scripts/test_critical_sites.py --site satenders
"""

import asyncio
import sys
import os
import argparse
import json
from collections import Counter

_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def print_results(name: str, tenders: list):
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")

    if not tenders:
        print("  ❌  No tenders returned")
        return

    print(f"  ✅  {len(tenders)} tenders extracted\n")

    # Province breakdown
    provinces = Counter(t.get("province") or "Unknown" for t in tenders)
    print("  Province breakdown:")
    for p, c in provinces.most_common():
        bar = "█" * c
        print(f"    {(p or 'Unknown'):<25} {c:>4}  {bar}")

    # Industry breakdown
    industries = Counter(t.get("industry_category") or "General" for t in tenders)
    print("\n  Industry breakdown:")
    for ind, c in industries.most_common(8):
        print(f"    {ind:<40} {c:>4}")

    # Sample tenders
    print(f"\n  Sample tenders (first 10):")
    print(f"  {'Title':<55} {'Province':<18} {'Closing':<12} Doc?")
    print("  " + "-" * 95)
    for t in tenders[:10]:
        title   = (t.get("title") or "")[:53]
        prov    = (t.get("province") or "Unknown")[:16]
        closing = (t.get("closing_date") or "")[:12]
        doc     = "✓" if t.get("document_url") else "-"
        print(f"  {title:<55} {prov:<18} {closing:<12} {doc}")

    if len(tenders) > 10:
        print(f"  ... and {len(tenders) - 10} more")

    # Save to JSON
    out = os.path.join(_BACKEND_DIR, f"{name.lower().replace(' ','_')}_output.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(tenders, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Saved to: {out}")


async def test_easytenders():
    print("\n🔍 Testing EasyTenders (all 9 provinces)...")
    from scraper.sites.js_scraper import scrape_js_source, JS_SOURCES
    tenders = await scrape_js_source(JS_SOURCES[0])
    print_results("EasyTenders — All Provinces", tenders)
    return tenders


async def test_etenders():
    print("\n🔍 Testing eTenders Portal (National)...")
    from scraper.sites.etenders import scrape_etenders
    tenders = await scrape_etenders()
    print_results("eTenders Portal (National)", tenders)
    return tenders


async def test_satenders():
    print("\n🔍 Testing SA-Tenders.co.za...")
    from scraper.sites.sa_tenders import scrape_sa_tenders
    tenders = await scrape_sa_tenders()
    print_results("SA-Tenders.co.za", tenders)
    return tenders


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=["easytenders", "etenders", "satenders"],
                        help="Test a specific site only")
    args = parser.parse_args()

    total = 0
    if not args.site or args.site == "easytenders":
        t = await test_easytenders()
        total += len(t)

    if not args.site or args.site == "etenders":
        t = await test_etenders()
        total += len(t)

    if not args.site or args.site == "satenders":
        t = await test_satenders()
        total += len(t)

    print(f"\n{'='*70}")
    print(f"  TOTAL from all 3 critical sites: {total} tenders")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())