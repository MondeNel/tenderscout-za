#!/usr/bin/env python
"""
Debug script to test CSS selectors against a specific site.
Run: python scripts/debug_selectors.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scraper.sites.sa_tenders import debug_selectors


async def main():
    if len(sys.argv) > 1:
        site_name = sys.argv[1]
    else:
        print("Available sites:")
        print("  - EasyTenders (Northern Cape)")
        print("  - OnlineTenders (Northern Cape)")
        print("  - sa-tenders.co.za")
        print("  - TenderAlerts")
        site_name = input("\nEnter site name to debug: ").strip()
    
    await debug_selectors(site_name)


if __name__ == "__main__":
    asyncio.run(main())