"""
scripts/benchmark.py
---------------------
Runs the actual scrapers (not just HTTP checks) against every active HTML site
and reports: tender count, time taken, and any errors.

Usage:
    cd backend
    python scripts/benchmark.py

This tells you exactly how many tenders the scraper extracts (not just link counts)
and how long the full cycle takes.

Output includes:
- Per‑site results grouped by province, with status (✅ / ❌ / ⚠️) and sample titles.
- Total tenders extracted, number of successful/failed sites, total and average time.
- Industry breakdown with a bar chart.
"""

import asyncio
import sys
import os
import time
from collections import defaultdict

# ------------------------------------------------------------------
# Path setup – ensure the project root is on sys.path so we can
# import the scraper modules.
# ------------------------------------------------------------------
_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))   # scripts/
_BACKEND_DIR = os.path.dirname(_THIS_DIR)                  # backend/
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import httpx
import logging
# Suppress the normally chatty scraper loggers – we only care about the
# benchmark output itself.
logging.basicConfig(level=logging.WARNING)

from scraper.utils import get_headers
from scraper.sites.registry import get_html_sources
from scraper.sites.city_portals import scrape_city


async def benchmark_site(client: httpx.AsyncClient, source: dict) -> dict:
    """
    Scrape a single site and return a dict with performance metrics.

    Args:
        client: shared httpx.AsyncClient (created once with SSL disabled, etc.)
        source: source configuration dict (must contain 'name', 'url', etc.)

    Returns a dict with:
        - name, province, scrape_type (metadata)
        - count: number of tenders extracted
        - elapsed: wall‑clock time in seconds
        - error: error message (or None if successful)
        - industries: dict mapping industry name -> count
        - sample: list of the first 3 tender titles (for quick inspection)
    """
    name = source["name"]
    t0   = time.perf_counter()
    error = None
    tenders = []

    try:
        tenders = await scrape_city(client, source)
    except Exception as e:
        # Truncate error messages to 100 chars to keep the report tidy
        error = str(e)[:100]

    elapsed = time.perf_counter() - t0

    # Build an industry breakdown from the extracted tenders
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
    """
    Benchmark the full set of HTML‑based sources concurrently.

    Steps:
    1. Get all HTML sources via registry.get_html_sources().
    2. Create a shared httpx.AsyncClient with SSL verification disabled
       (municipal sites often have broken certificates).
    3. Run benchmark_site() for each source, limiting concurrency to 6.
    4. Sort results by province and tender count (descending).
    5. Print a formatted table, a summary, and an industry breakdown.
    """
    sources      = get_html_sources()
    total_start  = time.perf_counter()

    print("\n" + "=" * 80)
    print("  TENDERSCOUT ZA — Full Scraper Benchmark")
    print(f"  {len(sources)} HTML sources")
    print("=" * 80)

    # Semaphore controls how many sites are scraped in parallel.
    # Too high may trigger rate‑limiting or exhaust local sockets.
    sem = asyncio.Semaphore(6)

    async with httpx.AsyncClient(
        headers=get_headers(),
        follow_redirects=True,
        verify=False,         # skip certificate validation for speed & reliability
        timeout=30,
    ) as client:

        async def bounded(source):
            """Wrap benchmark_site with the semaphore."""
            async with sem:
                return await benchmark_site(client, source)

        # Run all benchmarks concurrently
        results = await asyncio.gather(*[bounded(s) for s in sources])

    total_elapsed = time.perf_counter() - total_start

    # Sort results: first by province (A‑Z), then by tender count (descending)
    results = sorted(results, key=lambda r: (r["province"], -r["count"]))

    # ── Print per‑site results, grouped by province ───────────────────────
    current_province = None
    total_tenders    = 0
    failed           = 0   # sites with 0 tenders or an error

    print(f"\n  {'Site':<42} {'Type':<16} {'Tenders':>8} {'Time':>7}  Status")
    print("  " + "-" * 78)

    for r in results:
        # Print a province header when the province changes
        if r["province"] != current_province:
            current_province = r["province"]
            print(f"\n  📍 {current_province}")

        # Status icon
        if r["error"]:
            status = f"❌ {r['error'][:35]}"
        elif r["count"] > 0:
            status = "✅"
        else:
            status = "⚠️  0 results"

        time_str = f"{r['elapsed']:.1f}s"
        print(f"     {r['name']:<40} {r['scrape_type']:<16} {r['count']:>8} {time_str:>7}  {status}")

        # Show a few sample tender titles for visual inspection
        if r["count"] > 0 and r["sample"]:
            for s in r["sample"]:
                print(f"       → {s}")

        total_tenders += r["count"]
        if r["error"] or r["count"] == 0:
            failed += 1

    # ── Summary statistics ─────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print(f"  Total tenders extracted:  {total_tenders}")
    print(f"  Sites returning tenders:  {len(results) - failed}/{len(results)}")
    print(f"  Total time (concurrent):  {total_elapsed:.1f}s")
    print(f"  Avg per site:             {total_elapsed/len(results):.1f}s")
    print("=" * 80)

    # ── Industry totals (across all sites) ──────────────────────────────────
    all_industries = defaultdict(int)
    for r in results:
        for ind, cnt in r["industries"].items():
            all_industries[ind] += cnt

    print(f"\n  INDUSTRY BREAKDOWN ({total_tenders} tenders):")
    for ind, cnt in sorted(all_industries.items(), key=lambda x: -x[1]):
        # Simple ASCII bar chart
        bar = "█" * min(cnt // 5, 40)
        print(f"    {ind:<40} {cnt:>5}  {bar}")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())