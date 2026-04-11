import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
import models
from scraper.sites import sa_tenders, tender_bulletins, city_portals

logger = logging.getLogger(__name__)

SCRAPERS = [
    ("sa-tenders.co.za", sa_tenders.scrape),
    ("tenderbulletins.co.za", tender_bulletins.scrape),
    ("city-portals", city_portals.scrape),
]


def print_scrape_table(results: list):
    print("\n" + "=" * 75)
    print(f"  TENDERSCOUT ZA - Scrape Report  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)
    print(f"  {'Source':<35} {'Scraped':>8} {'New':>6} {'Status':<12}")
    print("-" * 75)
    total_scraped = 0
    total_new = 0
    for row in results:
        status = "OK" if row["status"] == "ok" else "FAILED" if row["status"] == "error" else "NO DATA"
        icon = "[+]" if row["new"] > 0 else "[ ]" if row["status"] == "ok" else "[!]"
        print(f"  {icon} {row['source']:<32} {row['scraped']:>8} {row['new']:>6}   {status}")
        total_scraped += row["scraped"]
        total_new += row["new"]
    print("-" * 75)
    print(f"  {'TOTAL':<35} {total_scraped:>8} {total_new:>6}")
    print("=" * 75)

    # DB total
    db = SessionLocal()
    try:
        db_total = db.query(models.Tender).count()
        print(f"  Database total: {db_total} tenders stored")
    finally:
        db.close()
    print("=" * 75 + "\n")


def upsert_tenders(db: Session, tenders: list):
    new_count = 0
    for t in tenders:
        if not t.get("content_hash") or not t.get("title"):
            continue
        try:
            exists = db.query(models.Tender).filter(
                models.Tender.content_hash == t["content_hash"]
            ).first()
            if not exists:
                db.add(models.Tender(**{k: v for k, v in t.items()}))
                db.commit()
                new_count += 1
        except IntegrityError:
            db.rollback()
        except Exception as e:
            db.rollback()
            logger.error(f"[SCRAPER] Insert failed: {e}")
    return new_count


def update_scraper_status(db: Session, site_name: str, count: int, error: str = None):
    try:
        status = db.query(models.ScraperStatus).filter(
            models.ScraperStatus.site_name == site_name
        ).first()
        if not status:
            status = models.ScraperStatus(site_name=site_name)
            db.add(status)
        status.last_scraped_at = datetime.utcnow()
        status.last_result_count = count
        status.last_error = error
        status.is_healthy = error is None
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[SCRAPER] Status update failed for {site_name}: {e}")


async def run_scraper():
    logger.info("[SCRAPER] Cycle started...")
    db = SessionLocal()
    report = []
    total_new = 0

    try:
        for site_name, scrape_fn in SCRAPERS:
            if site_name == "city-portals":
                # city-portals returns per-city breakdown
                from scraper.sites.city_portals import CITY_PORTALS, scrape_city
                import httpx
                from scraper.utils import get_headers
                async with httpx.AsyncClient(
                    timeout=20,
                    headers=get_headers(),
                    follow_redirects=True,
                    verify=False
                ) as client:
                    for city in CITY_PORTALS:
                        try:
                            city_tenders = await scrape_city(client, city)
                            new = upsert_tenders(db, city_tenders)
                            total_new += new
                            report.append({
                                "source": city["name"],
                                "scraped": len(city_tenders),
                                "new": new,
                                "status": "ok" if city_tenders is not None else "error"
                            })
                            update_scraper_status(db, city["name"], new)
                        except Exception as e:
                            report.append({
                                "source": city["name"],
                                "scraped": 0,
                                "new": 0,
                                "status": "error"
                            })
                            update_scraper_status(db, city["name"], 0, str(e))
            else:
                try:
                    tenders = await scrape_fn()
                    new = upsert_tenders(db, tenders)
                    total_new += new
                    report.append({
                        "source": site_name,
                        "scraped": len(tenders),
                        "new": new,
                        "status": "ok"
                    })
                    update_scraper_status(db, site_name, new)
                except Exception as e:
                    db.rollback()
                    report.append({
                        "source": site_name,
                        "scraped": 0,
                        "new": 0,
                        "status": "error"
                    })
                    update_scraper_status(db, site_name, 0, str(e))
    finally:
        db.close()

    print_scrape_table(report)
    return total_new
