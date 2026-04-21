"""
scraper/engine.py — Main Orchestrator
======================================
4-Phase pipeline that coordinates crawling and scraping of tender sources.

PIPELINE FLOW:
    Phase 1 — BFS Crawler
        Discovers live tender URLs by crawling from seed URLs.
        Results saved to CrawlResult table.
        
    Phase 2 — City Portals (HTML)
        Takes crawler-discovered URLs and scrapes them using city_portals.py.
        Each URL is treated as a tender listing page.
        
    Phase 3 — Static Aggregators & Bulletins (HTML)
        Scrapes configured aggregator/bulletin sources directly (no crawler).
        Uses sa_tenders.py and tender_bulletins.py.
        
    Phase 4 — JavaScript-Rendered Sites (Playwright)
        Scrapes sites requiring a real browser.
        Uses js_scraper.py (EasyTenders, sa-tenders, OnlineTenders)
        and etenders.py (eTenders Portal).

All extracted tenders are upserted to the Tender table using content_hash
for deduplication. ScraperStatus table tracks health of each source.

ARCHITECTURE NOTE:
    Currently, ONLY Phase 2 uses crawler-discovered URLs.
    Phase 3 and 4 scrape from hardcoded URLs in their respective configs.
    
    TODO: Extend crawler integration to Phase 3/4 for better coverage,
    OR ensure Phase 3/4 scrapers are comprehensive enough on their own.
"""
import logging
import httpx
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
import models
from scraper.utils import get_headers
from scraper.crawler import run_crawler
from scraper.sites import city_portals
from typing import List, Dict, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# SOURCE MAP BUILDER
# =============================================================================
# Builds a unified dictionary of all scraping sources for lookup by name.
# This allows the engine to find source configurations across all modules.
# =============================================================================

def _build_source_map() -> Dict[str, Dict]:
    """
    Build a unified source map from all scraper modules.
    
    Returns:
        Dictionary mapping source name → source configuration dict.
        Each dict includes a 'source_type' field: 'city', 'aggregator', or 'bulletin'.
    """
    m: Dict[str, Dict] = {}
    
    # City portals (from city_portals.py)
    for c in city_portals.CITY_PORTALS:
        m[c["name"]] = {**c, "source_type": "city"}
    
    # Aggregators (from sa_tenders.py)
    try:
        from scraper.sites.sa_tenders import AGGREGATORS
        for a in AGGREGATORS:
            m[a["name"]] = {**a, "source_type": "aggregator"}
    except Exception as e:
        logger.warning(f"[ENGINE] sa_tenders load error: {e}")
    
    # Bulletins (from tender_bulletins.py)
    try:
        from scraper.sites.tender_bulletins import SOURCES
        for s in SOURCES:
            m[s["name"]] = {**s, "source_type": "bulletin"}
    except Exception as e:
        logger.warning(f"[ENGINE] tender_bulletins load error: {e}")
    
    return m


# =============================================================================
# DATABASE HELPERS
# =============================================================================

def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    """
    Insert new tenders into the database, skipping duplicates.
    Returns the number of NEW tenders actually inserted.
    """
    if not tenders:
        return 0
        
    new_count = 0
    skipped_duplicates = 0
    skipped_invalid = 0
    
    for t in tenders:
        try:
            # Validate required fields
            content_hash = t.get("content_hash")
            title = t.get("title")
            
            if not content_hash or not title:
                skipped_invalid += 1
                continue
                
            # Check if already exists
            exists = db.query(models.Tender).filter(
                models.Tender.content_hash == content_hash
            ).first()
            
            if exists:
                skipped_duplicates += 1
                continue
                
            # Build valid fields (only those in the model)
            valid = {}
            for k, v in t.items():
                if hasattr(models.Tender, k) and v is not None and v != "":
                    valid[k] = v
                    
            # Create and commit
            new_tender = models.Tender(**valid)
            db.add(new_tender)
            db.commit()
            db.refresh(new_tender)  # Verify it was saved
            new_count += 1
            
        except IntegrityError:
            db.rollback()
            skipped_duplicates += 1
        except Exception as e:
            db.rollback()
            logger.error(f"[ENGINE] Insert failed: {e}")
            
    logger.info(f"[ENGINE] Upsert summary: {new_count} new, {skipped_duplicates} duplicates, {skipped_invalid} invalid")
    return new_count


def update_scraper_status(db: Session, site_name: str, count: int, error: str = None):
    """
    Update the ScraperStatus table with the results of a scrape run.
    
    Tracks:
        - Last scraped timestamp
        - Number of tenders found
        - Error message (if any)
        - Health status
        
    Args:
        db: SQLAlchemy database session
        site_name: Name of the source that was scraped
        count: Number of tenders extracted (0 if error)
        error: Error message if scrape failed, None if successful
    """
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
        logger.error(f"[ENGINE] Status update failed [{site_name}]: {e}")


def mark_crawled_urls_as_scraped(db: Session, urls: List[str]) -> int:
    """
    Mark crawler-discovered URLs as having been scraped.
    
    This prevents re-scraping the same URLs in future runs.
    
    Args:
        db: SQLAlchemy database session
        urls: List of URLs that were successfully scraped
        
    Returns:
        Number of records updated
    """
    if not urls:
        return 0
        
    try:
        import hashlib
        updated = 0
        
        for url in urls:
            url_hash = hashlib.md5(url.encode()).hexdigest()
            result = db.query(models.CrawlResult).filter(
                models.CrawlResult.url_hash == url_hash
            ).first()
            
            if result:
                result.scraped_at = datetime.utcnow()
                result.scrape_success = True
                updated += 1
                
        db.commit()
        return updated
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] Failed to mark URLs as scraped: {e}")
        return 0


# =============================================================================
# REPORT GENERATOR
# =============================================================================

def _print_report(crawler_summary: Dict, scrape_report: List[Dict], db: Session):
    """
    Print a formatted summary report of the scraping run.
    
    Args:
        crawler_summary: Dict mapping site_name → list of discovered URLs
        scrape_report: List of dicts with scraping results per source
        db: Database session for querying totals
    """
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    width = 78
    
    print("\n" + "=" * width)
    print(f"  TENDERSCOUT ZA  |  {now}")
    print("=" * width)

    # Phase 1 — Crawler summary
    print("  PHASE 1 — CRAWLER (Discovered URLs)")
    print(f"  {'Site':<42} {'URLs':>8}")
    print("-" * width)
    total_urls = 0
    for site, urls in crawler_summary.items():
        n = len(urls)
        print(f"     {site:<39} {n:>8}")
        total_urls += n
    print(f"  {'TOTAL':<42} {total_urls:>8}")
    print()

    # Phases 2-4 — Scraper summary
    print("  PHASES 2-4 — SCRAPER (Extracted Tenders)")
    print(f"  {'Source':<38} {'Scraped':>8} {'New':>6}  Status")
    print("-" * width)
    
    total_scraped = 0
    total_new = 0
    
    for row in scrape_report:
        status_str = "OK" if row["status"] == "ok" else "FAILED"
        icon = "[+]" if row["new"] > 0 else "[ ]" if row["status"] == "ok" else "[!]"
        print(f"  {icon} {row['source']:<35} {row['scraped']:>8} {row['new']:>6}  {status_str}")
        total_scraped += row["scraped"]
        total_new     += row["new"]
        
    print("-" * width)
    print(f"  {'TOTAL':<38} {total_scraped:>8} {total_new:>6}")
    print("=" * width)
    
    # Database totals
    try:
        db_total = db.query(models.Tender).count()
        active   = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        expired  = db_total - active
        print(f"  DB: {db_total} total tenders  ({active} active, {expired} expired)")
    except Exception:
        pass
        
    print("=" * width + "\n")


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

async def run_scraper() -> int:
    """
    Main entry point — runs the complete 4-phase scraping pipeline.
    
    Returns:
        Total number of new tenders added to the database
    """
    logger.info("[ENGINE] ═══════════════════════════════════════════════════════")
    logger.info("[ENGINE] ── Scraper Cycle Start ──────────────────────────────")
    logger.info("[ENGINE] ═══════════════════════════════════════════════════════")
    
    db         = SessionLocal()
    source_map = _build_source_map()
    scrape_report: List[Dict] = []
    total_new = 0
    scraped_urls: Set[str] = set()

    # =========================================================================
    # PHASE 1: BFS CRAWLER — Discover live tender URLs
    # =========================================================================
    logger.info("[ENGINE] Phase 1 — BFS Crawler (discovering URLs)...")
    
    try:
        crawl_index = await run_crawler(db)
        total_urls = sum(len(urls) for urls in crawl_index.values())
        logger.info(f"[ENGINE] Phase 1 complete: {total_urls} URLs discovered across {len(crawl_index)} sites")
    except Exception as e:
        logger.error(f"[ENGINE] Phase 1 failed: {e}")
        crawl_index = {}

    # =========================================================================
    # PHASE 2: CITY PORTALS — Scrape crawler-discovered URLs
    # =========================================================================
    logger.info("[ENGINE] Phase 2 — City Portals (scraping discovered URLs)...")
    
    async with httpx.AsyncClient(
        timeout=30, 
        headers=get_headers(), 
        follow_redirects=True, 
        verify=False
    ) as client:

        for site_name, verified_urls in crawl_index.items():
            source = source_map.get(site_name)
            
            # Only process city-type sources
            if not source or source.get("source_type") != "city":
                continue
                
            if not verified_urls:
                scrape_report.append({
                    "source": site_name, 
                    "scraped": 0, 
                    "new": 0, 
                    "status": "ok"
                })
                continue
                
            try:
                site_tenders = []
                site_scraped_urls = []
                
                # Scrape each discovered URL
                for entry in verified_urls:
                    url = entry["url"]
                    city_override = {**source, "url": url}
                    
                    try:
                        tenders = await city_portals.scrape_city(client, city_override)
                        if tenders:
                            site_tenders.extend(tenders)
                            site_scraped_urls.append(url)
                    except Exception as e:
                        logger.warning(f"[ENGINE] {url}: {e}")
                
                # Save to database
                new = upsert_tenders(db, site_tenders)
                total_new += new
                
                # Mark URLs as scraped
                if site_scraped_urls:
                    mark_crawled_urls_as_scraped(db, site_scraped_urls)
                    scraped_urls.update(site_scraped_urls)
                
                scrape_report.append({
                    "source": site_name, 
                    "scraped": len(site_tenders), 
                    "new": new, 
                    "status": "ok"
                })
                update_scraper_status(db, site_name, new)
                
                if site_tenders:
                    logger.info(f"[ENGINE] {site_name}: {len(site_tenders)} tenders ({new} new)")
                    
            except Exception as e:
                scrape_report.append({
                    "source": site_name, 
                    "scraped": 0, 
                    "new": 0, 
                    "status": "error"
                })
                update_scraper_status(db, site_name, 0, str(e))
                logger.error(f"[ENGINE] {site_name}: {e}")

        # =====================================================================
        # PHASE 3: STATIC AGGREGATORS & BULLETINS
        # =====================================================================
        logger.info("[ENGINE] Phase 3 — Static Aggregators & Bulletins...")
        
        for src in source_map.values():
            src_type = src.get("source_type")
            
            # Only process aggregator and bulletin types
            if src_type not in ("aggregator", "bulletin"):
                continue
                
            # Skip JS-required sites (handled in Phase 4)
            if src.get("js_required"):
                continue
                
            try:
                if src_type == "aggregator":
                    from scraper.sites.sa_tenders import scrape_aggregator
                    tenders = await scrape_aggregator(client, src)
                else:
                    from scraper.sites.tender_bulletins import scrape_source
                    tenders = await scrape_source(client, src)
                    
                new = upsert_tenders(db, tenders)
                total_new += new
                
                scrape_report.append({
                    "source": src["name"], 
                    "scraped": len(tenders), 
                    "new": new, 
                    "status": "ok"
                })
                update_scraper_status(db, src["name"], new)
                
                if tenders:
                    logger.info(f"[ENGINE] {src['name']}: {len(tenders)} tenders ({new} new)")
                else:
                    logger.warning(f"[ENGINE] {src['name']}: 0 tenders — may need selector updates")
                    
            except Exception as e:
                db.rollback()
                scrape_report.append({
                    "source": src["name"], 
                    "scraped": 0, 
                    "new": 0, 
                    "status": "error"
                })
                update_scraper_status(db, src["name"], 0, str(e))
                logger.error(f"[ENGINE] {src['name']}: {e}")

    # =========================================================================
    # PHASE 4: JAVASCRIPT-RENDERED SITES (Playwright)
    # =========================================================================
    logger.info("[ENGINE] Phase 4 — JS Sites (Playwright required)...")

    # -------------------------------------------------------------------------
    # 4a — JS Aggregators (EasyTenders, sa-tenders, OnlineTenders)
    # -------------------------------------------------------------------------
    try:
        from scraper.sites.js_scraper import scrape_all_js_sources
        js_tenders = await scrape_all_js_sources()
        new = upsert_tenders(db, js_tenders)
        total_new += new
        
        scrape_report.append({
            "source": "JS Sites (EasyTenders, etc.)", 
            "scraped": len(js_tenders), 
            "new": new, 
            "status": "ok"
        })
        logger.info(f"[ENGINE] JS aggregators: {len(js_tenders)} tenders ({new} new)")
        
    except Exception as e:
        scrape_report.append({
            "source": "JS Sites", 
            "scraped": 0, 
            "new": 0, 
            "status": "error"
        })
        logger.error(f"[ENGINE] JS scraper error: {e}")

    # -------------------------------------------------------------------------
    # 4b — eTenders Portal (Official government portal)
    # -------------------------------------------------------------------------
    try:
        from scraper.sites.etenders import scrape_etenders
        et_tenders = await scrape_etenders()
        new = upsert_tenders(db, et_tenders)
        total_new += new
        
        scrape_report.append({
            "source": "eTenders Portal (National)", 
            "scraped": len(et_tenders), 
            "new": new, 
            "status": "ok"
        })
        logger.info(f"[ENGINE] eTenders: {len(et_tenders)} tenders ({new} new)")
        
    except Exception as e:
        scrape_report.append({
            "source": "eTenders Portal (National)", 
            "scraped": 0, 
            "new": 0, 
            "status": "error"
        })
        logger.error(f"[ENGINE] eTenders error: {e}")

    # =========================================================================
    # REPORT & NOTIFICATIONS
    # =========================================================================
    _print_report(crawl_index, scrape_report, db)

    if total_new > 0:
        try:
            from notifications import send_admin_notification, send_user_alerts
            send_admin_notification(total_new)
            send_user_alerts(db)
            logger.info(f"[ENGINE] Notifications sent for {total_new} new tenders")
        except Exception as e:
            logger.warning(f"[ENGINE] Notification error: {e}")

    db.close()
    
    logger.info("[ENGINE] ═══════════════════════════════════════════════════════")
    logger.info(f"[ENGINE] ── Cycle Complete — {total_new} new tenders added ───")
    logger.info("[ENGINE] ═══════════════════════════════════════════════════════")
    
    return total_new


# =============================================================================
# TODO: IMPROVEMENTS NEEDED
# =============================================================================
# 1. Phase 3 sources (OnlineTenders, sa-tenders, TenderAlerts) return 0 tenders.
#    → Debug selectors in sa_tenders.py and tender_bulletins.py
#
# 2. Crawler discovers many URLs that are never scraped (Phase 3/4 don't use them).
#    → Consider extending crawler integration to Phase 3/4 sources
#
# 3. No detail page scraping — only listing pages are scraped.
#    → Add a Phase 5 that visits CrawlResult URLs and extracts full details
#
# 4. tenderbulletins.co.za returns 403.
#    → Move to js_required or implement better headers/retry logic
# =============================================================================