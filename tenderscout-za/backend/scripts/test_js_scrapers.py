"""
Test script for JS-rendered aggregator scrapers.
Run from backend directory with venv activated:
    python scripts/test_js_scrapers.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from scraper.sites import js_scraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

async def test_source(source_name: str, show_all: bool = True):
    """Test a single JS source by name."""
    source = None
    for s in js_scraper.JS_SOURCES:
        if s["name"] == source_name:
            source = s
            break
    
    if not source:
        print(f"Source '{source_name}' not found in JS_SOURCES")
        return

    print(f"\n{'='*80}")
    print(f"Testing: {source['name']}")
    print(f"URL: {source['url']}")
    print(f"{'='*80}\n")

    try:
        results = await js_scraper.scrape_js_source(source)
        print(f"✅ Scraped {len(results)} tenders\n")
        
        if results:
            if show_all:
                print(f"📋 ALL {len(results)} TENDERS:\n")
                print("-" * 80)
                for i, tender in enumerate(results, 1):
                    print(f"\n{i}. {tender['title']}")
                    print(f"   Issuing Body: {tender['issuing_body'] or 'N/A'}")
                    print(f"   Closing Date: {tender['closing_date'] or 'N/A'}")
                    print(f"   Province:     {tender['province'] or 'N/A'}")
                    print(f"   Municipality: {tender['municipality'] or 'N/A'}")
                    print(f"   Town:         {tender['town'] or 'N/A'}")
                    print(f"   Industry:     {tender['industry_category']}")
                    print(f"   Document URL: {tender['document_url'] or 'N/A'}")
                    print(f"   Source URL:   {tender['source_url']}")
                print("\n" + "-" * 80)
            else:
                print("Sample tenders (first 3):")
                for i, tender in enumerate(results[:3], 1):
                    print(f"\n--- Tender {i} ---")
                    print(f"Title: {tender['title'][:100]}...")
                    print(f"Issuing Body: {tender['issuing_body']}")
                    print(f"Closing Date: {tender['closing_date']}")
                    print(f"Province: {tender['province']}")
                    print(f"Document URL: {tender['document_url']}")
                    print(f"Source URL: {tender['source_url']}")
        else:
            print("❌ No tenders found. Check selectors or if site structure changed.")
            
    except Exception as e:
        print(f"❌ Error scraping {source_name}: {e}")
        import traceback
        traceback.print_exc()


async def main():
    print("\n🔍 TenderScout ZA - JS Scraper Test\n")
    
    # Ask user if they want to see all tenders or just sample
    response = input("Show ALL tenders? (y/n, default: y): ").strip().lower()
    show_all = response != 'n'
    
    # Test EasyTenders
    await test_source("EasyTenders (Northern Cape)", show_all=show_all)
    
    # Test OnlineTenders
    await test_source("OnlineTenders (Northern Cape)", show_all=show_all)
    
    print("\n✅ Test completed.\n")


if __name__ == "__main__":
    asyncio.run(main())