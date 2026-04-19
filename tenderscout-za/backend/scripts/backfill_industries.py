"""
scripts/backfill_industries.py
-------------------------------
Reclassifies all tenders in the DB using the new 16-category industry system.

Run ONCE after updating utils.py INDUSTRY_KEYWORDS:

    cd backend
    python scripts/backfill_industries.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Tender
from scraper.utils import detect_industry
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

def backfill():
    db = SessionLocal()
    tenders = db.query(Tender).all()
    total   = len(tenders)
    updated = 0

    from collections import Counter
    new_categories = Counter()

    for t in tenders:
        text = f"{t.title or ''} {t.description or ''} {t.issuing_body or ''}"
        new_cat = detect_industry(text)
        if new_cat != t.industry_category:
            t.industry_category = new_cat
            updated += 1
        new_categories[new_cat] += 1

    db.commit()
    db.close()

    print(f"\nBackfill complete — {updated}/{total} tenders reclassified\n")
    print("New industry breakdown:")
    for cat, count in new_categories.most_common():
        bar = "█" * (count // 10)
        print(f"  {cat:<42} {count:>5}  {bar}")
    print()

if __name__ == "__main__":
    backfill()