"""
scripts/show_provinces.py
--------------------------
Shows province, industry, and source distribution of all tenders in the DB.
Run: python scripts/show_provinces.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import Counter
from database import SessionLocal
from models import Tender


def main():
    db = SessionLocal()
    tenders = db.query(Tender).all()

    province_counts = Counter(t.province for t in tenders)
    null_count = province_counts.pop(None, 0)
    active = sum(1 for t in tenders if t.is_active)

    print(f"\n{'='*60}")
    print(f"  Province distribution  ({len(tenders)} total, {active} active)")
    print(f"{'='*60}")
    for prov, count in province_counts.most_common():
        bar = "█" * min(count // max(len(tenders) // 40, 1), 40)
        print(f"  {prov:<25} {count:>5}  {bar}")
    print(f"  {'NULL':<25} {null_count:>5}")

    # Industry breakdown
    print(f"\n{'='*60}")
    print("  Industry breakdown")
    print(f"{'='*60}")
    ind_counts = Counter(t.industry_category for t in tenders if t.is_active)
    for ind, count in ind_counts.most_common():
        bar = "█" * min(count // max(active // 40, 1), 40)
        print(f"  {ind:<42} {count:>5}  {bar}")

    # NC breakdown by source
    nc = [t for t in tenders if t.province == "Northern Cape"]
    if nc:
        print(f"\n  Northern Cape by source ({len(nc)}):")
        for src, c in Counter(t.source_site for t in nc).most_common():
            print(f"    {src:<38} {c:>4}")

    print(f"{'='*60}\n")
    db.close()


if __name__ == "__main__":
    main()