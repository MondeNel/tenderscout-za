"""
scraper/engine.py — Scraper Orchestrator (Resilience‑Hardened)
===============================================================
4‑phase pipeline for South African tender acquisition.

v2 improvements:
- SSL bypass for all city portal scrapers (custom SSL context)
- Exponential backoff retry for transient network errors in Phase 2

Pipeline stages:
  Phase 1 — Crawling:   BFS discovery of tender URLs from seed pages
  Phase 2 — City portals: scrape individual municipal/city websites
                         (parallel, SSL‑disabled, with retries)
  Phase 3 — Aggregators & bulletins: scrape national aggregator sites
                         (SSL enabled except for exempted domains)
  Phase 4 — JS‑rendered sources: Playwright‑based scraping for sites
                         that require JavaScript rendering
  Post‑pipeline — Notifications: if new tenders were added, alert
                         admin and users via notifications.py
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

# ------------------------------------------------------------------
# Whitelist of fields that may be inserted into the Tender table.
# Any extra fields scraped from a site are silently ignored.
# This prevents arbitrary data from polluting the database.
# ------------------------------------------------------------------
_TENDER_SAFE_FIELDS: frozenset[str] = frozenset([
    "title", "description", "issuing_body", "province", "municipality",
    "town", "industry_category", "closing_date", "closing_date_parsed",
    "posted_date", "source_url", "source_site", "reference_number",
    "contact_info", "content_hash", "document_url", "lat", "lng",
])

# ------------------------------------------------------------------
# Aggregator domains with known broken certificates.
# During Phase 3 we'll create a separate client with verify=False for these.
# ------------------------------------------------------------------
_SSL_EXEMPT_DOMAINS: frozenset[str] = frozenset([
    "etenders.gov.za",
    # Other aggregator domains can be added here as needed
])

# ------------------------------------------------------------------
# Retryable exception types – transient network failures that are
# likely to succeed if we wait and retry.
# ------------------------------------------------------------------
_RETRYABLE_EXCEPTIONS = (
    httpx.RemoteProtocolError,  # server disconnected mid‑response
    httpx.ConnectError,        # TCP connection failed
    httpx.ReadTimeout,         # server didn't send response in time
    httpx.ConnectTimeout,      # connection establishment timeout
    httpx.ReadError,           # partial response / broken pipe
)


async def _retry_scrape_city(
    client: httpx.AsyncClient,
    config: Dict,
    max_retries: int = 2,
    base_delay: float = 1.0,
) -> List[Dict]:
    """
    Call city_portals.scrape_city with exponential backoff on failure.

    If a transient network error occurs, we wait `base_delay` seconds,
    then `base_delay * 2`, then `base_delay * 4` (up to max_retries).
    After all retries are exhausted, the last exception is re‑raised.

    Args:
        client: httpx client (should already have SSL disabled for city portals)
        config: single‑city portal config dict (must include 'url')
        max_retries: number of attempts before giving up
        base_delay: initial wait in seconds (doubled each retry)

    Returns:
        List of tender dicts scraped from this URL.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            return await city_portals.scrape_city(client, config)
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                break  # no more retries
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Retry %d/%d for %s after %.1fs: %s",
                attempt + 1, max_retries, config.get("url", ""), delay, exc,
            )
            await asyncio.sleep(delay)
    # If we exit the loop, all retries failed
    raise last_exc  # will be caught by the caller


def _build_source_map() -> Dict[str, Dict]:
    """
    Combine all scraper source definitions (city portals, aggregators,
    bulletins) into a single dictionary keyed by source name.

    Each entry is annotated with a `source_type` field:
      - "city"       – municipal/city portal
      - "aggregator" – national tender aggregator (e.g., sa‑tenders)
      - "bulletin"   – provincial/national bulletin sites

    Returns:
        Dict mapping source name → dict with all source config data.
    """
    m: Dict[str, Dict] = {}

    # City portals from city_portals.py
    for c in city_portals.CITY_PORTALS:
        m[c["name"]] = {**c, "source_type": "city"}

    # Aggregators (optional – may not exist if the module is removed)
    try:
        from scraper.sites.sa_tenders import AGGREGATORS
        for a in AGGREGATORS:
            m[a["name"]] = {**a, "source_type": "aggregator"}
    except ImportError:
        pass

    # Bulletins (optional – may not exist if the module is removed)
    try:
        from scraper.sites.tender_bulletins import SOURCES
        for s in SOURCES:
            m[s["name"]] = {**s, "source_type": "bulletin"}
    except ImportError:
        pass

    return m


def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    """
    Insert new tenders into the database, ignoring duplicates.

    Deduplication is based on `content_hash`. Tenders whose hash already
    exists in the database are skipped. Expired tenders (closing date
    in the past) are also filtered out.

    Implementation detail:
      - First, a batch insert is attempted. If a single row causes a
        database error (e.g., constraint violation), the entire batch
        would be rolled back.
      - Therefore, if the batch insert fails, we fall back to inserting
        row‑by‑row, skipping individual problematic rows.

    Args:
        db: SQLAlchemy Session
        tenders: list of tender dicts (must include 'content_hash')

    Returns:
        Number of tenders actually inserted.
    """
    if not tenders:
        return 0

    now = datetime.now(timezone.utc)

    # --- Remove duplicates within the incoming batch itself ---
    seen: Set[str] = set()
    unique: List[Dict] = []
    for t in tenders:
        h = t.get("content_hash")
        title = t.get("title", "").strip()
        if not h or not title:
            continue   # invalid tender
        if h in seen:
            continue   # duplicate within batch
        # Skip tenders that are already expired
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

    # --- Check which hashes already exist in the database ---
    incoming_hashes = [t["content_hash"] for t in unique]
    existing_hashes: Set[str] = {
        row[0] for row in
        db.query(models.Tender.content_hash)
        .filter(models.Tender.content_hash.in_(incoming_hashes))
        .all()
    }

    # --- Build the list of SQLAlchemy model objects ---
    batch: List[models.Tender] = []
    for t in unique:
        if t["content_hash"] in existing_hashes:
            continue   # already in DB
        # Keep only fields that are defined in the model
        clean = {k: v for k, v in t.items() if k in _TENDER_SAFE_FIELDS and v is not None}
        batch.append(models.Tender(**clean))

    if not batch:
        return 0

    # --- Attempt batch insert, with row‑by‑row fallback ---
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
    """
    Record the outcome of scraping a source in the ScraperStatus table.

    If a row for this site already exists, it is updated; otherwise a new
    row is created.

    Args:
        db: SQLAlchemy Session
        site_name: name of the source (e.g., "City of Johannesburg")
        count: number of tenders scraped (or 0 if error)
        error: exception or string describing what went wrong
    """
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
    """
    After successfully scraping tenders from a set of URLs, mark those
    CrawlResult rows as scraped (scraped_at = now, scrape_success = True).

    URLs are identified by their MD5 hash (the url_hash column).

    Args:
        db: SQLAlchemy Session
        urls: list of absolute URL strings that were just scraped
    """
    if not urls:
        return
    hashes = [hashlib.md5(u.encode()).hexdigest() for u in urls]
    try:
        db.query(models.CrawlResult).filter(
            models.CrawlResult.url_hash.in_(hashes)
        ).update(
            {"scraped_at": datetime.now(timezone.utc), "scrape_success": True},
            synchronize_session=False
        )
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

    This function is called for every city portal that the crawler
    discovered URLs for (Phase 2 of the pipeline).

    Key behaviours:
    - SSL certificate verification is completely disabled via a custom
      SSL context – municipal sites often have broken certificates.
    - Up to 5 URLs are scraped concurrently (semaphore).
    - Each URL is scraped with retry (exponential backoff) in case of
      transient network errors (see _retry_scrape_city).
    - Scraped tenders are immediately persisted via upsert_tenders.
    - Successfully scraped URLs are marked as processed in the
      CrawlResult table via mark_urls_scraped.

    Args:
        site_name: name of the city portal (e.g., "City of Tshwane")
        urls: list of dicts, each containing at least {"url": ...}
        source: full source configuration dict (from _build_source_map)

    Returns:
        Dict with keys:
          "scraped" – total tenders extracted (including duplicates)
          "new"     – number of tenders actually inserted into DB
    """
    sem = asyncio.Semaphore(5)           # limit concurrency per site
    site_tenders: List[Dict] = []        # collected tenders
    scraped_urls: List[str]  = []        # URLs that produced at least one tender

    # Custom SSL context: skip all certificate verification
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    async def _task(url_entry: Dict):
        """Scrape one URL within the semaphore."""
        async with sem:
            try:
                # Create a short‑lived client per URL (keeps isolation simple)
                async with httpx.AsyncClient(
                    timeout=30,
                    headers=get_headers(),
                    follow_redirects=True,
                    verify=ctx,            # <-- bypass broken certs
                    trust_env=False,       # ignore system proxy / cert env vars
                    http2=False,           # stick to HTTP/1.1
                ) as client:
                    config = {**source, "url": url_entry["url"]}
                    # Retry the actual scraping with backoff
                    results = await _retry_scrape_city(client, config, max_retries=3)
                    return url_entry["url"], results or []
            except Exception as e:
                logger.debug(f"[ENGINE] Error on {url_entry['url']}: {e}")
                return url_entry["url"], []

    # Run all tasks in parallel
    results = await asyncio.gather(*[_task(u) for u in urls])

    # Collect successful results
    for url, res in results:
        if res:
            site_tenders.extend(res)
            scraped_urls.append(url)

    # Persist to database
    db = SessionLocal()
    try:
        new_count = upsert_tenders(db, site_tenders)
        mark_urls_scraped(db, scraped_urls)
    finally:
        db.close()

    return {"scraped": len(site_tenders), "new": new_count}


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------
async def run_scraper() -> int:
    """
    Execute the complete 4‑phase tender acquisition pipeline.

    Returns the total number of **new** tenders inserted during this cycle.

    The function is designed to be called by APScheduler or manually via
    the /admin/trigger-scrape endpoint.
    """
    logger.info("[ENGINE] ═══ Starting scraper cycle ═══")
    started_at = datetime.now(timezone.utc)

    # Build the unified source map (city + aggregator + bulletin)
    source_map = _build_source_map()

    total_new = 0          # count of newly inserted tenders
    report    = []         # per‑source status for logging

    # ------------------------------------------------------------------
    # Phase 1 & 2: Crawl then scrape city portals
    # ------------------------------------------------------------------
    # The main client is used for the crawler and for Phase 3 aggregators.
    # City portal scrapers (Phase 2) create their own SSL‑disabled clients.
    # ------------------------------------------------------------------
    async with httpx.AsyncClient(
        timeout=45,
        headers=get_headers(),
        follow_redirects=True,
        verify=True,   # aggregators usually have valid certificates
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
    ) as client:
        db = SessionLocal()
        try:
            # ---------- Phase 1: Crawl ----------
            crawl_index = await run_crawler(db, polite_delay=0.3)
            total_urls = sum(len(v) for v in crawl_index.values())
            logger.info(f"[ENGINE] Phase 1 complete — {total_urls} URLs discovered")

            # ---------- Phase 2: City portals ----------
            # Build a mapping of site name → scrape task for city portals only
            city_tasks = {
                site_name: _scrape_city_parallel(site_name, urls, source_map[site_name])
                for site_name, urls in crawl_index.items()
                if site_name in source_map and source_map[site_name].get("source_type") == "city"
            }

            # Run all city portal scrapes concurrently
            city_results = await asyncio.gather(*city_tasks.values(), return_exceptions=True)

            # Process results and update per‑site status
            for site_name, result in zip(city_tasks.keys(), city_results):
                if isinstance(result, Exception):
                    logger.error(f"[ENGINE] City scrape failed for {site_name}: {result}")
                    report.append({"source": site_name, "new": 0, "status": "error"})
                    update_scraper_status(db, site_name, 0, result)
                else:
                    total_new += result["new"]
                    report.append({"source": site_name, "new": result["new"], "status": "ok"})
                    update_scraper_status(db, site_name, result["new"])

            new_in_phase2 = sum(r.get("new", 0) for r in report)
            logger.info(f"[ENGINE] Phase 2 complete — {new_in_phase2} new tenders")

            # ---------- Phase 3: Aggregators & bulletins ----------
            for name, src in source_map.items():
                if src.get("source_type") not in ("aggregator", "bulletin"):
                    continue
                if src.get("js_required"):
                    continue  # these will be handled in Phase 4

                # Check if this source needs SSL exemption
                host = src.get("url", "")
                ssl_exempt = any(d in host for d in _SSL_EXEMPT_DOMAINS)
                scrape_client = client  # default: reuse the main client (verify=True)
                if ssl_exempt:
                    # Create a temporary client with verify=False just for this source
                    scrape_client = httpx.AsyncClient(
                        timeout=45,
                        headers=get_headers(),
                        follow_redirects=True,
                        verify=False,
                    )

                try:
                    # Dispatch to the correct scraper based on source type
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
                        await scrape_client.aclose()  # clean up temporary client

                # Insert scraped tenders
                new = upsert_tenders(db, tenders)
                total_new += new
                report.append({"source": name, "scraped": len(tenders), "new": new, "status": "ok"})
                update_scraper_status(db, name, new)

            logger.info("[ENGINE] Phase 3 complete")
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Phase 4: JS‑rendered sources (Playwright‑based)
    # ------------------------------------------------------------------
    # These are run after the main async context because Playwright
    # requires its own event loop handling.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Post‑pipeline: notifications (if any new tenders were added)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    ok     = sum(1 for r in report if r["status"] == "ok")
    errors = sum(1 for r in report if r["status"] == "error")
    logger.info(
        f"[ENGINE] ═══ Cycle complete in {elapsed:.1f}s — "
        f"{total_new} new tenders | {ok} ok | {errors} errors ═══"
    )
    return total_new