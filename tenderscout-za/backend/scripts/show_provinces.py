"""
scripts/show_provinces.py
--------------------------
Shows province, industry, and source distribution of all tenders in the DB.

Usage:
    cd backend
    python scripts/show_provinces.py

Output sections:
1. Province distribution (total tenders and active count, with ASCII bar chart)
2. Industry breakdown (only active tenders, with bar chart)
3. Northern Cape source breakdown (if any NC tenders exist)
"""

import sys
import os

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so we can import the database
# and models.
# ---------------------------------------------------------------------------
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from collections import Counter
from database import SessionLocal
from models import Tender


def main() -> None:
    """Print a summary of the tender database contents."""

    # Create a database session
    db = SessionLocal()

    # Fetch all tenders (active and inactive)
    tenders = db.query(Tender).all()

    # ------------------------------------------------------------------
    # Province distribution
    # ------------------------------------------------------------------
    # Count how many tenders are in each province. Tenders without a
    # province are grouped separately as None and removed from the main
    # Counter for cleaner output.
    province_counts = Counter(t.province for t in tenders)
    null_count = province_counts.pop(None, 0)
    active = sum(1 for t in tenders if t.is_active)

    print(f"\n{'='*60}")
    print(f"  Province distribution  ({len(tenders)} total, {active} active)")
    print(f"{'='*60}")

    for prov, count in province_counts.most_common():
        # Scale the bar so the longest is ~40 characters
        bar = "█" * min(count // max(len(tenders) // 40, 1), 40)
        print(f"  {prov:<25} {count:>5}  {bar}")
    print(f"  {'NULL':<25} {null_count:>5}")

    # ------------------------------------------------------------------
    # Industry breakdown (active tenders only)
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  Industry breakdown")
    print(f"{'='*60}")

    ind_counts = Counter(t.industry_category for t in tenders if t.is_active)
    for ind, count in ind_counts.most_common():
        bar = "█" * min(count // max(active // 40, 1), 40)
        print(f"  {ind:<42} {count:>5}  {bar}")

    # ------------------------------------------------------------------
    # Northern Cape detail (if any NC tenders exist)
    # ------------------------------------------------------------------
    nc = [t for t in tenders if t.province == "Northern Cape"]
    if nc:
        print(f"\n  Northern Cape by source ({len(nc)}):")
        for src, c in Counter(t.source_site for t in nc).most_common():
            print(f"    {src:<38} {c:>4}")

    print(f"{'='*60}\n")
    db.close()


if __name__ == "__main__":
    main()