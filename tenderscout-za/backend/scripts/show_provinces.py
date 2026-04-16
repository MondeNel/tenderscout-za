"""
scripts/show_provinces.py
--------------------------
Diagnostic — shows the province distribution of all tenders in the DB,
including per-source breakdown for Northern Cape.

Run:
    python scripts/show_provinces.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Tender
from collections import Counter


def main():
    db = SessionLocal()
    tenders = db.query(Tender).all()

    province_counts = Counter(t.province for t in tenders)
    null_count = province_counts.pop(None, 0)

    print(f"\n{'='*55}")
    print(f"  Province distribution ({len(tenders)} total tenders)")
    print(f"{'='*55}")
    for prov, count in province_counts.most_common():
        bar = "█" * min(count // 5, 40)
        print(f"  {prov:<22} {count:>5}  {bar}")
    print(f"  {'NULL / undetected':<22} {null_count:>5}")
    print(f"{'='*55}")

    # Northern Cape breakdown by source
    nc_tenders = [t for t in tenders if t.province == "Northern Cape"]
    if nc_tenders:
        print(f"\n  Northern Cape by source ({len(nc_tenders)} tenders):")
        nc_sources = Counter(t.source_site for t in nc_tenders)
        for src, count in nc_sources.most_common():
            print(f"    {src:<35} {count:>4}")

    # Active vs inactive
    active = sum(1 for t in tenders if t.is_active)
    inactive = len(tenders) - active
    print(f"\n  Active: {active}  |  Inactive/expired: {inactive}")
    print(f"{'='*55}\n")

    db.close()


if __name__ == "__main__":
    main()