from database import SessionLocal
from models import Tender
from scraper.utils import is_closing_date_expired
import logging

logging.basicConfig(level=logging.INFO)
db = SessionLocal()

tenders = db.query(Tender).all()
expired_count = 0
for t in tenders:
    if t.closing_date and is_closing_date_expired(t.closing_date):
        t.is_active = False
        expired_count += 1
        print(f"Marked inactive: {t.title[:50]}... (closed {t.closing_date})")
db.commit()
print(f"Marked {expired_count} expired tenders as inactive")
db.close()
