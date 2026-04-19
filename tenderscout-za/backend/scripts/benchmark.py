"""
scripts/benchmark.py
---------------------
Runs the actual scrapers (not just HTTP checks) against every active HTML site
and reports: tender count, time taken, and any errors.

    cd backend
    python scripts/benchmark.py

This tells you exactly how many tenders the scraper extracts (not just link counts)
and how long the full cycle takes.
"""

import asyncio
import sys
import os
import time
from collections import defaultdict

_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import httpx
import logging
logging.basicConfig(level=logging.WARNING)  # suppress scraper noise during benchmark

from scraper.utils import get_headers
from scraper.sites.registry import get_html_sources
from scraper.sites.city_portals import scrape_city


async def benchmark_site(client: httpx.AsyncClient, source: dict) -> dict:
    name = source["name"]
    t0   = time.perf_counter()
    error = None
    tenders = []

    try:
        tenders = await scrape_city(client, source)
    except Exception as e:
        error = str(e)[:100]

    elapsed = time.perf_counter() - t0

    # Industry breakdown
    industry_counts = defaultdict(int)
    for t in tenders:
        industry_counts[t.get("industry_category") or "General"] += 1

    return {
        "name":       name,
        "province":   source.get("province") or "National",
        "scrape_type": source.get("scrape_type"),
        "count":      len(tenders),
        "elapsed":    elapsed,
        "error":      error,
        "industries": dict(industry_counts),
        "sample":     [t["title"][:70] for t in tenders[:3]],
    }


async def main():
    sources      = get_html_sources()
    total_start  = time.perf_counter()

    print("\n" + "=" * 80)
    print("  TENDERSCOUT ZA — Full Scraper Benchmark")
    print(f"  {len(sources)} HTML sources")
    print("=" * 80)

    # Run all concurrently with semaphore to avoid overloading
    sem = asyncio.Semaphore(6)

    async with httpx.AsyncClient(
        headers=get_headers(),
        follow_redirects=True,
        verify=False,
        timeout=30,
    ) as client:

        async def bounded(source):
            async with sem:
                return await benchmark_site(client, source)

        results = await asyncio.gather(*[bounded(s) for s in sources])

    total_elapsed = time.perf_counter() - total_start

    # Sort by province then count
    results = sorted(results, key=lambda r: (r["province"], -r["count"]))

    # ── Print results ─────────────────────────────────────────────────────────
    current_province = None
    total_tenders    = 0
    failed           = 0

    print(f"\n  {'Site':<42} {'Type':<16} {'Tenders':>8} {'Time':>7}  Status")
    print("  " + "-" * 78)

    for r in results:
        if r["province"] != current_province:
            current_province = r["province"]
            print(f"\n  📍 {current_province}")

        status = f"❌ {r['error'][:35]}" if r["error"] else ("✅" if r["count"] > 0 else "⚠️  0 results")
        time_str = f"{r['elapsed']:.1f}s"
        print(f"     {r['name']:<40} {r['scrape_type']:<16} {r['count']:>8} {time_str:>7}  {status}")

        if r["count"] > 0 and r["sample"]:
            for s in r["sample"]:
                print(f"       → {s}")

        total_tenders += r["count"]
        if r["error"] or r["count"] == 0:
            failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print(f"  Total tenders extracted:  {total_tenders}")
    print(f"  Sites returning tenders:  {len(results) - failed}/{len(results)}")
    print(f"  Total time (concurrent):  {total_elapsed:.1f}s")
    print(f"  Avg per site:             {total_elapsed/len(results):.1f}s")
    print("=" * 80)

    # ── Industry totals ───────────────────────────────────────────────────────
    all_industries = defaultdict(int)
    for r in results:
        for ind, cnt in r["industries"].items():
            all_industries[ind] += cnt

    print(f"\n  INDUSTRY BREAKDOWN ({total_tenders} tenders):")
    for ind, cnt in sorted(all_industries.items(), key=lambda x: -x[1]):
        bar = "█" * min(cnt // 5, 40)
        print(f"    {ind:<40} {cnt:>5}  {bar}")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())