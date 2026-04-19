"""
scraper/engine.py
-----------------
Orchestrates all scraping. Two phases:
  Phase 1 — 35 HTML sources (concurrent, fast ~20s)
  Phase 2 — 4 Playwright sources (sequential, slower ~10 min)

Data hygiene:
  - Tenders with closing dates in the past are marked inactive before each cycle
  - content_hash deduplication prevents double-inserts
  - SCRAPE_INTERVAL_SECONDS controls cycle frequency (default 6h)
"""

import logging
import httpx
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
import models
from scraper.utils import get_headers, is_closing_date_expired
from scraper.sites.registry import get_html_sources, get_playwright_sources
from scraper.sites import city_portals, js_scraper, sa_tenders
from scraper.sites import etenders as etenders_scraper
from typing import List, Dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def mark_expired_tenders(db: Session) -> int:
    """Mark tenders with past closing dates as inactive."""
    count = 0
    tenders = db.query(models.Tender).filter(
        models.Tender.is_active == True,
        models.Tender.closing_date.isnot(None),
        models.Tender.closing_date != "",
    ).all()
    for t in tenders:
        if is_closing_date_expired(t.closing_date):
            t.is_active = False
            count += 1
    if count:
        db.commit()
    return count


def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    new_count = 0
    for t in tenders:
        if not t.get("content_hash") or not t.get("title"):
            continue
        # Skip if closing date is already past
        if t.get("closing_date") and is_closing_date_expired(t["closing_date"]):
            continue
        try:
            exists = db.query(models.Tender).filter(
                models.Tender.content_hash == t["content_hash"]
            ).first()
            if exists:
                # Re-activate if it was previously marked inactive
                if not exists.is_active:
                    exists.is_active = True
                    db.commit()
            else:
                db.add(models.Tender(**{
                    k: v for k, v in t.items() if hasattr(models.Tender, k)
                }))
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
        status.last_scraped_at   = datetime.utcnow()
        status.last_result_count = count
        status.last_error        = error
        status.is_healthy        = (error is None)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] Status update failed for {site_name}: {e}")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _print_report(report: List[Dict], db: Session):
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    width = 76
    print("\n" + "=" * width)
    print(f"  TENDERSCOUT ZA  |  {now}")
    print("=" * width)
    print(f"  {'Source':<36} {'Scraped':>8} {'New':>6}   Status")
    print("-" * width)
    total_scraped = total_new = 0
    for row in report:
        icon       = "[+]" if row["new"] > 0 else "[ ]" if row["status"] == "ok" else "[!]"
        status_str = "OK" if row["status"] == "ok" else "FAILED"
        print(f"  {icon} {row['source']:<33} {row['scraped']:>8} {row['new']:>6}   {status_str}")
        total_scraped += row["scraped"]
        total_new     += row["new"]
    print("-" * width)
    print(f"  {'TOTAL':<36} {total_scraped:>8} {total_new:>6}")
    print("=" * width)
    try:
        db_total  = db.query(models.Tender).count()
        db_active = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        print(f"  DB: {db_total} total  |  {db_active} active")
    except Exception:
        pass
    print("=" * width + "\n")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_scraper():
    logger.info("[ENGINE] ── Cycle start ──────────────────────────────────────")
    db           = SessionLocal()
    report       = []
    total_new    = 0
    html_sources = get_html_sources()
    pw_sources   = get_playwright_sources()

    # ── Step 0: Mark expired tenders inactive ─────────────────────────────────
    expired = mark_expired_tenders(db)
    if expired:
        logger.info(f"[ENGINE] Marked {expired} expired tenders as inactive")

    # ── Phase 1: HTML sources ─────────────────────────────────────────────────
    logger.info(f"[ENGINE] Phase 1 — {len(html_sources)} HTML sources...")

    async with httpx.AsyncClient(
        timeout=30, headers=get_headers(), follow_redirects=True, verify=False
    ) as client:
        for source in html_sources:
            name = source["name"]
            try:
                tenders = await city_portals.scrape_city(client, source)
                new     = upsert_tenders(db, tenders)
                total_new += new
                report.append({"source": name, "scraped": len(tenders), "new": new, "status": "ok"})
                update_scraper_status(db, name, new)
            except Exception as e:
                db.rollback()
                report.append({"source": name, "scraped": 0, "new": 0, "status": "error"})
                update_scraper_status(db, name, 0, str(e))
                logger.error(f"[ENGINE] {name} failed: {e}")

    # ── Phase 2: Playwright sources ───────────────────────────────────────────
    logger.info(f"[ENGINE] Phase 2 — {len(pw_sources)} Playwright sources...")

    for source in pw_sources:
        name        = source["name"]
        scrape_type = source.get("scrape_type", "")
        try:
            if scrape_type == "etenders_playwright":
                tenders = await etenders_scraper.scrape_etenders()
            elif "sa-tenders" in source.get("url", ""):
                tenders = await sa_tenders.scrape_sa_tenders()
            else:
                # EasyTenders and others
                tenders = await js_scraper.scrape_js_source(source)

            new        = upsert_tenders(db, tenders)
            total_new += new
            report.append({"source": name, "scraped": len(tenders), "new": new, "status": "ok"})
            update_scraper_status(db, name, new)
            logger.info(f"[ENGINE] {name}: {len(tenders)} scraped, {new} new")
        except Exception as e:
            db.rollback()
            report.append({"source": name, "scraped": 0, "new": 0, "status": "error"})
            update_scraper_status(db, name, 0, str(e))
            logger.error(f"[ENGINE] {name} failed: {e}")

    _print_report(report, db)

    if total_new > 0:
        try:
            from notifications import send_admin_notification, send_user_alerts
            send_admin_notification(total_new)
            send_user_alerts(db)
        except Exception as e:
            logger.warning(f"[ENGINE] Notification error: {e}")

    db.close()
    logger.info(f"[ENGINE] ── Cycle complete — {total_new} new tenders ──────────")
    return total_new