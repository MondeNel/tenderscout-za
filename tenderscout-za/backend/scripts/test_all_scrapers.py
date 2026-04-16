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
from typing import Dict  # <-- ADD THIS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

from scraper.utils import get_headers
from scraper.sites import city_portals, sa_tenders, tender_bulletins, js_scraper


async def test_city_portal(client: httpx.AsyncClient, city: Dict, index: int, total: int):
    """Test a single city portal."""
    name = city["name"]
    url = city["url"]
    
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
    
    return name, 0  # count tracked separately


async def test_aggregator(client: httpx.AsyncClient, source: Dict, index: int, total: int):
    """Test a single aggregator."""
    name = source["name"]
    url = source["url"]
    
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


async def test_bulletin(client: httpx.AsyncClient, source: Dict, index: int, total: int):
    """Test a single bulletin source."""
    name = source["name"]
    url = source["url"]
    
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


async def test_js_source(index: int, total: int):
    """Test a single JS source."""
    if not js_scraper.JS_SOURCES:
        print(f"[{index}/{total}] No JS sources configured")
        return
    
    source = js_scraper.JS_SOURCES[0]  # Only EasyTenders now
    name = source["name"]
    url = source["url"]
    
    print(f"[{index}/{total}] Testing: {name[:40]:<40}", end=" ", flush=True)
    
    try:
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


async def main():
    print("\n" + "=" * 80)
    print(f"  TENDERSCOUT ZA - SCRAPER TEST SUITE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")
    
    total_sources = 0
    
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
        
        total_sources += len(sample_cities)
        for i, city in enumerate(sample_cities, 1):
            await test_city_portal(client, city, i, len(sample_cities))
        
        # ----------------------------------------------------------------------
        # PHASE 2: Aggregators
        # ----------------------------------------------------------------------
        print("\n📡 PHASE 2: AGGREGATORS\n")
        print("-" * 80)
        
        total_sources += len(sa_tenders.AGGREGATORS)
        for i, source in enumerate(sa_tenders.AGGREGATORS, 1):
            await test_aggregator(client, source, i, len(sa_tenders.AGGREGATORS))
        
        # ----------------------------------------------------------------------
        # PHASE 3: Bulletins (if any)
        # ----------------------------------------------------------------------
        if tender_bulletins.SOURCES:
            print("\n📰 PHASE 3: BULLETINS\n")
            print("-" * 80)
            
            total_sources += len(tender_bulletins.SOURCES)
            for i, source in enumerate(tender_bulletins.SOURCES, 1):
                await test_bulletin(client, source, i, len(tender_bulletins.SOURCES))
        else:
            print("\n📰 PHASE 3: BULLETINS\n")
            print("-" * 80)
            print("  No bulletin sources configured.")
        
        # ----------------------------------------------------------------------
        # PHASE 4: JavaScript Sources
        # ----------------------------------------------------------------------
        print("\n⚡ PHASE 4: JAVASCRIPT SOURCES\n")
        print("-" * 80)
        
        if js_scraper.JS_SOURCES:
            total_sources += len(js_scraper.JS_SOURCES)
            for i in range(len(js_scraper.JS_SOURCES)):
                await test_js_source(i + 1, len(js_scraper.JS_SOURCES))
        else:
            print("  No JS sources configured.")
    
    # ----------------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f"  TEST COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())