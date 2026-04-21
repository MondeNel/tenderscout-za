"""
scripts/backfill_industries.py
-------------------------------
Re-classifies all tenders using the updated INDUSTRY_KEYWORDS.
Also re-runs municipality/town detection with the expanded lists.
Safe to run multiple times.

Run: python scripts/backfill_industries.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import Counter
from database import SessionLocal
from models import Tender
from scraper.utils import detect_industry, detect_municipality, detect_town


def backfill():
    db = SessionLocal()
    tenders = db.query(Tender).all()
    ind_updated  = 0
    loc_updated  = 0

    for t in tenders:
        text = f"{t.title or ''} {t.description or ''} {t.issuing_body or ''}"

        # Industry
        new_industry = detect_industry(text)
        if new_industry != t.industry_category:
            t.industry_category = new_industry
            ind_updated += 1

        # Municipality and town (within known province)
        if t.province and not t.municipality:
            mun = detect_municipality(text, t.province)
            if mun:
                t.municipality = mun
                loc_updated += 1

        if t.province and not t.town:
            town = detect_town(text, t.province)
            if town:
                t.town = town

    db.commit()

    all_industries = Counter(t.industry_category for t in tenders)
    total = len(tenders)
    print(f"\nBackfill complete:")
    print(f"  Industry reclassified : {ind_updated}/{total}")
    print(f"  Municipality filled   : {loc_updated}")
    print(f"\nIndustry breakdown:")
    for industry, count in all_industries.most_common():
        bar = "█" * min(count // max(total // 40, 1), 40)
        print(f"  {industry:<44} {count:>5}  {bar}")

    db.close()


if __name__ == "__main__":
    backfill()