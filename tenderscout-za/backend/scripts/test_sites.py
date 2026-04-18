"""
scripts/test_sites.py
----------------------
Tests every site in the registry: reachability, tender count, industry detection.

Usage:
    cd backend
    python scripts/test_sites.py                  # test all active sites
    python scripts/test_sites.py --all            # include broken + dead
    python scripts/test_sites.py --site "Sol Plaatje Municipality"
    python scripts/test_sites.py --province "Northern Cape"
    python scripts/test_sites.py --type links     # only test sites with scrape_type=links
"""

import asyncio
import sys
import os
import argparse
import time
from collections import defaultdict

_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import httpx
import logging
logging.basicConfig(level=logging.WARNING)  # quiet during test — we print our own output

from scraper.sites.registry import (
    ACTIVE_SOURCES, BROKEN_SOURCES, DEAD_SOURCES, ALL_SOURCES
)
from scraper.utils import get_headers

INDUSTRY_KEYWORDS = {
    "Security Services":     ["security", "guarding", "cctv", "access control"],
    "Construction":          ["construction", "building", "civil", "roads", "infrastructure"],
    "Waste Management":      ["waste", "refuse", "sanitation", "recycling"],
    "Electrical Services":   ["electrical", "generator", "solar", "metering"],
    "Plumbing":              ["plumbing", "pipes", "water reticulation", "drainage"],
    "ICT / Technology":      ["ict", "software", "network", "hardware", "fiber"],
    "Maintenance":           ["maintenance", "repairs", "renovations", "facilities"],
    "Cleaning Services":     ["cleaning", "hygiene", "janitorial", "pest control"],
    "Catering":              ["catering", "food", "meals", "canteen"],
    "Consulting":            ["consulting", "advisory", "research", "feasibility"],
    "Transport & Logistics": ["transport", "logistics", "fleet", "vehicles"],
    "Healthcare":            ["medical", "healthcare", "pharmaceutical", "clinic"],
    "Landscaping":           ["landscaping", "gardening", "parks", "grass"],
    "Mining Services":       ["mining", "drilling", "blasting", "mineral"],
}

TENDER_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "supply", "contract"]


# ---------------------------------------------------------------------------
# Reachability check
# ---------------------------------------------------------------------------

async def check_reachable(client: httpx.AsyncClient, url: str) -> tuple[bool, int, str]:
    """Returns (reachable, status_code, error_msg)."""
    try:
        r = await client.get(url, timeout=15)
        return r.status_code < 400, r.status_code, ""
    except httpx.TimeoutException:
        return False, 0, "Timeout"
    except httpx.ConnectError as e:
        return False, 0, f"DNS/Connect: {str(e)[:60]}"
    except Exception as e:
        return False, 0, str(e)[:80]


# ---------------------------------------------------------------------------
# Tender detection (non-JS sites only)
# ---------------------------------------------------------------------------

async def count_tenders(client: httpx.AsyncClient, url: str) -> tuple[int, list]:
    """
    Returns (tender_count, industries_found).
    Quick heuristic — counts links/elements that look like tenders.
    """
    try:
        from bs4 import BeautifulSoup
        r = await client.get(url, timeout=20)
        if r.status_code != 200:
            return 0, []

        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text().lower()
        links = soup.select("a[href]")

        # Count tender-related links
        tender_links = [
            a for a in links
            if any(kw in (a.get_text() or "").lower() or kw in (a.get("href") or "").lower()
                   for kw in TENDER_KEYWORDS)
        ]

        # Detect industries from page text
        found_industries = []
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                found_industries.append(industry)

        return len(tender_links), found_industries

    except Exception:
        return 0, []


# ---------------------------------------------------------------------------
# Test a single source
# ---------------------------------------------------------------------------

async def test_source(client: httpx.AsyncClient, source: dict) -> dict:
    name         = source["name"]
    url          = source["url"]
    status       = source.get("status", "unknown")
    scrape_type  = source.get("scrape_type", "links")
    is_playwright = scrape_type in ("js_playwright", "etenders_playwright")

    result = {
        "name":        name,
        "url":         url,
        "province":    source.get("province", ""),
        "status":      status,
        "scrape_type": scrape_type,
        "reachable":   False,
        "http_code":   0,
        "tender_count": 0,
        "industries":  [],
        "error":       "",
        "skip_reason": "",
        "duration_s":  0.0,
    }

    # Dead sites — just do a quick DNS check
    if status == "dead":
        t0 = time.time()
        reachable, code, err = await check_reachable(client, url)
        result.update(reachable=reachable, http_code=code, error=err,
                      duration_s=round(time.time() - t0, 2))
        if reachable:
            result["status"] = "resurrected"  # was dead, now alive!
        return result

    # Playwright sites — only check reachability, don't run full scrape in test
    if is_playwright:
        t0 = time.time()
        reachable, code, err = await check_reachable(client, url)
        result.update(reachable=reachable, http_code=code, error=err,
                      duration_s=round(time.time() - t0, 2),
                      skip_reason="Playwright — run test_etenders.py for full test")
        return result

    # HTML sites — check reachability + count tenders
    t0 = time.time()
    reachable, code, err = await check_reachable(client, url)
    result.update(reachable=reachable, http_code=code, error=err)

    if reachable:
        count, industries = await count_tenders(client, url)
        result.update(tender_count=count, industries=industries)

    result["duration_s"] = round(time.time() - t0, 2)
    return result


# ---------------------------------------------------------------------------
# Print results table
# ---------------------------------------------------------------------------

def _status_icon(r: dict) -> str:
    if r["status"] == "dead" and not r["reachable"]:
        return "💀"
    if r["status"] == "dead" and r["reachable"]:
        return "🔄"   # was dead, now alive
    if not r["reachable"]:
        return "🔴"
    if r["tender_count"] == 0 and not r["skip_reason"]:
        return "🟡"   # reachable but no tenders
    if r["skip_reason"]:
        return "⚡"   # playwright — skipped
    return "✅"


def print_results(results: list, show_industries: bool = True):
    # Group by province
    by_province = defaultdict(list)
    for r in results:
        by_province[r.get("province") or "National/Multi"].append(r)

    total_sites    = len(results)
    total_active   = sum(1 for r in results if r["reachable"] and r["tender_count"] > 0)
    total_tenders  = sum(r["tender_count"] for r in results)
    total_broken   = sum(1 for r in results if r["reachable"] and r["tender_count"] == 0 and not r["skip_reason"])
    total_dead     = sum(1 for r in results if not r["reachable"])
    total_playwright = sum(1 for r in results if r["skip_reason"])

    print("\n" + "=" * 90)
    print("  TENDERSCOUT ZA — Site Registry Test")
    print("=" * 90)

    for province, prov_results in sorted(by_province.items()):
        print(f"\n  📍 {province}")
        print(f"  {'Name':<42} {'Status':<10} {'HTTP':<6} {'Tenders':<9} {'Time':<7} Notes")
        print("  " + "-" * 85)

        for r in prov_results:
            icon    = _status_icon(r)
            name    = r["name"][:40]
            code    = str(r["http_code"]) if r["http_code"] else "—"
            count   = str(r["tender_count"]) if r["tender_count"] else ("JS" if r["skip_reason"] else "0")
            dur     = f"{r['duration_s']}s"
            note    = r["skip_reason"] or r["error"] or ""
            print(f"  {icon} {name:<42} {code:<6} {count:<9} {dur:<7} {note[:30]}")

        if show_industries:
            all_industries = set()
            for r in prov_results:
                all_industries.update(r.get("industries", []))
            if all_industries:
                print(f"\n     Industries detected in {province}:")
                for ind in sorted(all_industries):
                    print(f"       • {ind}")

    # Summary
    print("\n" + "=" * 90)
    print(f"  SUMMARY")
    print(f"  {'Total sites tested:':<35} {total_sites}")
    print(f"  {'✅ Active (returning tenders):':<35} {total_active}")
    print(f"  {'⚡ Playwright (not tested here):':<35} {total_playwright}")
    print(f"  {'🟡 Reachable but 0 tenders:':<35} {total_broken}")
    print(f"  {'🔴 Unreachable / dead:':<35} {total_dead}")
    print(f"  {'Total tender links detected:':<35} {total_tenders}")
    print("=" * 90)

    # Industry coverage across all sites
    all_industries: dict = defaultdict(int)
    for r in results:
        for ind in r.get("industries", []):
            all_industries[ind] += 1
    if all_industries:
        print(f"\n  INDUSTRY COVERAGE (across all active sites):")
        for ind, count in sorted(all_industries.items(), key=lambda x: -x[1]):
            bar = "█" * count
            print(f"    {ind:<32} {count:>3} sites  {bar}")

    print("=" * 90 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Test all sites in the TenderScout registry")
    parser.add_argument("--all",      action="store_true", help="Include broken and dead sites")
    parser.add_argument("--site",     type=str, default=None, help="Test a single site by name")
    parser.add_argument("--province", type=str, default=None, help="Filter by province")
    parser.add_argument("--type",     type=str, default=None, help="Filter by scrape_type")
    parser.add_argument("--no-industries", action="store_true", help="Hide industry breakdown")
    args = parser.parse_args()

    # Build source list
    if args.all:
        sources = ALL_SOURCES
    else:
        sources = ACTIVE_SOURCES + BROKEN_SOURCES  # skip dead by default

    if args.site:
        sources = [s for s in sources if args.site.lower() in s["name"].lower()]
    if args.province:
        sources = [s for s in sources if (s.get("province") or "").lower() == args.province.lower()]
    if args.type:
        sources = [s for s in sources if s.get("scrape_type") == args.type]

    if not sources:
        print("No sources matched your filters.")
        return

    print(f"\n  Testing {len(sources)} sites...")
    print(f"  (Playwright sites will show as ⚡ — run test_etenders.py separately)\n")

    # Run all tests concurrently (with a semaphore to avoid hammering)
    sem = asyncio.Semaphore(8)

    async with httpx.AsyncClient(
        headers=get_headers(),
        follow_redirects=True,
        verify=False,
        timeout=20,
    ) as client:

        async def bounded_test(source):
            async with sem:
                return await test_source(client, source)

        results = await asyncio.gather(*[bounded_test(s) for s in sources])

    print_results(list(results), show_industries=not args.no_industries)

    # Highlight resurrected dead sites
    resurrected = [r for r in results if r["status"] == "resurrected"]
    if resurrected:
        print("  🔄 PREVIOUSLY DEAD SITES NOW ALIVE — update registry.py:")
        for r in resurrected:
            print(f"     {r['name']}  →  {r['url']}")
        print()

    # Highlight sites that were active but now return 0 tenders
    newly_broken = [
        r for r in results
        if r.get("status") == "active"
        and r["reachable"]
        and r["tender_count"] == 0
        and not r["skip_reason"]
    ]
    if newly_broken:
        print("  ⚠️  ACTIVE SITES NOW RETURNING 0 TENDERS — selectors may need updating:")
        for r in newly_broken:
            print(f"     {r['name']}  →  {r['url']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())