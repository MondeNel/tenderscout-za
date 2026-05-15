"""
scraper/crawler.py — Tender URL Discovery Crawler
===================================================
Breadth-First Search (BFS) web crawler that discovers tender-related URLs
by starting from seed URLs and following links containing tender keywords.

This is URL DISCOVERY only — it finds WHERE tenders are, not the tender data
itself. Discovered URLs are saved to CrawlResult and then scraped by engine.py.

Architecture:
    crawl_site()         — BFS crawler for a single seed URL
    run_crawler()        — Concurrent crawler across all CRAWL_TARGETS
    _persist_crawl_results() — Batch-saves discovered URLs to DB
"""

import asyncio
import hashlib
import logging
import re
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models

# FIX: Single logger using stdlib logging — loguru was imported but the
# rest of the codebase uses stdlib. Mixing both caused logger.success()
# calls to crash when the loguru import was absent.
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

MAX_CONCURRENT_SITES = 5
DEFAULT_MAX_DEPTH    = 3
DEFAULT_MAX_PAGES    = 50

# SSL-exempt domains — known broken/expired certs on SA gov sites
_SSL_EXEMPT_DOMAINS: frozenset[str] = frozenset([
    "etenders.gov.za",
    "joburg.org.za",
    "tshwane.gov.za",
    "durban.gov.za",
    "solplaatje.org.za",
    "nkangaladm.gov.za",
])

# =============================================================================
# KEYWORD FILTERS
# =============================================================================

TENDER_KEYWORDS: list[str] = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "supply", "contract", "bids", "tenders", "sourcing", "award",
    "scm", "bulletin", "advertised", "advert", "proposal",
    "supply-chain", "request-for-quotation", "current-tenders",
    "formal-quotation", "bidding-document", "tender-bulletin",
    "navraag", "tendernommer", "kwotasie",
]

STRONG_ANCHOR_KEYWORDS: list[str] = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "sourcing", "bids", "tenders", "scm", "advertised",
    "bulletin", "supply chain",
]

SKIP_PATH_FRAGMENTS: list[str] = [
    "/login", "/admin", "/logout", "/register", "/wp-admin",
    "/cart", "/checkout", "?s=", "/tag/", "/category/feed",
    "/newsletter", "/news-and-media", "/media-releases", "/budget/",
    "/performance-contracts", "/long-term-borrowing", "/annual-report",
    "/financial-statement", "/organogram", "/vacancy", "/vacancies",
    "/council", "/gallery", "/awarded-tenders", "/tenders-awarded",
]

SOFT_404_FRAGMENTS: list[str] = [
    "/help?e=404", "/error", "/not-found", "404", "/page-not-found",
]

SKIP_EXTENSIONS: list[str] = [
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".jpg", ".png", ".gif", ".mp4",
]


# =============================================================================
# URL HELPERS
# =============================================================================

def _is_tender_url(url: str, anchor_text: str = "") -> bool:
    url_l   = url.lower()
    anchor_l = anchor_text.lower()
    return (
        any(kw in url_l    for kw in TENDER_KEYWORDS) or
        any(kw in anchor_l for kw in STRONG_ANCHOR_KEYWORDS)
    )


def _same_domain(base: str, url: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc


def _should_skip(url: str) -> bool:
    lower = url.lower()
    if any(lower.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    if any(frag in lower for frag in SKIP_PATH_FRAGMENTS):
        return True
    if "download=" in lower:
        return True
    return False


def _is_stale_year_url(url: str) -> bool:
    # FIX: Removed erroneous `self` parameter — this is a module-level function
    current_year = datetime.now(timezone.utc).year
    years = re.findall(r'20\d{2}', url)
    return any(int(y) < (current_year - 1) for y in years)


def _is_soft_404(final_url: str) -> bool:
    lower = final_url.lower()
    return any(frag in lower for frag in SOFT_404_FRAGMENTS)


def _load_robots(base_url: str) -> Optional[RobotFileParser]:
    try:
        parsed    = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp
    except Exception:
        return None


def _ssl_verify(url: str) -> bool:
    """FIX: Per-domain SSL control instead of global verify=False."""
    host = urlparse(url).netloc.lower().replace("www.", "")
    return not any(host == d or host.endswith(f".{d}") for d in _SSL_EXEMPT_DOMAINS)


# =============================================================================
# BFS CRAWLER — single site
# =============================================================================

async def crawl_site(
    seed_url:     str,
    max_depth:    int   = DEFAULT_MAX_DEPTH,
    max_pages:    int   = DEFAULT_MAX_PAGES,
    polite_delay: float = 1.0,
) -> List[Dict]:
    """
    BFS crawler for a single seed URL.

    Returns a list of dicts, each with:
      url, final_url, depth, status_code, discovered_at, seed_url
    """
    # FIX: deque + popleft() for O(1) BFS instead of list.pop(0) which is O(n)
    queue:   deque[Tuple[str, int]] = deque([(seed_url, 0)])
    visited: Set[str]               = {seed_url}
    # FIX: Track queued URLs separately to prevent duplicate queue entries
    # before they're visited — list.pop(0) previously allowed the same URL
    # to be enqueued multiple times from different parent pages
    queued:  Set[str]               = {seed_url}
    results: List[Dict]             = []

    robots = _load_robots(seed_url)

    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
        "Cache-Control":   "no-cache",
    }

    ssl_verify = _ssl_verify(seed_url)

    async with httpx.AsyncClient(
        timeout=30,
        headers=headers,
        follow_redirects=True,
        verify=ssl_verify,         # FIX: per-domain, not global False
        limits=httpx.Limits(max_keepalive_connections=10),
    ) as client:

        pages_visited = 0

        while queue and pages_visited < max_pages:
            url, depth = queue.popleft()   # FIX: O(1) deque popleft

            if _should_skip(url):
                continue
            if _is_stale_year_url(url):
                logger.debug(f"[CRAWLER] Skipping stale URL: {url}")
                continue
            if robots and not robots.can_fetch("*", url):
                logger.debug(f"[CRAWLER] robots.txt disallows: {url}")
                continue

            try:
                await asyncio.sleep(polite_delay)
                response = await client.get(url)
                pages_visited += 1
                visited.add(url)

                final_url = str(response.url)

                if _is_soft_404(final_url):
                    logger.debug(f"[CRAWLER] Soft 404: {url}")
                    continue

                if response.status_code != 200:
                    logger.debug(f"[CRAWLER] HTTP {response.status_code}: {url}")
                    continue

                results.append({
                    "url":          url,
                    "final_url":    final_url,
                    "depth":        depth,
                    "status_code":  response.status_code,
                    # FIX: timezone-aware datetime object, not naive isoformat string
                    "discovered_at": datetime.now(timezone.utc),
                    "seed_url":     seed_url,
                })

                if depth >= max_depth:
                    continue

                # Extract and queue new links
                soup = BeautifulSoup(response.text, "lxml")
                for tag in soup.find_all("a", href=True):
                    href   = tag["href"].strip()
                    anchor = tag.get_text(strip=True)

                    if not href or href.startswith("javascript:"):
                        continue

                    full_url = urljoin(url, href).split("#")[0]

                    if not full_url.startswith("http"):
                        continue
                    if not _same_domain(seed_url, full_url):
                        continue
                    # FIX: Check `queued` set to prevent duplicate queue entries
                    # before the URL has been visited
                    if full_url in visited or full_url in queued:
                        continue
                    if _should_skip(full_url):
                        continue
                    if _is_stale_year_url(full_url):
                        continue
                    if not _is_tender_url(full_url, anchor):
                        continue

                    queue.append((full_url, depth + 1))
                    queued.add(full_url)

            except httpx.TimeoutException:
                logger.warning(f"[CRAWLER] Timeout: {url}")
            except httpx.ConnectError as e:
                logger.warning(f"[CRAWLER] Connection error {url}: {e}")
            except httpx.ReadError as e:
                logger.warning(f"[CRAWLER] Read error {url}: {e}")
            except httpx.RequestError as e:
                logger.warning(f"[CRAWLER] Request error {url}: {e}")
            except Exception as e:
                logger.error(f"[CRAWLER] Unexpected error {url}: {e}")

    logger.info(f"[CRAWLER] {seed_url} → {len(results)} URLs ({pages_visited} pages)")
    return results


# =============================================================================
# DATABASE PERSISTENCE
# =============================================================================

def _persist_crawl_results(
    db:        Session,
    site_name: str,
    seed_url:  str,
    urls:      List[Dict],
) -> None:
    """
    Batch-save discovered URLs to CrawlResult table.

    FIX: Previous version committed inside the loop — one DB round-trip per URL.
    Now batches all inserts and commits once, with per-row rollback only on error.
    """
    if not urls:
        return

    now = datetime.now(timezone.utc)
    saved = 0
    skipped = 0

    # Bulk-fetch existing hashes to avoid per-row existence checks
    incoming_hashes = [hashlib.md5(e["url"].encode()).hexdigest() for e in urls]
    existing: Set[str] = {
        row[0] for row in
        db.query(models.CrawlResult.url_hash)
        .filter(models.CrawlResult.url_hash.in_(incoming_hashes))
        .all()
    }

    for entry in urls:
        url_hash = hashlib.md5(entry["url"].encode()).hexdigest()

        if url_hash in existing:
            # Update last_seen_at on known URLs
            try:
                db.query(models.CrawlResult).filter(
                    models.CrawlResult.url_hash == url_hash
                ).update(
                    {"last_seen_at": now, "is_active": True},
                    synchronize_session=False,
                )
                skipped += 1
            except Exception as e:
                db.rollback()
                logger.debug(f"[CRAWLER] Update failed for {entry['url'][:80]}: {e}")
        else:
            db.add(models.CrawlResult(
                site_name=site_name,
                seed_url=seed_url,
                discovered_url=entry["url"],
                final_url=entry.get("final_url"),
                depth=entry.get("depth", 0),
                status_code=entry.get("status_code", 200),
                url_hash=url_hash,
                is_active=True,
            ))
            existing.add(url_hash)
            saved += 1

    # FIX: Single commit for entire batch instead of per-row commits
    try:
        db.commit()
        logger.debug(f"[CRAWLER] {site_name}: {saved} new, {skipped} updated")
    except IntegrityError:
        db.rollback()
        logger.warning(f"[CRAWLER] Batch commit conflict for {site_name} — skipping batch")
    except Exception as e:
        db.rollback()
        logger.error(f"[CRAWLER] Batch commit failed for {site_name}: {e}")


# =============================================================================
# CRAWL TARGETS
# =============================================================================

CRAWL_TARGETS: list[Dict] = [
    # GAUTENG
    {"name": "City of Johannesburg",  "seed_url": "https://www.joburg.org.za/work_/TendersQuotations/Pages/Tenders.aspx", "max_depth": 2, "max_pages": 30},
    {"name": "City of Tshwane",       "seed_url": "https://www.tshwane.gov.za/?page_id=2194",                             "max_depth": 2, "max_pages": 30},
    {"name": "City of Ekurhuleni",    "seed_url": "https://www.ekurhuleni.gov.za/tenders",                                "max_depth": 3, "max_pages": 50},
    {"name": "Sedibeng District",     "seed_url": "https://www.sedibeng.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "West Rand District",    "seed_url": "https://www.westranddm.gov.za/tenders",                                "max_depth": 2, "max_pages": 30},
    # WESTERN CAPE
    {"name": "City of Cape Town",     "seed_url": "https://web1.capetown.gov.za/web1/procurementportal/",                 "max_depth": 2, "max_pages": 30},
    {"name": "Stellenbosch",          "seed_url": "https://www.stellenbosch.gov.za/tenders",                              "max_depth": 2, "max_pages": 30},
    {"name": "George Municipality",   "seed_url": "https://www.george.gov.za/tenders",                                    "max_depth": 2, "max_pages": 30},
    {"name": "Garden Route District", "seed_url": "https://www.gardenroute.gov.za/tenders",                               "max_depth": 2, "max_pages": 30},
    {"name": "Cape Winelands",        "seed_url": "https://www.capewinelands.gov.za/tenders",                             "max_depth": 2, "max_pages": 30},
    # KWAZULU-NATAL
    {"name": "eThekwini Municipality","seed_url": "https://www.durban.gov.za/pages/government/procurement",               "max_depth": 3, "max_pages": 40},
    {"name": "Msunduzi Municipality", "seed_url": "https://www.msunduzi.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "Umgungundlovu District","seed_url": "https://www.umdm.gov.za/tenders",                                      "max_depth": 2, "max_pages": 30},
    {"name": "Ugu District",          "seed_url": "https://www.ugu.gov.za/tenders",                                       "max_depth": 2, "max_pages": 30},
    {"name": "Zululand District",     "seed_url": "https://www.zululand.org.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    # EASTERN CAPE
    {"name": "Buffalo City Metro",    "seed_url": "https://www.buffalocity.gov.za/tenders",                               "max_depth": 3, "max_pages": 40},
    {"name": "Nelson Mandela Bay",    "seed_url": "https://www.nelsonmandelabay.gov.za/tenders",                          "max_depth": 3, "max_pages": 40},
    {"name": "OR Tambo District",     "seed_url": "https://www.ortambodm.gov.za/tenders",                                 "max_depth": 2, "max_pages": 30},
    {"name": "Amathole District",     "seed_url": "https://www.amathole.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    # FREE STATE
    {"name": "Mangaung Municipality", "seed_url": "https://www.mangaung.co.za/category/tenders-bids/",                    "max_depth": 2, "max_pages": 30},
    {"name": "Fezile Dabi District",  "seed_url": "https://www.feziledabi.gov.za/tenders",                                "max_depth": 2, "max_pages": 30},
    {"name": "Lejweleputswa District","seed_url": "https://www.lejweleputswa.gov.za/tenders",                             "max_depth": 2, "max_pages": 30},
    # LIMPOPO
    {"name": "Polokwane Municipality","seed_url": "https://www.polokwane.gov.za/index.php/tenders",                       "max_depth": 2, "max_pages": 30},
    {"name": "Capricorn District",    "seed_url": "https://www.cdm.org.za/tenders",                                       "max_depth": 2, "max_pages": 30},
    {"name": "Vhembe District",       "seed_url": "https://www.vhembe.gov.za/tenders",                                    "max_depth": 2, "max_pages": 30},
    {"name": "Mopani District",       "seed_url": "https://www.mopani.gov.za/tenders",                                    "max_depth": 2, "max_pages": 30},
    {"name": "Waterberg District",    "seed_url": "https://www.waterberg.gov.za/tenders",                                 "max_depth": 2, "max_pages": 30},
    # MPUMALANGA
    {"name": "Mbombela Municipality", "seed_url": "https://www.mbombela.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "Ehlanzeni District",    "seed_url": "https://www.ehlanzeni.gov.za/tenders",                                 "max_depth": 2, "max_pages": 30},
    {"name": "Gert Sibande District", "seed_url": "https://www.gertsibande.gov.za/tenders",                               "max_depth": 2, "max_pages": 30},
    {"name": "Nkangala District",     "seed_url": "https://www.nkangaladm.gov.za/tenders",                                "max_depth": 2, "max_pages": 30},
    # NORTH WEST
    {"name": "Rustenburg Municipality","seed_url": "https://www.rustenburg.gov.za/tenders",                               "max_depth": 2, "max_pages": 30},
    {"name": "Bojanala District",     "seed_url": "https://www.bojanala.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "Ngaka Modiri Molema",   "seed_url": "https://www.nmmdm.gov.za/tenders",                                     "max_depth": 2, "max_pages": 30},
    # NORTHERN CAPE
    {"name": "NC Provincial Govt",    "seed_url": "https://www.ncgov.co.za/tenders",                                      "max_depth": 3, "max_pages": 40},
    {"name": "Sol Plaatje Municipality","seed_url": "https://www.solplaatje.org.za/tenders",                              "max_depth": 2, "max_pages": 20},
    {"name": "Frances Baard District","seed_url": "https://francesbaard.gov.za/tenders/",                                 "max_depth": 2, "max_pages": 20},
    {"name": "Namakwa District",      "seed_url": "https://www.namakwa-dm.gov.za/request-for-tenders/",                   "max_depth": 2, "max_pages": 20},
    # AGGREGATORS
    {"name": "eTenders Portal",       "seed_url": "https://www.etenders.gov.za",                                          "max_depth": 2, "max_pages": 40},
    {"name": "Municipalities.co.za",  "seed_url": "https://municipalities.co.za/tenders",                                 "max_depth": 2, "max_pages": 40},
]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def run_crawler(
    db:           Optional[Session] = None,
    polite_delay: float             = 1.0,      # FIX: Added missing param from engine.py call
) -> Dict[str, List[Dict]]:
    """
    Concurrent BFS crawl across all CRAWL_TARGETS.
    Returns a dict of site_name → list of discovered URL dicts.
    """
    sem          = asyncio.Semaphore(MAX_CONCURRENT_SITES)
    crawl_index: Dict[str, List[Dict]] = {}
    started_at   = datetime.now(timezone.utc)

    logger.info(f"[CRAWLER] Starting batch crawl — {len(CRAWL_TARGETS)} targets")

    async def _crawl_one(target: Dict) -> Tuple[str, List[Dict]]:
        name = target.get("name", "Unknown")
        seed = target.get("seed_url", "")
        async with sem:
            try:
                urls = await crawl_site(
                    seed_url=seed,
                    max_depth=target.get("max_depth", DEFAULT_MAX_DEPTH),
                    max_pages=target.get("max_pages",  DEFAULT_MAX_PAGES),
                    polite_delay=polite_delay,
                )
                if db is not None and urls:
                    _persist_crawl_results(db, name, seed, urls)
                return name, urls
            except Exception as e:
                logger.error(f"[CRAWLER] {name} failed: {e}")
                return name, []

    results = await asyncio.gather(
        *[_crawl_one(t) for t in CRAWL_TARGETS],
        return_exceptions=True,
    )

    for item in results:
        if isinstance(item, Exception):
            logger.error(f"[CRAWLER] Task-level exception: {item}")
            continue
        name, urls = item
        crawl_index[name] = urls

    total_urls = sum(len(v) for v in crawl_index.values())
    elapsed    = (datetime.now(timezone.utc) - started_at).total_seconds()
    sites_ok   = len([v for v in crawl_index.values() if v])

    logger.info(
        f"[CRAWLER] Complete in {elapsed:.1f}s — "
        f"{total_urls} URLs from {sites_ok}/{len(CRAWL_TARGETS)} sites"
    )

    return crawl_index