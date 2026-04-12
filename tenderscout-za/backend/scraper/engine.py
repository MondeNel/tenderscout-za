import logging
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
import models
from scraper.sites import sa_tenders, tender_bulletins, city_portals
from scraper.crawler import run_crawler, CRAWL_TARGETS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scrapers that do NOT depend on crawler output (aggregator sites)
# ---------------------------------------------------------------------------
STANDALONE_SCRAPERS = [
    ("sa-tenders.co.za",      sa_tenders.scrape),
    ("tenderbulletins.co.za", tender_bulletins.scrape),
]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_scrape_table(crawler_summary: dict, scrape_report: list):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    width = 75

    print("\n" + "=" * width)
    print(f"  TENDERSCOUT ZA  |  {now}")
    print("=" * width)

    # --- Phase 1: crawler summary ---
    print("  PHASE 1 — CRAWLER")
    print(f"  {'Site':<38} {'URLs Found':>10}")
    print("-" * width)
    total_urls = 0
    for site, urls in crawler_summary.items():
        print(f"  {'':3}{site:<35} {len(urls):>10}")
        total_urls += len(urls)
    print(f"  {'TOTAL':<38} {total_urls:>10}")
    print()

    # --- Phase 2: scraper results ---
    print("  PHASE 2 — SCRAPER")
    print(f"  {'Source':<35} {'Scraped':>8} {'New':>6} {'Status':<12}")
    print("-" * width)
    total_scraped = total_new = 0
    for row in scrape_report:
        status = {"ok": "OK", "error": "FAILED"}.get(row["status"], "NO DATA")
        icon = "[+]" if row["new"] > 0 else "[ ]" if row["status"] == "ok" else "[!]"
        print(f"  {icon} {row['source']:<32} {row['scraped']:>8} {row['new']:>6}   {status}")
        total_scraped += row["scraped"]
        total_new += row["new"]
    print("-" * width)
    print(f"  {'TOTAL':<35} {total_scraped:>8} {total_new:>6}")
    print("=" * width)

    db = SessionLocal()
    try:
        db_total = db.query(models.Tender).count()
        print(f"  Database total: {db_total} tenders stored")
    finally:
        db.close()
    print("=" * width + "\n")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def upsert_tenders(db: Session, tenders: list) -> int:
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
            logger.error(f"[ENGINE] Insert failed: {e}")
    return new_count


def store_crawl_results(db: Session, site_name: str, seed_url: str, urls: list):
    """Persist discovered URLs to crawl_results table (upsert by url_hash)."""
    for entry in urls:
        url = entry["url"]
        url_hash = hashlib.md5(url.encode()).hexdigest()
        try:
            existing = db.query(models.CrawlResult).filter(
                models.CrawlResult.url_hash == url_hash
            ).first()
            if existing:
                existing.last_seen_at = datetime.utcnow()
                existing.is_active = True
            else:
                db.add(models.CrawlResult(
                    site_name=site_name,
                    seed_url=seed_url,
                    discovered_url=url,
                    depth=entry.get("depth", 0),
                    status_code=entry.get("status_code", 200),
                    url_hash=url_hash,
                ))
            db.commit()
        except IntegrityError:
            db.rollback()
        except Exception as e:
            db.rollback()
            logger.error(f"[ENGINE] CrawlResult insert failed: {e}")


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
        logger.error(f"[ENGINE] Status update failed for {site_name}: {e}")


# ---------------------------------------------------------------------------
# Phase 2 helpers — scrape crawler-verified URLs
# ---------------------------------------------------------------------------

async def _scrape_crawled_city(client, city: dict, verified_urls: list) -> list:
    """
    Re-scrapes each verified URL from the crawler using the appropriate
    city_portals extractor, but only hits live pages.
    """
    import httpx
    from scraper.utils import get_headers

    results = []
    for entry in verified_urls:
        url = entry["url"]
        # Build a synthetic city config pointing at this specific verified URL
        city_override = {**city, "url": url}
        try:
            city_results = await city_portals.scrape_city(client, city_override)
            results.extend(city_results)
        except Exception as e:
            logger.warning(f"[ENGINE] Failed to scrape verified URL {url}: {e}")
    return results


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_scraper():
    logger.info("[ENGINE] ── Cycle start ──────────────────────────────────")
    db = SessionLocal()
    scrape_report = []
    total_new = 0

    # ── PHASE 1: Crawler ────────────────────────────────────────────────────
    logger.info("[ENGINE] Phase 1 — Crawling all sites...")
    crawl_index = await run_crawler()   # {site_name: [url_dicts]}

    # Persist crawl results
    target_map = {t["name"]: t["seed_url"] for t in CRAWL_TARGETS}
    for site_name, urls in crawl_index.items():
        store_crawl_results(db, site_name, target_map.get(site_name, ""), urls)
        update_scraper_status(db, f"crawler:{site_name}", len(urls))

    # ── PHASE 2: Scraper ────────────────────────────────────────────────────
    logger.info("[ENGINE] Phase 2 — Scraping verified URLs...")

    import httpx
    from scraper.utils import get_headers

    # Build a lookup: city name → CITY_PORTALS config dict
    city_config_map = {c["name"]: c for c in city_portals.CITY_PORTALS}

    async with httpx.AsyncClient(
        timeout=20,
        headers=get_headers(),
        follow_redirects=True,
        verify=False,
    ) as client:

        # 2a — Crawler-backed municipal/provincial portals
        for site_name, verified_urls in crawl_index.items():
            city_cfg = city_config_map.get(site_name)
            if not city_cfg:
                continue   # aggregator site — handled below

            if not verified_urls:
                scrape_report.append({
                    "source": site_name,
                    "scraped": 0,
                    "new": 0,
                    "status": "ok",
                })
                continue

            try:
                # Use verified URLs as scrape targets instead of the hardcoded seed
                tenders = await _scrape_crawled_city(client, city_cfg, verified_urls)
                new = upsert_tenders(db, tenders)
                total_new += new
                scrape_report.append({
                    "source": site_name,
                    "scraped": len(tenders),
                    "new": new,
                    "status": "ok",
                })
                update_scraper_status(db, site_name, new)
            except Exception as e:
                scrape_report.append({"source": site_name, "scraped": 0, "new": 0, "status": "error"})
                update_scraper_status(db, site_name, 0, str(e))
                logger.error(f"[ENGINE] {site_name} scrape error: {e}")

        # 2b — Standalone aggregator scrapers (sa-tenders, tenderbulletins)
        for site_name, scrape_fn in STANDALONE_SCRAPERS:
            try:
                tenders = await scrape_fn()
                new = upsert_tenders(db, tenders)
                total_new += new
                scrape_report.append({
                    "source": site_name,
                    "scraped": len(tenders),
                    "new": new,
                    "status": "ok",
                })
                update_scraper_status(db, site_name, new)
            except Exception as e:
                db.rollback()
                scrape_report.append({"source": site_name, "scraped": 0, "new": 0, "status": "error"})
                update_scraper_status(db, site_name, 0, str(e))
                logger.error(f"[ENGINE] {site_name} standalone scrape error: {e}")

    print_scrape_table(crawl_index, scrape_report)

    if total_new > 0:
        try:
            from notifications import send_admin_notification, send_user_alerts
            send_admin_notification(total_new)
            send_user_alerts(db)
        except Exception as e:
            logger.warning(f"[ENGINE] Email notification failed: {e}")

    db.close()

    logger.info(f"[ENGINE] ── Cycle complete — {total_new} new tenders ──────")
    return total_new