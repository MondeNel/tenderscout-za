"""
scripts/backfill_industries.py
Reclassify all tenders in the DB using the current 16-category system.

    cd backend
    python scripts/backfill_industries.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Tender
from scraper.utils import detect_industry
from collections import Counter

def backfill():
    db      = SessionLocal()
    try:
        tenders = db.query(Tender).all()
        if not tenders:
            print("No tenders in DB yet — run a scrape cycle first.")
            return

        total   = len(tenders)
        updated = 0
        new_cats = Counter()

        for t in tenders:
            text    = f"{t.title or ''} {t.description or ''} {t.issuing_body or ''}"
            new_cat = detect_industry(text)
            new_cats[new_cat] += 1
            if new_cat != t.industry_category:
                t.industry_category = new_cat
                updated += 1

        db.commit()
        print(f"\nBackfill complete — {updated}/{total} tenders reclassified\n")
        print("New industry breakdown:")
        for cat, count in new_cats.most_common():
            bar = "█" * (count // max(1, total // 40))
            print(f"  {cat:<42} {count:>5}  {bar}")
        print()
    finally:
        db.close()

if __name__ == "__main__":
    backfill()