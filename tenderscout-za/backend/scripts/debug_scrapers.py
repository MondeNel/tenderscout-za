"""
scripts/debug_scrapers.py
--------------------------
Run this to diagnose which sites are returning 0 tenders and why.

    cd backend
    python scripts/debug_scrapers.py
"""
import asyncio
import sys
import os

_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import httpx
from bs4 import BeautifulSoup
from scraper.utils import get_headers

# Sites that showed 0 scraped in the engine report
PROBLEM_SITES = [
    ("Dikgatlong Municipality",    "https://dikgatlong.gov.za/tenders-quotations/tenders",       "dikgatlong"),
    ("Magareng Municipality",      "https://www.magareng.gov.za/index.php/tenders-quotations/tenders", "dikgatlong"),
    ("Phokwane Municipality",      "https://phokwane.gov.za/category/tenders-quotations/",        "phokwane"),
    ("Frances Baard District",     "https://francesbaard.gov.za/tenders/",                        "frances_baard"),
    ("Dawid Kruiper Municipality", "https://web.dkm.gov.za/bids",                                 "dawid_kruiper"),
    ("Ga-Segonyana Municipality",  "https://ga-segonyana.gov.za/Tenders.html",                    "ga_segonyana"),
    ("Richtersveld Municipality",  "https://www.richtersveld.gov.za/tenders",                     "phoca"),
    ("Hantam Municipality",        "https://www.hantam.gov.za/tenders",                           "hantam"),
]

TENDER_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement"]


async def debug_site(client, name, url, scrape_type):
    print(f"\n{'='*65}")
    print(f"  {name}  [{scrape_type}]")
    print(f"  {url}")
    print(f"{'='*65}")

    try:
        r = await client.get(url, timeout=20)
        print(f"  HTTP: {r.status_code}  |  Size: {len(r.text):,} chars")

        if r.status_code != 200:
            print(f"  ❌ Non-200 response")
            return

        soup = BeautifulSoup(r.text, "lxml")

        # Show all headings
        headings = [h.get_text().strip()[:50] for h in soup.select("h1,h2,h3,h4,h5")[:8]]
        print(f"  Headings: {headings}")

        # Show tables
        tables = soup.select("table")
        print(f"  Tables: {len(tables)}")
        for i, tbl in enumerate(tables[:2]):
            rows = tbl.select("tr")
            print(f"    Table {i}: {len(rows)} rows")
            for row in rows[:3]:
                cells = [c.get_text().strip()[:30] for c in row.select("td,th")]
                print(f"      {cells}")

        # WordPress articles
        articles = soup.select("article, .post, .entry, div.type-post")
        print(f"  WP Articles: {len(articles)}")
        for a in articles[:3]:
            title = a.select_one("h1,h2,h3,.entry-title")
            if title:
                print(f"    '{title.get_text().strip()[:60]}'")

        # PDF links
        pdfs = soup.select("a[href*='.pdf'], a[href*='.PDF']")
        print(f"  PDF links: {len(pdfs)}")
        for p in pdfs[:5]:
            print(f"    '{p.get_text().strip()[:40]}' → {p.get('href','')[:60]}")

        # All links with tender keywords
        tender_links = []
        for a in soup.select("a[href]"):
            t = a.get_text().strip()
            h = a.get("href", "")
            if any(kw in t.lower() for kw in TENDER_KEYWORDS) and len(t) > 5:
                tender_links.append((t[:60], h[:60]))
        print(f"  Tender keyword links: {len(tender_links)}")
        for t, h in tender_links[:5]:
            print(f"    '{t}' → {h}")

        # Scraper-specific checks
        if scrape_type == "dikgatlong":
            headings_with_tender = [
                h.get_text().strip()[:80]
                for h in soup.select("h1,h2,h3,h4,h5,.entry-title")
                if any(kw in h.get_text().lower() for kw in TENDER_KEYWORDS)
            ]
            print(f"  Tender headings found: {len(headings_with_tender)}")
            for h in headings_with_tender[:5]:
                print(f"    '{h}'")

        if scrape_type == "ga_segonyana":
            for tbl in tables:
                header = tbl.select_one("tr")
                if header:
                    print(f"  Table header: {[c.get_text().strip() for c in header.select('th,td')]}")

        if scrape_type == "dawid_kruiper":
            tabs = soup.select("[role='tab'], .tab, .nav-tab, li.active")
            print(f"  Tabs found: {[t.get_text().strip()[:30] for t in tabs[:5]]}")

    except Exception as e:
        print(f"  ❌ ERROR: {e}")


async def main():
    print("\nDEBUGGING SCRAPERS THAT RETURNED 0 TENDERS")
    print("=" * 65)

    async with httpx.AsyncClient(
        headers=get_headers(), follow_redirects=True, verify=False
    ) as client:
        for name, url, scrape_type in PROBLEM_SITES:
            await debug_site(client, name, url, scrape_type)

    print("\n" + "=" * 65)
    print("Debug complete. Share this output to get scrapers fixed.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())