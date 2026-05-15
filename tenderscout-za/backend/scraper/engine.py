"""
scraper/engine.py — Scraper Orchestrator (Resilience‑Hardened)
===============================================================
4‑phase pipeline for South African tender acquisition.
v2: SSL bypass for all city portals, retry with backoff in Phase 2.
"""

import asyncio
import logging
import hashlib
import ssl
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set, Tuple

from sqlalchemy.orm import Session
from database import SessionLocal
import models
from scraper.utils import get_headers
from scraper.crawler import run_crawler
from scraper.sites import city_portals

logger = logging.getLogger(__name__)

_TENDER_SAFE_FIELDS: frozenset[str] = frozenset([
    "title", "description", "issuing_body", "province", "municipality",
    "town", "industry_category", "closing_date", "closing_date_parsed",
    "posted_date", "source_url", "source_site", "reference_number",
    "contact_info", "content_hash", "document_url", "lat", "lng",
])

# Domains that need SSL verification disabled (broken government certificates)
_SSL_EXEMPT_DOMAINS: frozenset[str] = frozenset([
    "etenders.gov.za",
    # Add any other specific aggregator domains as needed
])

# ---------------------------------------------------------------------------
# Utility: exponential‑backoff retry for scraping a single URL
# ---------------------------------------------------------------------------
_RETRYABLE_EXCEPTIONS = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.ReadError,
)

async def _retry_scrape_city(
    client: httpx.AsyncClient,
    config: Dict,
    max_retries: int = 2,
    base_delay: float = 1.0,
) -> List[Dict]:
    """
    Call city_portals.scrape_city with retries on transient network errors.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            return await city_portals.scrape_city(client, config)
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                break
            delay = base_delay * (2**attempt)
            logger.warning(
                "Retry %d/%d for %s after %.1fs: %s",
                attempt + 1, max_retries, config.get("url", ""), delay, exc,
            )
            await asyncio.sleep(delay)
    raise last_exc  # will be caught by outer handler


def _build_source_map() -> Dict[str, Dict]:
    m: Dict[str, Dict] = {}
    for c in city_portals.CITY_PORTALS:
        m[c["name"]] = {**c, "source_type": "city"}
    try:
        from scraper.sites.sa_tenders import AGGREGATORS
        for a in AGGREGATORS:
            m[a["name"]] = {**a, "source_type": "aggregator"}
    except ImportError:
        pass
    try:
        from scraper.sites.tender_bulletins import SOURCES
        for s in SOURCES:
            m[s["name"]] = {**s, "source_type": "bulletin"}
    except ImportError:
        pass
    return m


def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    # (unchanged)
    if not tenders:
        return 0
    now = datetime.now(timezone.utc)
    seen: Set[str] = set()
    unique: List[Dict] = []
    for t in tenders:
        h = t.get("content_hash")
        title = t.get("title", "").strip()
        if not h or not title:
            continue
        if h in seen:
            continue
        expiry = t.get("expiry_date") or t.get("closing_date_parsed")
        if expiry:
            if isinstance(expiry, datetime):
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry < now:
                    continue
        seen.add(h)
        unique.append(t)
    if not unique:
        return 0
    incoming_hashes = [t["content_hash"] for t in unique]
    existing_hashes: Set[str] = {
        row[0] for row in
        db.query(models.Tender.content_hash)
        .filter(models.Tender.content_hash.in_(incoming_hashes))
        .all()
    }
    batch: List[models.Tender] = []
    for t in unique:
        if t["content_hash"] in existing_hashes:
            continue
        clean = {k: v for k, v in t.items() if k in _TENDER_SAFE_FIELDS and v is not None}
        batch.append(models.Tender(**clean))
    if not batch:
        return 0
    try:
        db.add_all(batch)
        db.commit()
        return len(batch)
    except Exception as batch_err:
        db.rollback()
        logger.warning(f"[ENGINE] Batch insert failed, falling back row-by-row: {batch_err}")
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


def update_scraper_status(db: Session, site_name: str, count: int, error: Optional[Exception | str] = None) -> None:
    # (unchanged)
    try:
        status = db.query(models.ScraperStatus).filter_by(site_name=site_name).first()
        if not status:
            status = models.ScraperStatus(site_name=site_name)
            db.add(status)
        status.last_scraped_at   = datetime.now(timezone.utc)
        status.last_result_count = count
        status.last_error        = str(error) if error else None
        status.is_healthy        = (error is None)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] Status update failed for {site_name}: {e}")


def mark_urls_scraped(db: Session, urls: List[str]) -> None:
    # (unchanged)
    if not urls:
        return
    hashes = [hashlib.md5(u.encode()).hexdigest() for u in urls]
    try:
        db.query(models.CrawlResult).filter(
            models.CrawlResult.url_hash.in_(hashes)
        ).update({"scraped_at": datetime.now(timezone.utc), "scrape_success": True}, synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[ENGINE] URL sync failed: {e}")


# ---------------------------------------------------------------------------
# Phase 2: parallel city portal scraping (hardened)
# ---------------------------------------------------------------------------
async def _scrape_city_parallel(site_name: str, urls: List[Dict], source: Dict) -> Dict:
    """
    Scrape all discovered URLs for a single city portal.
    - SSL verification is disabled for all city portals.
    - Each URL is scraped with retries on transient network errors.
    """
    sem = asyncio.Semaphore(5)
    site_tenders: List[Dict] = []
    scraped_urls: List[str]  = []

    # Custom SSL context – skip cert verification for municipal sites
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    async def _task(url_entry: Dict):
        async with sem:
            try:
                # Use a dedicated client per URL (keeps it simple)
                async with httpx.AsyncClient(
                    timeout=30,
                    headers=get_headers(),
                    follow_redirects=True,
                    verify=ctx,            # <-- bypass broken certs
                    trust_env=False,
                    http2=False,
                ) as client:
                    config = {**source, "url": url_entry["url"]}
                    # Retry the actual scraping with backoff
                    results = await _retry_scrape_city(client, config, max_retries=3)
                    return url_entry["url"], results or []
            except Exception as e:
                logger.debug(f"[ENGINE] Error on {url_entry['url']}: {e}")
                return url_entry["url"], []

    results = await asyncio.gather(*[_task(u) for u in urls])
    for url, res in results:
        if res:
            site_tenders.extend(res)
            scraped_urls.append(url)

    db = SessionLocal()
    try:
        new_count = upsert_tenders(db, site_tenders)
        mark_urls_scraped(db, scraped_urls)
    finally:
        db.close()
    return {"scraped": len(site_tenders), "new": new_count}


# ---------------------------------------------------------------------------
# Main pipeline (minor SSL adjustments for Phase 3)
# ---------------------------------------------------------------------------
async def run_scraper() -> int:
    logger.info("[ENGINE] ═══ Starting scraper cycle ═══")
    started_at = datetime.now(timezone.utc)
    source_map = _build_source_map()
    total_new  = 0
    report     = []

    # Main client for crawler & aggregators that need SSL verification
    async with httpx.AsyncClient(
        timeout=45,
        headers=get_headers(),
        follow_redirects=True,
        verify=True,   # aggregators usually have valid certs
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
    ) as client:
        db = SessionLocal()
        try:
            crawl_index = await run_crawler(db, polite_delay=0.3)
            logger.info(f"[ENGINE] Phase 1 complete — {sum(len(v) for v in crawl_index.values())} URLs discovered")

            # Phase 2: city portals (SSL already disabled inside _scrape_city_parallel)
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

            # Phase 3: aggregators & bulletins
            for name, src in source_map.items():
                if src.get("source_type") not in ("aggregator", "bulletin"):
                    continue
                if src.get("js_required"):
                    continue

                # Determine if this specific aggregator needs SSL exemption
                host = src.get("url", "")
                ssl_exempt = any(d in host for d in _SSL_EXEMPT_DOMAINS)
                scrape_client = client  # default to main client with verify=True
                if ssl_exempt:
                    # Create a temporary client with verify=False for this source
                    scrape_client = httpx.AsyncClient(
                        timeout=45,
                        headers=get_headers(),
                        follow_redirects=True,
                        verify=False,
                    )

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
                finally:
                    if ssl_exempt:
                        await scrape_client.aclose()

                new = upsert_tenders(db, tenders)
                total_new += new
                report.append({"source": name, "scraped": len(tenders), "new": new, "status": "ok"})
                update_scraper_status(db, name, new)
            logger.info(f"[ENGINE] Phase 3 complete")
        finally:
            db.close()

    # Phase 4: JS‑rendered sources (unchanged)
    for js_task in ["JS Aggregators", "eTenders National"]:
        try:
            if "National" in js_task:
                from scraper.sites.etenders import scrape_etenders
                tenders = await scrape_etenders()
            else:
                from scraper.sites.js_scraper import scrape_all_js_sources
                tenders = await scrape_all_js_sources()
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

    # Notifications (unchanged)
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
            logger.error(f"[ENGINE] Notification failed: {e}")

    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    ok = sum(1 for r in report if r["status"] == "ok")
    errors = sum(1 for r in report if r["status"] == "error")
    logger.info(f"[ENGINE] ═══ Cycle complete in {elapsed:.1f}s — {total_new} new tenders | {ok} ok | {errors} errors ═══")
    return total_new