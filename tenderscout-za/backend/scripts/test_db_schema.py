# scripts/test_db_schema.py
"""
Verify that all database tables were created correctly.
Run: python scripts/test_db_schema.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models


def test_schema():
    """Test that all tables exist with correct columns."""
    db = SessionLocal()
    
    print("\n" + "=" * 60)
    print("  DATABASE SCHEMA VERIFICATION")
    print("=" * 60 + "\n")
    
    tables = [
        ("users", models.User),
        ("tenders", models.Tender),
        ("search_logs", models.SearchLog),
        ("transactions", models.Transaction),
        ("scraper_status", models.ScraperStatus),
        ("crawl_results", models.CrawlResult),
    ]
    
    for table_name, model in tables:
        try:
            count = db.query(model).count()
            print(f"✅ {table_name:<20} exists ({count} records)")
            
            # Check specific columns for CrawlResult
            if table_name == "crawl_results":
                # Test if new columns exist by querying them
                sample = db.query(model).first()
                if sample:
                    attrs = ['final_url', 'scraped_at', 'scrape_success', 'scrape_error', 'tenders_found']
                    for attr in attrs:
                        if hasattr(sample, attr):
                            print(f"   └─ {attr} column exists ✅")
                        else:
                            print(f"   └─ {attr} column MISSING ❌")
                            
        except Exception as e:
            print(f"❌ {table_name:<20} ERROR: {str(e)[:50]}")
    
    db.close()
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    test_schema()