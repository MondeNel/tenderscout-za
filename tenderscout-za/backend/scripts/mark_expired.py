"""
scripts/mark_expired.py
------------------------
Marks tenders with a parseable past closing date as is_active=False.

This script is safe to run at any time — it only transitions active
tenders to inactive when their closing date is in the past. Tenders
without a parseable date are left unchanged.

Usage:
    cd backend
    python scripts/mark_expired.py
"""

import sys
import os

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so we can import database + models.
# ---------------------------------------------------------------------------
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import logging
from database import SessionLocal
from models import Tender
from scraper.utils import is_closing_date_expired

# Minimal logging – just show the final summary
logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> None:
    """
    Query all currently active tenders, check if their closing date has
    passed, and flip is_active to False for the expired ones.

    The check is performed using `is_closing_date_expired`, which returns
    False for unparseable dates – those tenders are preserved as active
    to avoid accidentally hiding valid opportunities.
    """
    # Create a new database session
    db = SessionLocal()

    # Fetch every tender that is still marked as active
    tenders = db.query(Tender).filter(Tender.is_active == True).all()

    expired = 0
    for t in tenders:
        # Only consider tenders that actually have a closing_date string
        if t.closing_date and is_closing_date_expired(t.closing_date):
            t.is_active = False
            expired += 1

    # Commit all changes in a single transaction
    db.commit()
    db.close()

    print(f"Marked {expired} of {len(tenders)} active tenders as expired.")


if __name__ == "__main__":
    main()