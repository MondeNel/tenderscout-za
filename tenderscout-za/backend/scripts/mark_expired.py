"""
scripts/mark_expired.py
------------------------
Marks tenders with a parseable past closing date as is_active=False.
Safe to run repeatedly — idempotent.

Run:
    python scripts/mark_expired.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from database import SessionLocal
from models import Tender
from scraper.utils import is_closing_date_expired

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()
    tenders = db.query(Tender).filter(Tender.is_active == True).all()
    expired_count = 0

    for t in tenders:
        if t.closing_date and is_closing_date_expired(t.closing_date):
            t.is_active = False
            expired_count += 1
            logger.info(f"  Expired: {t.title[:60]} (closes {t.closing_date})")

    db.commit()
    db.close()
    logger.info(f"\nMarked {expired_count} of {len(tenders)} active tenders as expired.")


if __name__ == "__main__":
    main()