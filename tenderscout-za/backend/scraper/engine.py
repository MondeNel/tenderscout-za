"""
scraper/engine.py — Scraper Orchestrator
=========================================
4-phase pipeline for South African tender acquisition.

Phases:
  1. Discovery  — BFS crawler finds tender URLs on city/gov portals
  2. City sites — parallel scraping of crawled URLs
  3. Static     — aggregators and bulletin boards (plain HTTP)
  4. JS engines — Playwright-based scrapers for JS-heavy sites
"""

import asyncio
import logging
import hashlib
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set

from sqlalchemy.orm import Session
from database import SessionLocal
import models
from scraper.utils import get_headers
from scraper.crawler import run_crawler
from scraper.sites import city_portals

logger = logging.getLogger(__name__)

# =============================================================================
# SAFE MODEL FIELDS
# =============================================================================
# Explicit allowlist of fields that scrapers are permitted to set on Tender.
# FIX: Previous version used hasattr(models.Tender, k) which allowed scrapers
# to overwrite id, content_hash, scraped_at, is_active etc.

_TENDER_SAFE_FIELDS: frozenset[str] = frozenset([
    "title", "description", "issuing_body", "province", "municipality",
    "town", "industry_category", "closing_date", "closing_date_parsed",
    "posted_date", "source_url", "source_site", "reference_number",
    "contact_info", "content_hash", "document_url", "lat", "lng",
])

# SSL-exempt domains — broken/expired certs on known SA gov sites
_SSL_EXEMPT_DOMAINS: frozenset[str] = frozenset([
    "etenders.gov.za",
])


# =============================================================================
# SOURCE MAP
# =============================================================================

def _build_source_map() -> Dict[str, Dict]:
    """Aggregate all site definitions into a unified lookup table."""
    m: Dict[str, Dict] = {}

    for c in city_portals.CITY_PORTALS:
        m[c["name"]] = {**c, "source_type": "city"}

    try:
        from scraper.sites.sa_tenders import AGGREGATORS
        for a in AGGREGATORS:
            m[a["name"]] = {**a, "source_type": "aggregator"}
    except ImportError as e:
        logger.warning(f"[ENGINE] sa_tenders module missing: {e}")

    try:
        from scraper.sites.tender_bulletins import SOURCES
        for s in SOURCES:
            m[s["name"]] = {**s, "source_type": "bulletin"}
    except ImportError as e:
        logger.warning(f"[ENGINE] tender_bulletins module missing: {e}")

    return m


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    """
    Batch-insert new tenders, skipping duplicates and expired entries.

    FIX: On batch commit failure, falls back to inserting one-by-one so a
    single bad row doesn't silently discard the entire batch.

    FIX: Expiry comparison uses timezone-aware datetimes throughout to
    prevent TypeError when scraped dates are timezone-aware but `now` wasn't.

    FIX: Field allowlist (_TENDER_SAFE_FIELDS) prevents scrapers from
    overwriting id, scraped_at, is_active, or other internal fields.
    """
    if not tenders:
        return 0

    now = datetime.now(timezone.utc)

    # 1. Deduplicate input and filter invalid/expired
    seen: Set[str] = set()
    unique: List[Dict] = []

    for t in tenders:
        h     = t.get("content_hash")
        title = t.get("title", "").strip()
        if not h or not title:
            continue
        if h in seen:
            continue

        # FIX: Normalise expiry to timezone-aware before comparing
        expiry = t.get("expiry_date") or t.get("closing_date_parsed")
        if expiry:
            if isinstance(expiry, datetime):
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry < now:
                    continue  # Skip expired tenders

        seen.add(h)
        unique.append(t)

    if not unique:
        return 0

    # 2. Bulk check existing hashes — avoid inserting duplicates
    incoming_hashes = [t["content_hash"] for t in unique]
    existing_hashes: Set[str] = {
        row[0] for row in
        db.query(models.Tender.content_hash)
        .filter(models.Tender.content_hash.in_(incoming_hashes))
        .all()
    }

    # 3. Build model objects using safe field allowlist
    batch: List[models.Tender] = []
    for t in unique:
        if t["content_hash"] in existing_hashes:
            continue
        clean = {k: v for k, v in t.items() if k in _TENDER_SAFE_FIELDS and v is not None}
        batch.append(models.Tender(**clean))

    if not batch:
        return 0

    # 4. Try atomic batch insert first (fast path)
    try:
        db.add_all(batch)
        db.commit()
        return len(batch)
    except Exception as batch_err:
        db.rollback()
        logger.warning(
            f"[ENGINE] Batch insert failed ({batch_err}), "
            f"falling back to row-by-row insert for {len(batch)} tenders"
        )

    # 5. FIX: Row-by-row fallback — bad rows skipped, good rows saved
    saved = 0
    for tender in batch:
        try:
            db.add(tender)
            db.commit()
            saved += 1
        except Exception as row_err:
            db.rollback()
            logger.debug(f"[ENGINE] Skipped row {tender.content_hash}: {row_err}")

    return saved


def update_scraper_status(
    db: Session,
    site_name: str,
    count: int,
    error: Optional[Exception | str] = None,
) -> None:
    """Update heartbeat record for a scraper source."""
    try:
        status = db.query(models.ScraperStatus).filter_by(site_name=site_name).first()
        if not status:
            status = models.ScraperStatus(site_name=site_name)
            db.add(status)

        # FIX: datetime.now(timezone.utc) — utcnow() is deprecated and timezone-naive
        status.last_scraped_at   = datetime.now(timezone.utc)
        status.last_result_count = count
        # FIX: str() cast handles both Exception objects and plain strings safely
        status.last_error        = str(error) if error else None
        status.is_healthy        = (error is None)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] Status update failed for {site_name}: {e}")


def mark_urls_scraped(db: Session, urls: List[str]) -> None:
    """Mark CrawlResult entries as successfully scraped."""
    if not urls:
        return
    hashes = [hashlib.md5(u.encode()).hexdigest() for u in urls]
    try:
        updated = db.query(models.CrawlResult).filter(
            models.CrawlResult.url_hash.in_(hashes)
        ).update(
            {
                "scraped_at":     datetime.now(timezone.utc),  # FIX: timezone-aware
                "scrape_success": True,
            },
            synchronize_session=False,
        )
        db.commit()
        logger.debug(f"[ENGINE] Marked {updated} URLs as scraped")
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] URL sync failed: {e}")


# =============================================================================
# CITY SCRAPING (PARALLEL)
# =============================================================================

async def _scrape_city_parallel(
    site_name: str,
    urls: List[Dict],
    source: Dict,
) -> Dict:
    """
    Parallel URL scraping for a single city site with its own DB session.

    FIX: Each parallel task now gets its own httpx client and DB session.
    Previously a single shared db session was passed across concurrent async
    tasks — SQLAlchemy sessions are not thread/async-safe when shared.
    """
    sem = asyncio.Semaphore(5)
    site_tenders: List[Dict] = []
    scraped_urls: List[str]  = []

    # FIX: Determine SSL verification per domain
    host = source.get("url", "")
    ssl_verify = not any(d in host for d in _SSL_EXEMPT_DOMAINS)

    async def _task(url_entry: Dict):
        async with sem:
            try:
                async with httpx.AsyncClient(
                    timeout=30,
                    headers=get_headers(),
                    follow_redirects=True,
                    verify=ssl_verify,
                ) as client:
                    config  = {**source, "url": url_entry["url"]}
                    results = await city_portals.scrape_city(client, config)
                    return url_entry["url"], results or []
            except Exception as e:
                logger.debug(f"[ENGINE] Error on {url_entry['url']}: {e}")
                return url_entry["url"], []

    results = await asyncio.gather(*[_task(u) for u in urls])

    for url, res in results:
        if res:
            site_tenders.extend(res)
            scraped_urls.append(url)

    # FIX: Own DB session per city — not shared across concurrent tasks
    db = SessionLocal()
    try:
        new_count = upsert_tenders(db, site_tenders)
        mark_urls_scraped(db, scraped_urls)
    finally:
        db.close()

    return {"scraped": len(site_tenders), "new": new_count}


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

async def run_scraper() -> int:
    """
    Run a full scraper cycle across all sources.
    Returns the total number of new tenders inserted.
    """
    logger.info("[ENGINE] ═══ Starting scraper cycle ═══")
    started_at = datetime.now(timezone.utc)
    source_map = _build_source_map()
    total_new  = 0
    report     = []

    # Shared HTTP client for non-JS scrapers (phases 2 & 3)
    # FIX: verify=False removed — use per-request SSL handling instead
    async with httpx.AsyncClient(
        timeout=45,
        headers=get_headers(),
        follow_redirects=True,
        verify=True,
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
    ) as client:

        db = SessionLocal()
        try:

            # ------------------------------------------------------------------
            # PHASE 1: DISCOVERY — BFS crawler
            # ------------------------------------------------------------------
            crawl_index = await run_crawler(db, polite_delay=0.3)
            logger.info(f"[ENGINE] Phase 1 complete — {sum(len(v) for v in crawl_index.values())} URLs discovered")

            # ------------------------------------------------------------------
            # PHASE 2: CITY PORTALS (parallel per site)
            # ------------------------------------------------------------------
            city_tasks = {
                site_name: _scrape_city_parallel(site_name, urls, source_map[site_name])
                for site_name, urls in crawl_index.items()
                if site_name in source_map and source_map[site_name].get("source_type") == "city"
            }

            city_results = await asyncio.gather(*city_tasks.values(), return_exceptions=True)

            for site_name, result in zip(city_tasks.keys(), city_results):
                if isinstance(result, Exception):
                    logger.error(f"[ENGINE] City scrape failed for {site_name}: {result}")
                    report.append({"source": site_name, "new": 0, "status": "error"})
                    update_scraper_status(db, site_name, 0, result)
                else:
                    total_new += result["new"]
                    report.append({"source": site_name, "new": result["new"], "status": "ok"})
                    update_scraper_status(db, site_name, result["new"])

            logger.info(f"[ENGINE] Phase 2 complete — {sum(r.get('new', 0) for r in report)} new tenders")

            # ------------------------------------------------------------------
            # PHASE 3: STATIC SOURCES (aggregators + bulletins)
            # ------------------------------------------------------------------
            for name, src in source_map.items():
                if src.get("source_type") not in ("aggregator", "bulletin"):
                    continue
                if src.get("js_required"):
                    continue

                # FIX: Use a context-managed client for SSL-exempt domains to prevent connection leaks
                if any(d in src.get("url", "") for d in _SSL_EXEMPT_DOMAINS):
                    async with httpx.AsyncClient(
                        timeout=45, headers=get_headers(),
                        follow_redirects=True, verify=False,
                    ) as scrape_client:
                        try:
                            if src["source_type"] == "aggregator":
                                from scraper.sites.sa_tenders import scrape_aggregator
                                tenders = await scrape_aggregator(scrape_client, src)
                            else:
                                from scraper.sites.tender_bulletins import scrape_source
                                tenders = await scrape_source(scrape_client, src)
                        except Exception as e:
                            logger.error(f"[ENGINE] Static source {name} failed: {e}")
                            report.append({"source": name, "scraped": 0, "new": 0, "status": "error"})
                            update_scraper_status(db, name, 0, e)
                            continue
                else:
                    try:
                        if src["source_type"] == "aggregator":
                            from scraper.sites.sa_tenders import scrape_aggregator
                            tenders = await scrape_aggregator(client, src)
                        else:
                            from scraper.sites.tender_bulletins import scrape_source
                            tenders = await scrape_source(client, src)
                    except Exception as e:
                        logger.error(f"[ENGINE] Static source {name} failed: {e}")
                        report.append({"source": name, "scraped": 0, "new": 0, "status": "error"})
                        update_scraper_status(db, name, 0, e)
                        continue

                new = upsert_tenders(db, tenders)
                total_new += new
                report.append({"source": name, "scraped": len(tenders), "new": new, "status": "ok"})
                update_scraper_status(db, name, new)

            logger.info(f"[ENGINE] Phase 3 complete")

        finally:
            db.close()

    # --------------------------------------------------------------------------
    # PHASE 4: JS ENGINES (Playwright — manage their own browser context)
    # --------------------------------------------------------------------------
    for js_task in ["JS Aggregators", "eTenders National"]:
        try:
            if "National" in js_task:
                from scraper.sites.etenders import scrape_etenders
                tenders = await scrape_etenders()
            else:
                from scraper.sites.js_scraper import scrape_all_js_sources
                tenders = await scrape_all_js_sources()

            # JS scrapers need their own DB session
            db = SessionLocal()
            try:
                new = upsert_tenders(db, tenders)
            finally:
                db.close()

            total_new += new
            report.append({"source": js_task, "scraped": len(tenders), "new": new, "status": "ok"})
            logger.info(f"[ENGINE] {js_task}: {new} new tenders")

        except Exception as e:
            logger.error(f"[ENGINE] {js_task} failed: {e}")
            report.append({"source": js_task, "scraped": 0, "new": 0, "status": "error"})

    # --------------------------------------------------------------------------
    # NOTIFICATIONS
    # --------------------------------------------------------------------------
    if total_new > 0:
        try:
            from notifications import send_admin_notification, send_user_alerts
            send_admin_notification(total_new)
            db = SessionLocal()
            try:
                send_user_alerts(db)
            finally:
                db.close()
        except Exception as e:
            # FIX: Notification failure logged but doesn't mask scrape result
            logger.error(f"[ENGINE] Notification failed: {e}")

    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    ok      = sum(1 for r in report if r["status"] == "ok")
    errors  = sum(1 for r in report if r["status"] == "error")

    logger.info(
        f"[ENGINE] ═══ Cycle complete in {elapsed:.1f}s — "
        f"{total_new} new tenders | {ok} sources ok | {errors} errors ═══"
    )

    return total_new