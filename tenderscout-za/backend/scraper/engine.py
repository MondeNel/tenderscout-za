"""
scraper/engine.py
-----------------
Orchestrates all scraping in a single cycle:

  Phase 1 — HTML sites:      scrape all active HTML sources directly from registry
  Phase 2 — Playwright sites: EasyTenders, SA-Tenders, eTenders (Playwright)

The old crawler-first approach is removed. Each site is scraped directly at
its configured URL. This is simpler, faster, and works for all 36 HTML sites.
"""

import logging
import httpx
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
import models
from scraper.utils import get_headers
from scraper.sites.registry import get_html_sources, get_playwright_sources
from scraper.sites import city_portals, js_scraper
from scraper.sites import etenders as etenders_scraper
from scraper.sites import sa_tenders
from typing import List, Dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    """Insert new tenders, skip duplicates by content_hash. Returns new count."""
    new_count = 0
    for t in tenders:
        if not t.get("content_hash") or not t.get("title"):
            continue
        try:
            exists = db.query(models.Tender).filter(
                models.Tender.content_hash == t["content_hash"]
            ).first()
            if not exists:
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
        status.last_scraped_at    = datetime.utcnow()
        status.last_result_count  = count
        status.last_error         = error
        status.is_healthy         = (error is None)
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
    print(f"  {'Source':<36} {'Scraped':>8} {'New':>6}   {'Status'}")
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
    db            = SessionLocal()
    report        = []
    total_new     = 0
    html_sources  = get_html_sources()
    pw_sources    = get_playwright_sources()

    # ── Phase 1: All HTML sources — direct scrape, no crawler needed ──────────
    logger.info(f"[ENGINE] Phase 1 — Scraping {len(html_sources)} HTML sources...")

    async with httpx.AsyncClient(
        timeout=30,
        headers=get_headers(),
        follow_redirects=True,
        verify=False,
    ) as client:

        for source in html_sources:
            name = source["name"]
            try:
                tenders = await city_portals.scrape_city(client, source)
                new     = upsert_tenders(db, tenders)
                total_new += new
                report.append({
                    "source":  name,
                    "scraped": len(tenders),
                    "new":     new,
                    "status":  "ok",
                })
                update_scraper_status(db, name, new)
                logger.info(f"[ENGINE] {name}: {len(tenders)} scraped, {new} new")
            except Exception as e:
                db.rollback()
                report.append({"source": name, "scraped": 0, "new": 0, "status": "error"})
                update_scraper_status(db, name, 0, str(e))
                logger.error(f"[ENGINE] {name} failed: {e}")

    # ── Phase 2: Playwright sources ───────────────────────────────────────────
    logger.info(f"[ENGINE] Phase 2 — Scraping {len(pw_sources)} Playwright sources...")

    for source in pw_sources:
        name         = source["name"]
        scrape_type  = source.get("scrape_type", "")

        try:
            if scrape_type == "etenders_playwright":
                tenders = await etenders_scraper.scrape_etenders()

            elif scrape_type == "js_playwright" and "sa-tenders" in source["url"]:
                tenders = await sa_tenders.scrape_sa_tenders()

            elif scrape_type == "js_playwright" and "dkm.gov.za" in source["url"]:
                # Dawid Kruiper — JS-rendered bids table, scrape with generic Playwright
                tenders = await js_scraper.scrape_js_source(source)

            elif scrape_type == "js_playwright":
                tenders = await js_scraper.scrape_js_source(source)

            else:
                logger.warning(f"[ENGINE] Unknown playwright type '{scrape_type}' for {name}")
                tenders = []

            new        = upsert_tenders(db, tenders)
            total_new += new
            report.append({
                "source":  name,
                "scraped": len(tenders),
                "new":     new,
                "status":  "ok",
            })
            update_scraper_status(db, name, new)
            logger.info(f"[ENGINE] {name}: {len(tenders)} scraped, {new} new")

        except Exception as e:
            db.rollback()
            report.append({"source": name, "scraped": 0, "new": 0, "status": "error"})
            update_scraper_status(db, name, 0, str(e))
            logger.error(f"[ENGINE] {name} failed: {e}")

    _print_report(report, db)

    # ── Notifications ─────────────────────────────────────────────────────────
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