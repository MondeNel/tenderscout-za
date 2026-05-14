"""
scraper/engine.py — High-Performance Orchestrator (2026 Edition)
==============================================================
Optimized 4-Phase pipeline for South African Tender acquisition.

Features:
  - Atomic Batch Upserts (SQLAlchemy optimized)
  - Concurrent City Scraping (Semaphore-guarded)
  - Pre-insertion filtering (Expired/Invalid data)
  - Request-state caching for database efficiency
"""

import asyncio
import logging
import hashlib
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set, Any

from sqlalchemy.orm import Session
from database import SessionLocal
import models
from scraper.utils import get_headers
from scraper.crawler import run_crawler
from scraper.sites import city_portals

logger = logging.getLogger(__name__)

# =============================================================================
# DATA INTEGRITY & SOURCE MAPPING
# =============================================================================

def _build_source_map() -> Dict[str, Dict]:
    """Aggregates all site definitions into a unified lookup table."""
    m: Dict[str, Dict] = {}
    
    # Load City Portals
    for c in city_portals.CITY_PORTALS:
        m[c["name"]] = {**c, "source_type": "city"}
    
    # Load Aggregators
    try:
        from scraper.sites.sa_tenders import AGGREGATORS
        for a in AGGREGATORS:
            m[a["name"]] = {**a, "source_type": "aggregator"}
    except ImportError as e:
        logger.warning(f"[ENGINE] sa_tenders module missing: {e}")

    # Load Bulletins
    try:
        from scraper.sites.tender_bulletins import SOURCES
        for s in SOURCES:
            m[s["name"]] = {**s, "source_type": "bulletin"}
    except ImportError as e:
        logger.warning(f"[ENGINE] tender_bulletins module missing: {e}")
        
    return m

# =============================================================================
# DATABASE OPERATIONS (PERFORMANCE TUNED)
# =============================================================================

def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    """
    High-speed batch insertion. Filters duplicates and expired tenders 
    before hitting the DB to minimize transaction overhead.
    """
    if not tenders:
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    valid_batch: List[models.Tender] = []
    
    # 1. Deduplicate input and filter expired
    seen_hashes = set()
    unique_tenders = []
    
    for t in tenders:
        h = t.get("content_hash")
        title = t.get("title")
        expiry = t.get("expiry_date")

        # Basic Validation
        if not h or not title: continue
        if h in seen_hashes: continue
        
        # Pre-filter expired tenders (Save DB space)
        if expiry and expiry < now:
            continue

        seen_hashes.add(h)
        unique_tenders.append(t)

    if not unique_tenders:
        return 0

    # 2. Bulk check against DB (The 'Exists' Query)
    incoming_hashes = [t["content_hash"] for t in unique_tenders]
    existing_hashes = {
        h[0] for h in db.query(models.Tender.content_hash)
        .filter(models.Tender.content_hash.in_(incoming_hashes))
        .all()
    }

    # 3. Construct Model Objects
    for t in unique_tenders:
        if t["content_hash"] in existing_hashes:
            continue
            
        # Clean dict to match model attributes
        clean_data = {
            k: v for k, v in t.items() 
            if hasattr(models.Tender, k) and v is not None
        }
        valid_batch.append(models.Tender(**clean_data))

    # 4. Atomic Commit
    if valid_batch:
        try:
            db.add_all(valid_batch)
            db.commit()
            return len(valid_batch)
        except Exception as e:
            db.rollback()
            logger.error(f"[ENGINE] Batch commit failed: {e}")
            return 0
    return 0

def update_scraper_status(db: Session, site_name: str, count: int, error: str = None):
    """Updates heartbeat for specific scrapers to track health."""
    try:
        status = db.query(models.ScraperStatus).filter_by(site_name=site_name).first()
        if not status:
            status = models.ScraperStatus(site_name=site_name)
            db.add(status)
        
        status.last_scraped_at = datetime.utcnow()
        status.last_result_count = count
        status.last_error = error[:255] if error else None # Truncate for DB safety
        status.is_healthy = (error is None)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] Status update fail for {site_name}: {e}")

def mark_urls_scraped(db: Session, urls: List[str]):
    """Syncs the Crawler results with the Scraper results."""
    if not urls: return
    hashes = [hashlib.md5(u.encode()).hexdigest() for u in urls]
    try:
        db.query(models.CrawlResult).filter(
            models.CrawlResult.url_hash.in_(hashes)
        ).update(
            {"scraped_at": datetime.utcnow(), "scrape_success": True},
            synchronize_session=False
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] URL sync fail: {e}")

# =============================================================================
# SCRAPING PHASES
# =============================================================================

async def _scrape_city_parallel(client: httpx.AsyncClient, site_name: str, 
                               urls: List[Dict], source: Dict, db: Session) -> Dict:
    """Handles parallel URL scraping for a single city site."""
    sem = asyncio.Semaphore(5) # Conservative per-site limit
    site_tenders = []
    scraped_urls = []
    
    async def _task(url_entry: Dict):
        async with sem:
            try:
                # Merge source config with specific URL
                config = {**source, "url": url_entry["url"]}
                results = await city_portals.scrape_city(client, config)
                return url_entry["url"], results
            except Exception as e:
                logger.debug(f"[ENGINE] Error on {url_entry['url']}: {e}")
                return url_entry["url"], None

    tasks = [_task(u) for u in urls]
    results = await asyncio.gather(*tasks)

    for url, res in results:
        if res:
            site_tenders.extend(res)
            scraped_urls.append(url)

    new_count = upsert_tenders(db, site_tenders)
    mark_urls_scraped(db, scraped_urls)
    
    return {"scraped": len(site_tenders), "new": new_count}

# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

async def run_scraper() -> int:
    logger.info("[ENGINE] Starting Full Scraper Cycle...")
    db = SessionLocal()
    source_map = _build_source_map()
    total_new = 0
    report_data = []

    try:
        # --- PHASE 1: DISCOVERY ---
        crawl_index = await run_crawler(db, polite_delay=0.3)

        # --- NETWORK CLIENT SETUP ---
        async with httpx.AsyncClient(
            timeout=45,
            headers=get_headers(),
            follow_redirects=True,
            verify=False, # Necessary for some older ZA gov certs
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20)
        ) as client:

            # --- PHASE 2: CRAWLED CITIES (PARALLEL) ---
            for site_name, urls in crawl_index.items():
                source = source_map.get(site_name)
                if not source or source.get("source_type") != "city": continue

                res = await _scrape_city_parallel(client, site_name, urls, source, db)
                total_new += res["new"]
                report_data.append({
                    "source": site_name, "scraped": res["scraped"], 
                    "new": res["new"], "status": "ok"
                })
                update_scraper_status(db, site_name, res["new"])

            # --- PHASE 3: STATIC SOURCES ---
            for name, src in source_map.items():
                if src.get("source_type") not in ("aggregator", "bulletin"): continue
                if src.get("js_required"): continue
                
                try:
                    if src["source_type"] == "aggregator":
                        from scraper.sites.sa_tenders import scrape_aggregator
                        tenders = await scrape_aggregator(client, src)
                    else:
                        from scraper.sites.tender_bulletins import scrape_source
                        tenders = await scrape_source(client, src)

                    new = upsert_tenders(db, tenders)
                    total_new += new
                    report_data.append({"source": name, "scraped": len(tenders), "new": new, "status": "ok"})
                    update_scraper_status(db, name, new)
                except Exception as e:
                    report_data.append({"source": name, "scraped": 0, "new": 0, "status": "error"})
                    update_scraper_status(db, name, 0, str(e))

        # --- PHASE 4: JS ENGINES (PLAYWRIGHT) ---
        # Note: These handle their own browser context internally
        for js_task in ["JS Aggregators", "eTenders National"]:
            try:
                if "National" in js_task:
                    from scraper.sites.etenders import scrape_etenders
                    tenders = await scrape_etenders()
                else:
                    from scraper.sites.js_scraper import scrape_all_js_sources
                    tenders = await scrape_all_js_sources()

                new = upsert_tenders(db, tenders)
                total_new += new
                report_data.append({"source": js_task, "scraped": len(tenders), "new": new, "status": "ok"})
            except Exception as e:
                logger.error(f"[ENGINE] {js_task} failed: {e}")
                report_data.append({"source": js_task, "scraped": 0, "new": 0, "status": "error"})

        # --- FINALIZATION ---
        if total_new > 0:
            from notifications import send_admin_notification, send_user_alerts
            send_admin_notification(total_new)
            send_user_alerts(db)

    finally:
        db.close()
        logger.info(f"[ENGINE] Cycle Complete. {total_new} new tenders found.")

    return total_new