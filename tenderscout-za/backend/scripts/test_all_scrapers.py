"""
Test script for all scraper modules.
Run from backend directory with venv activated:
    python scripts/test_all_scrapers.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import httpx
from datetime import datetime
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

from scraper.utils import get_headers
from scraper.sites import city_portals, sa_tenders, tender_bulletins, js_scraper


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_js_source_url(source: Dict) -> str:
    """
    Get the primary URL from a JS source configuration.
    
    Handles both:
        - Simple case: source["url"] (if present)
        - Province case: first value from source["province_urls"]
        - Fallback: source["base_url"]
    
    Args:
        source: JS source configuration dictionary
        
    Returns:
        URL string for testing
    """
    # Check for direct url field (added in updated js_scraper.py)
    if "url" in source:
        return source["url"]
    
    # Otherwise get first province URL
    urls = source.get("province_urls", {})
    if urls:
        return list(urls.values())[0]
    
    # Fallback to base_url
    return source.get("base_url", "")


def _get_js_sources_for_testing() -> List[Dict]:
    """
    Get JS sources in a format compatible with testing.
    
    Returns a list of source dicts with a guaranteed 'url' field.
    """
    sources = []
    for src in js_scraper.JS_SOURCES:
        sources.append({
            **src,
            "url": _get_js_source_url(src)  # Add flat url field for test
        })
    return sources


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

async def test_city_portal(client: httpx.AsyncClient, city: Dict, index: int, total: int):
    """Test a single city portal."""
    name = city["name"]
    
    print(f"[{index}/{total}] Testing: {name[:40]:<40}", end=" ", flush=True)
    
    try:
        results = await city_portals.scrape_city(client, city)
        count = len(results)
        if count > 0:
            print(f"✅ {count:>4} tenders")
            # Show first tender as sample
            if results:
                t = results[0]
                print(f"      Sample: {t['title'][:60]}...")
        else:
            print(f"⚠️  {count:>4} tenders")
    except Exception as e:
        print(f"❌ ERROR: {str(e)[:40]}")
    
    return name, count


async def test_aggregator(client: httpx.AsyncClient, source: Dict, index: int, total: int):
    """Test a single aggregator."""
    name = source["name"]
    
    print(f"[{index}/{total}] Testing: {name[:40]:<40}", end=" ", flush=True)
    
    try:
        results = await sa_tenders.scrape_aggregator(client, source)
        count = len(results)
        if count > 0:
            print(f"✅ {count:>4} tenders")
            if results:
                t = results[0]
                print(f"      Sample: {t['title'][:60]}...")
        else:
            print(f"⚠️  {count:>4} tenders")
    except Exception as e:
        print(f"❌ ERROR: {str(e)[:40]}")
    
    return name, count


async def test_bulletin(client: httpx.AsyncClient, source: Dict, index: int, total: int):
    """Test a single bulletin source."""
    name = source["name"]
    
    print(f"[{index}/{total}] Testing: {name[:40]:<40}", end=" ", flush=True)
    
    try:
        results = await tender_bulletins.scrape_source(client, source)
        count = len(results)
        if count > 0:
            print(f"✅ {count:>4} tenders")
            if results:
                t = results[0]
                print(f"      Sample: {t['title'][:60]}...")
        else:
            print(f"⚠️  {count:>4} tenders")
    except Exception as e:
        print(f"❌ ERROR: {str(e)[:40]}")
    
    return name, count


async def test_js_source(source: Dict, index: int, total: int):
    """Test a single JS source."""
    name = source["name"]
    
    print(f"[{index}/{total}] Testing: {name[:40]:<40}", end=" ", flush=True)
    
    try:
        # Use scrape_js_source_by_name if available, otherwise use scrape_js_source
        if hasattr(js_scraper, 'scrape_js_source_by_name'):
            results = await js_scraper.scrape_js_source_by_name(name)
        else:
            results = await js_scraper.scrape_js_source(source)
            
        count = len(results)
        if count > 0:
            print(f"✅ {count:>4} tenders")
            if results:
                t = results[0]
                print(f"      Sample: {t['title'][:60]}...")
        else:
            print(f"⚠️  {count:>4} tenders")
    except Exception as e:
        print(f"❌ ERROR: {str(e)[:40]}")
    
    return name, count


async def test_etenders():
    """Test the eTenders portal separately (requires Playwright)."""
    print("\n🎯 TESTING: eTenders Portal (National)")
    print("-" * 80)
    
    try:
        from scraper.sites.etenders import scrape_etenders
        print("Running eTenders scraper (this may take 30-60 seconds)...")
        results = await scrape_etenders()
        count = len(results)
        
        if count > 0:
            print(f"✅ {count:>4} tenders extracted")
            if results:
                t = results[0]
                print(f"   Sample: {t['title'][:60]}...")
                print(f"   Province: {t.get('province', 'N/A')}")
                print(f"   Closing: {t.get('closing_date', 'N/A')}")
        else:
            print(f"⚠️  {count:>4} tenders extracted")
            
        return count
    except ImportError:
        print("❌ Playwright not installed. Run: pip install playwright && playwright install chromium")
        return 0
    except Exception as e:
        print(f"❌ ERROR: {str(e)[:80]}")
        return 0


# =============================================================================
# MAIN
# =============================================================================

async def main():
    print("\n" + "=" * 80)
    print(f"  TENDERSCOUT ZA - SCRAPER TEST SUITE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")
    
    results_summary = {
        "city": {"passed": 0, "failed": 0, "total": 0},
        "aggregator": {"passed": 0, "failed": 0, "total": 0},
        "bulletin": {"passed": 0, "failed": 0, "total": 0},
        "js": {"passed": 0, "failed": 0, "total": 0},
    }
    
    async with httpx.AsyncClient(
        timeout=30, headers=get_headers(), follow_redirects=True, verify=False
    ) as client:
        
        # ----------------------------------------------------------------------
        # PHASE 1: City Portals (sample of key ones)
        # ----------------------------------------------------------------------
        print("\n🏙️  PHASE 1: CITY PORTALS (Sample)\n")
        print("-" * 80)
        
        # Test a representative sample of city portals
        sample_cities = [
            c for c in city_portals.CITY_PORTALS 
            if c["name"] in [
                "City of Cape Town",
                "City of Ekurhuleni",
                "Buffalo City Metro",
                "Nelson Mandela Bay",
                "Northern Cape Provincial Government",
                "Gamagara Municipality",
                "Siyancuma Municipality",
                "Richtersveld Municipality",
                "Karoo Hoogland Municipality",
                "Siyathemba Municipality",
                "Municipalities.co.za (Northern Cape)",
            ]
        ]
        
        for i, city in enumerate(sample_cities, 1):
            name, count = await test_city_portal(client, city, i, len(sample_cities))
            results_summary["city"]["total"] += 1
            if count > 0:
                results_summary["city"]["passed"] += 1
            else:
                results_summary["city"]["failed"] += 1
        
        # ----------------------------------------------------------------------
        # PHASE 2: Aggregators
        # ----------------------------------------------------------------------
        print("\n📡 PHASE 2: AGGREGATORS\n")
        print("-" * 80)
        
        for i, source in enumerate(sa_tenders.AGGREGATORS, 1):
            name, count = await test_aggregator(client, source, i, len(sa_tenders.AGGREGATORS))
            results_summary["aggregator"]["total"] += 1
            if count > 0:
                results_summary["aggregator"]["passed"] += 1
            else:
                results_summary["aggregator"]["failed"] += 1
        
        # ----------------------------------------------------------------------
        # PHASE 3: Bulletins
        # ----------------------------------------------------------------------
        if tender_bulletins.SOURCES:
            print("\n📰 PHASE 3: BULLETINS\n")
            print("-" * 80)
            
            for i, source in enumerate(tender_bulletins.SOURCES, 1):
                name, count = await test_bulletin(client, source, i, len(tender_bulletins.SOURCES))
                results_summary["bulletin"]["total"] += 1
                if count > 0:
                    results_summary["bulletin"]["passed"] += 1
                else:
                    results_summary["bulletin"]["failed"] += 1
        else:
            print("\n📰 PHASE 3: BULLETINS\n")
            print("-" * 80)
            print("  No bulletin sources configured.")
        
        # ----------------------------------------------------------------------
        # PHASE 4: JavaScript Sources
        # ----------------------------------------------------------------------
        print("\n⚡ PHASE 4: JAVASCRIPT SOURCES\n")
        print("-" * 80)
        
        js_sources = _get_js_sources_for_testing()
        if js_sources:
            for i, source in enumerate(js_sources, 1):
                name, count = await test_js_source(source, i, len(js_sources))
                results_summary["js"]["total"] += 1
                if count > 0:
                    results_summary["js"]["passed"] += 1
                else:
                    results_summary["js"]["failed"] += 1
        else:
            print("  No JS sources configured.")
    
    # ----------------------------------------------------------------------
    # PHASE 5: eTenders (separate due to longer runtime)
    # ----------------------------------------------------------------------
    print("\n🎯 PHASE 5: eTENDERS PORTAL\n")
    print("-" * 80)
    et_count = await test_etenders()
    
    # ----------------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("  TEST SUMMARY")
    print("=" * 80)
    
    def print_category(name: str, stats: dict):
        passed = stats["passed"]
        failed = stats["failed"]
        total = stats["total"]
        if total > 0:
            success_rate = (passed / total) * 100
            print(f"  {name:<15} {passed}/{total} passed ({success_rate:.0f}%) — {failed} failed")
        else:
            print(f"  {name:<15} No sources tested")
    
    print_category("City Portals", results_summary["city"])
    print_category("Aggregators", results_summary["aggregator"])
    print_category("Bulletins", results_summary["bulletin"])
    print_category("JS Sources", results_summary["js"])
    
    if et_count > 0:
        print(f"  {'eTenders':<15} ✅ {et_count} tenders extracted")
    else:
        print(f"  {'eTenders':<15} ⚠️ 0 tenders extracted")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())