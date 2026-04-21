"""
scripts/mark_expired.py
------------------------
Marks tenders with a parseable past closing date as is_active=False.
Safe to run repeatedly — idempotent.
Run: python scripts/mark_expired.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from database import SessionLocal
from models import Tender
from scraper.utils import is_closing_date_expired

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    db = SessionLocal()
    tenders = db.query(Tender).filter(Tender.is_active == True).all()
    expired = 0
    for t in tenders:
        if t.closing_date and is_closing_date_expired(t.closing_date):
            t.is_active = False
            expired += 1
    db.commit()
    db.close()
    print(f"Marked {expired} of {len(tenders)} active tenders as expired.")


if __name__ == "__main__":
    main()