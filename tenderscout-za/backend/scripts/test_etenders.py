"""
test_etenders.py  —  run from backend/:
    python scripts/test_etenders.py
"""

import asyncio, json, logging, sys, os
from collections import Counter

_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    print("\n" + "=" * 72)
    print("  eTenders Portal — Scraper Test")
    print("=" * 72)

    try:
        from scraper.sites.etenders import scrape_etenders
    except ImportError as e:
        print(f"\n  ❌  Import error: {e}")
        print(f"  Run from:  cd tenderscout-za/backend && python scripts/test_etenders.py")
        return

    try:
        from playwright.sync_api import sync_playwright  # noqa
    except ImportError:
        print("\n  ❌  Playwright missing.  Run:")
        print("       pip install playwright")
        print("       python -m playwright install chromium")
        return

    print("\n  Running scraper (30-120s)...\n")
    tenders = await scrape_etenders()

    if not tenders:
        print("  ❌  No tenders returned — check INFO/ERROR logs above")
        return

    print(f"\n  ✅  {len(tenders)} tenders found\n")
    print(f"  {'#':<4} {'Title':<56} {'Closing':<13} {'Province':<18} Doc?")
    print("  " + "-" * 96)

    for i, t in enumerate(tenders[:40], 1):
        title   = (t.get("title") or "")[:54]
        closing = (t.get("closing_date") or "")[:12]
        prov    = (t.get("province") or "Unknown")[:16]
        doc     = "✓" if t.get("document_url") else "-"
        print(f"  {i:<4} {title:<56} {closing:<13} {prov:<18} {doc}")

    if len(tenders) > 40:
        print(f"\n  ... {len(tenders) - 40} more not shown")

    print(f"\n  Province breakdown:")
    for p, c in Counter(t.get("province") or "Unknown" for t in tenders).most_common():
        print(f"    {(p or 'Unknown'):<28} {c}")

    print(f"\n  Industry breakdown:")
    for ind, c in Counter(t.get("industry_category") or "General" for t in tenders).most_common(8):
        print(f"    {ind:<32} {c}")

    with_docs = sum(1 for t in tenders if t.get("document_url"))
    print(f"\n  Document links: {with_docs}/{len(tenders)}")

    out = os.path.join(_BACKEND_DIR, "etenders_test_output.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(tenders, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved to: {out}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    asyncio.run(main())