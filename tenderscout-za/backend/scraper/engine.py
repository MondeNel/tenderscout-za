import logging
import hashlib
import httpx
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
import models
from scraper.utils import get_headers
from scraper.crawler import run_crawler, CRAWL_TARGETS
from scraper.sites import city_portals, sa_tenders, tender_bulletins, js_scraper   # ← added js_scraper
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unified source registry
# ---------------------------------------------------------------------------

ALL_CITY_SOURCES      = [{**c, "source_type": "city"}       for c in city_portals.CITY_PORTALS]
ALL_AGGREGATOR_SOURCES = [{**a, "source_type": "aggregator"} for a in sa_tenders.AGGREGATORS]
ALL_BULLETIN_SOURCES  = [{**s, "source_type": "bulletin"}   for s in tender_bulletins.SOURCES]
ALL_JS_SOURCES        = [{**j, "source_type": "js"}         for j in js_scraper.JS_SOURCES]   # ← new
ALL_SOURCES           = ALL_CITY_SOURCES + ALL_AGGREGATOR_SOURCES + ALL_BULLETIN_SOURCES + ALL_JS_SOURCES

_SOURCE_BY_NAME: Dict[str, Dict] = {s["name"]: s for s in ALL_SOURCES}


def get_source_by_name(name: str) -> Optional[Dict]:
    return _SOURCE_BY_NAME.get(name)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    new_count = 0
    for t in tenders:
        if not t.get("content_hash") or not t.get("title"):
            continue
        try:
            exists = db.query(models.Tender).filter(
                models.Tender.content_hash == t["content_hash"]
            ).first()
            if not exists:
                db.add(models.Tender(**{k: v for k, v in t.items() if hasattr(models.Tender, k)}))
                new_count += 1
        except IntegrityError:
            db.rollback()
        except Exception as e:
            db.rollback()
            logger.error(f"[ENGINE] Insert failed: {e}")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] Commit failed: {e}")
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
        status.is_healthy = (error is None)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] Status update failed for {site_name}: {e}")


# ---------------------------------------------------------------------------
# Scraping helpers
# ---------------------------------------------------------------------------

async def _scrape_source_urls(
    client: httpx.AsyncClient, source: Dict, urls: List[Dict]
) -> List[Dict]:
    """Re-scrape each crawler-verified URL using the appropriate scraper."""
    results = []
    src_type = source.get("source_type", "city")
    for entry in urls:
        url = entry["url"]
        try:
            if src_type == "city":
                city_override = {**source, "url": url}
                tenders = await city_portals.scrape_city(client, city_override)
            elif src_type == "aggregator":
                tenders = await sa_tenders.scrape_detail(client, url, source)
            elif src_type == "bulletin":
                tenders = await tender_bulletins.scrape_detail(client, url, source)
            else:
                tenders = []
            results.extend(tenders)
        except Exception as e:
            logger.warning(f"[ENGINE] Failed to scrape {url}: {e}")
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_report(crawler_summary: Dict, scrape_report: List[Dict], db: Session):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    width = 76

    print("\n" + "=" * width)
    print(f"  TENDERSCOUT ZA  |  {now}")
    print("=" * width)

    print("  PHASE 1 — CRAWLER")
    print(f"  {'Site':<40} {'URLs':>8}")
    print("-" * width)
    total_urls = 0
    for site, urls in crawler_summary.items():
        n = len(urls)
        print(f"     {site:<37} {n:>8}")
        total_urls += n
    print(f"  {'TOTAL':<40} {total_urls:>8}")
    print()

    print("  PHASE 2 — SCRAPER")
    print(f"  {'Source':<36} {'Scraped':>8} {'New':>6}   {'Status':<8}")
    print("-" * width)
    total_scraped = total_new = 0
    for row in scrape_report:
        status_str = "OK" if row["status"] == "ok" else "FAILED"
        icon = "[+]" if row["new"] > 0 else "[ ]" if row["status"] == "ok" else "[!]"
        print(f"  {icon} {row['source']:<33} {row['scraped']:>8} {row['new']:>6}   {status_str}")
        total_scraped += row["scraped"]
        total_new += row["new"]
    print("-" * width)
    print(f"  {'TOTAL':<36} {total_scraped:>8} {total_new:>6}")
    print("=" * width)

    try:
        db_total = db.query(models.Tender).count()
        active_total = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        print(f"  DB: {db_total} total tenders ({active_total} active)")
    except Exception:
        pass
    print("=" * width + "\n")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_scraper():
    logger.info("[ENGINE] ── Cycle start ──────────────────────────────────")
    db = SessionLocal()
    scrape_report: List[Dict] = []
    total_new = 0

    # ── Phase 1: Crawl — discover live tender URLs, persist CrawlResults ─────
    logger.info("[ENGINE] Phase 1 — Crawling...")
    crawl_index = await run_crawler(db)

    # ── Phase 2: Scrape crawler-verified URLs (city portals) ─────────────────
    logger.info("[ENGINE] Phase 2 — Scraping verified URLs...")

    async with httpx.AsyncClient(
        timeout=30, headers=get_headers(), follow_redirects=True, verify=False
    ) as client:

        for site_name, verified_urls in crawl_index.items():
            source = get_source_by_name(site_name)
            if not source:
                logger.debug(f"[ENGINE] No source config for '{site_name}' — skipping")
                continue

            if not verified_urls:
                scrape_report.append({"source": site_name, "scraped": 0, "new": 0, "status": "ok"})
                continue

            try:
                tenders = await _scrape_source_urls(client, source, verified_urls)
                new = upsert_tenders(db, tenders)
                total_new += new
                scrape_report.append({"source": site_name, "scraped": len(tenders), "new": new, "status": "ok"})
                update_scraper_status(db, site_name, new)
            except Exception as e:
                scrape_report.append({"source": site_name, "scraped": 0, "new": 0, "status": "error"})
                update_scraper_status(db, site_name, 0, str(e))
                logger.error(f"[ENGINE] {site_name} scrape error: {e}")

        # ── Phase 3: Run aggregator / bulletin listing scrapers ───────────────
        logger.info("[ENGINE] Phase 3 — Aggregator scrapers...")

        for source in ALL_AGGREGATOR_SOURCES + ALL_BULLETIN_SOURCES:
            try:
                if source["source_type"] == "aggregator":
                    tenders = await sa_tenders.scrape_aggregator(client, source)
                else:
                    tenders = await tender_bulletins.scrape_source(client, source)

                new = upsert_tenders(db, tenders)
                total_new += new
                scrape_report.append({"source": source["name"], "scraped": len(tenders), "new": new, "status": "ok"})
                update_scraper_status(db, source["name"], new)
            except Exception as e:
                db.rollback()
                scrape_report.append({"source": source["name"], "scraped": 0, "new": 0, "status": "error"})
                update_scraper_status(db, source["name"], 0, str(e))
                logger.error(f"[ENGINE] {source['name']} aggregator error: {e}")

        # ── Phase 3b: JavaScript‑rendered sites (Playwright) ─────────────────
        logger.info("[ENGINE] Phase 3b — JavaScript scrapers...")
        for source in ALL_JS_SOURCES:
            try:
                tenders = await js_scraper.scrape_js_source(source)
                new = upsert_tenders(db, tenders)
                total_new += new
                scrape_report.append({"source": source["name"], "scraped": len(tenders), "new": new, "status": "ok"})
                update_scraper_status(db, source["name"], new)
            except Exception as e:
                db.rollback()
                scrape_report.append({"source": source["name"], "scraped": 0, "new": 0, "status": "error"})
                update_scraper_status(db, source["name"], 0, str(e))
                logger.error(f"[ENGINE] {source['name']} JS scraper error: {e}")

    _print_report(crawl_index, scrape_report, db)

    # ── Notifications ─────────────────────────────────────────────────────────
    if total_new > 0:
        try:
            from notifications import send_admin_notification, send_user_alerts
            send_admin_notification(total_new)
            send_user_alerts(db)
        except Exception as e:
            logger.warning(f"[ENGINE] Notification error: {e}")

    db.close()
    logger.info(f"[ENGINE] ── Cycle complete — {total_new} new tenders ──────")
    return total_new