"""
TenderScout ZA — Crawler Test Script
=====================================
Run from your backend/ directory:

    cd backend
    source venv/Scripts/activate   # Windows Git Bash
    python test_crawler.py

Tests the crawler against a small subset of sites so you get results
in under a minute. Prints a detailed report of every URL discovered.
"""

import asyncio
import sys
import time
import hashlib
import logging
from urllib.parse import urlparse

# ── Silence noisy SSL warnings ──────────────────────────────────────────────
import warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ── Basic logging so crawler internals are visible ───────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("test_crawler")

# ── Import your crawler ───────────────────────────────────────────────────────
try:
    from scraper.crawler import crawl_site, CRAWL_TARGETS, TENDER_KEYWORDS
except ImportError as e:
    print(f"\n[ERROR] Could not import scraper.crawler: {e}")
    print("Make sure you're running this from the backend/ directory.\n")
    sys.exit(1)


# ── Test targets — smaller subset so the test completes quickly ───────────────
TEST_TARGETS = [
    {
        "name": "City of Ekurhuleni",
        "seed_url": "https://www.ekurhuleni.gov.za/tenders",
        "max_depth": 2,
        "max_pages": 10,
    },
    {
        "name": "Buffalo City Metro",
        "seed_url": "https://www.buffalocity.gov.za/tenders",
        "max_depth": 2,
        "max_pages": 10,
    },
    {
        "name": "Siyathemba Municipality",
        "seed_url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders",
        "max_depth": 1,
        "max_pages": 10,
    },
    {
        "name": "Nelson Mandela Bay",
        "seed_url": "https://www.nelsonmandelabay.gov.za/tenders",
        "max_depth": 2,
        "max_pages": 10,
    },
    {
        "name": "Northern Cape DEDAT",
        "seed_url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824",
        "max_depth": 1,
        "max_pages": 10,
    },
]


# ── Pretty printer helpers ─────────────────────────────────────────────────────

W = 80

def divider(char="─"):
    print(char * W)

def header(text):
    print()
    print("═" * W)
    print(f"  {text}")
    print("═" * W)

def section(text):
    print()
    print(f"  ── {text}")
    print("  " + "─" * (W - 4))


# ── Core test logic ────────────────────────────────────────────────────────────

async def test_single_site(target: dict) -> dict:
    """Crawl one site and return a result summary dict."""
    name = target["name"]
    seed = target["seed_url"]
    max_depth = target.get("max_depth", 2)
    max_pages = target.get("max_pages", 10)

    print(f"\n  → Crawling: {name}")
    print(f"    Seed : {seed}")
    print(f"    Depth: {max_depth}   Max pages: {max_pages}")

    t0 = time.time()
    try:
        urls = await crawl_site(
            seed_url=seed,
            max_depth=max_depth,
            max_pages=max_pages,
            polite_delay=0.5,   # faster for testing
        )
        elapsed = time.time() - t0
        return {
            "name": name,
            "seed": seed,
            "urls": urls,
            "elapsed": elapsed,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"[TEST] {name} failed: {e}")
        return {
            "name": name,
            "seed": seed,
            "urls": [],
            "elapsed": elapsed,
            "error": str(e),
        }


async def run_all_tests():
    header("TENDERSCOUT ZA — CRAWLER TEST SUITE")
    print(f"  Testing {len(TEST_TARGETS)} sites  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Keywords: {', '.join(TENDER_KEYWORDS)}")

    overall_start = time.time()
    results = []

    for target in TEST_TARGETS:
        result = await test_single_site(target)
        results.append(result)

    overall_elapsed = time.time() - overall_start

    # ── Summary table ──────────────────────────────────────────────────────────
    header("RESULTS SUMMARY")
    print(f"  {'Site':<35} {'URLs':>6} {'Time':>8}   Status")
    divider()

    total_urls = 0
    for r in results:
        status = "✓ OK" if not r["error"] else f"✗ {r['error'][:30]}"
        icon   = "  " if not r["error"] else "! "
        print(f"  {icon}{r['name']:<33} {len(r['urls']):>6} {r['elapsed']:>6.1f}s   {status}")
        total_urls += len(r["urls"])

    divider()
    print(f"  {'TOTAL':<35} {total_urls:>6} {overall_elapsed:>6.1f}s")

    # ── Per-site URL detail ────────────────────────────────────────────────────
    header("DISCOVERED URLs — DETAIL")

    for r in results:
        section(f"{r['name']}  ({len(r['urls'])} URLs found)")

        if r["error"]:
            print(f"  [ERROR] {r['error']}")
            continue

        if not r["urls"]:
            print("  No tender URLs discovered.")
            print(f"  Seed was: {r['seed']}")
            print("  Possible causes:")
            print("    • Site returned 404/403 at seed URL")
            print("    • No internal links matched tender keywords")
            print("    • Site uses JavaScript rendering (crawler can't execute JS)")
            continue

        for i, entry in enumerate(r["urls"], 1):
            depth_indicator = "  " * entry.get("depth", 0) + "↳" if entry.get("depth", 0) > 0 else " "
            print(f"  {i:>3}. [depth {entry.get('depth', 0)}] {entry['url']}")

    # ── Diagnostics ────────────────────────────────────────────────────────────
    header("DIAGNOSTICS")

    failed = [r for r in results if r["error"]]
    empty  = [r for r in results if not r["error"] and not r["urls"]]
    ok     = [r for r in results if not r["error"] and r["urls"]]

    print(f"  Sites with results  : {len(ok)}")
    print(f"  Sites with 0 results: {len(empty)}")
    print(f"  Sites with errors   : {len(failed)}")

    if empty:
        print()
        print("  Zero-result sites (check these manually):")
        for r in empty:
            print(f"    • {r['name']}  →  {r['seed']}")
        print()
        print("  Tips:")
        print("    1. Open the seed URL in a browser — does it load?")
        print("    2. If the page needs JavaScript, the crawler won't see links.")
        print("       Consider adding a Playwright/Pyppeteer phase for JS-heavy sites.")
        print("    3. If the site returns 403, try rotating User-Agent in crawler.py.")

    if failed:
        print()
        print("  Failed sites:")
        for r in failed:
            print(f"    • {r['name']}: {r['error']}")

    if ok:
        print()
        print("  ✓ Crawler is working. These URLs will feed Phase 2 (scraper).")
        print("    Run `python -m uvicorn main:app --reload` to start the full engine.")

    print()
    divider("═")
    print(f"  Test complete in {overall_elapsed:.1f}s")
    print("═" * W)
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_all_tests())