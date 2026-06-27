#!/usr/bin/env python
"""
scripts/debug_selectors.py — Interactive CSS Selector Debugger
===============================================================
Run this to test the CSS selectors used by the sa‑tenders scrapers
against a live version of one of the aggregator sites.

    cd backend
    python scripts/debug_selectors.py            # interactive prompt
    python scripts/debug_selectors.py "sa-tenders.co.za"  # direct

The script prints the HTML that matches each selector so you can
quickly see whether the page structure has changed and which
selectors need updating.
"""

import asyncio
import sys
import os

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so that we can import the
# scraper modules (scraper.sites.sa_tenders).
# ---------------------------------------------------------------------------
_backend_dir = os.path.join(os.path.dirname(__file__), '..')
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from scraper.sites.sa_tenders import debug_selectors


async def main() -> None:
    """
    Entry point – either use a command‑line argument or ask the user
    which site they want to debug.
    """
    if len(sys.argv) > 1:
        site_name = sys.argv[1]
    else:
        # List the aggregators that have debug support
        print("Available sites:")
        print("  - EasyTenders (Northern Cape)")
        print("  - OnlineTenders (Northern Cape)")
        print("  - sa-tenders.co.za")
        print("  - TenderAlerts")
        site_name = input("\nEnter site name to debug: ").strip()

    # The actual debugging logic lives in sa_tenders.py – this script
    # just provides a convenient command‑line interface.
    await debug_selectors(site_name)


if __name__ == "__main__":
    asyncio.run(main())