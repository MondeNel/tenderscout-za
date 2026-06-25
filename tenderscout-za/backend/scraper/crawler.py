"""
scraper/crawler.py — Tender URL Discovery Crawler
===================================================
Breadth‑First Search (BFS) web crawler that discovers tender‑related URLs
from seed URLs. Discovered URLs are saved to the CrawlResult table for
later scraping by the pipeline.

Key features:
- BFS with configurable depth and page limits per site
- robots.txt compliance (cached per domain)
- Tender keyword detection (URL and anchor text)
- Domain‑based scope (only follows links within the same domain)
- Intelligent skipping of non‑tender pages (admin, login, media, etc.)
- SSL verification disabled for domains with broken government certificates
- Soft 404 detection
- Politeness delay between requests
- Parallel crawling of multiple sites using asyncio
- Immediate persistence of discovered URLs to the database
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
from sqlalchemy.orm import Session

import models

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Concurrency limits – how many sites are crawled in parallel
# ------------------------------------------------------------------
MAX_CONCURRENT_SITES = 5   # prevents overwhelming the server

# Default BFS constraints (overridable per target in CRAWL_TARGETS)
DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_PAGES = 50

# ------------------------------------------------------------------
# SSL Exemption – domains whose certificates are known to be broken
# ------------------------------------------------------------------
# When crawling these domains, certificate verification is turned off
# to avoid SSL errors that would otherwise block the crawl.
# ------------------------------------------------------------------
_SSL_EXEMPT_DOMAINS: frozenset[str] = frozenset([
    "etenders.gov.za",
    "joburg.org.za",
    "tshwane.gov.za",
    "durban.gov.za",
    "solplaatje.org.za",
    "nkangaladm.gov.za",
])

# ------------------------------------------------------------------
# Tender keywords – used to identify links likely to contain tenders
# ------------------------------------------------------------------
# A URL is considered tender‑related if it contains any of these keywords
# (case‑insensitive) in its path/query, or if its anchor text contains a
# strong keyword from the STRONG_ANCHOR_KEYWORDS list below.
# ------------------------------------------------------------------
TENDER_KEYWORDS: list[str] = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "supply", "contract", "bids", "tenders", "sourcing", "award",
    "scm", "bulletin", "advertised", "advert", "proposal",
    "supply-chain", "request-for-quotation", "current-tenders",
    "formal-quotation", "bidding-document", "tender-bulletin",
]

# Strong anchor keywords — if the visible text of a link contains
# any of these, we follow it even if the URL itself doesn't have a
# tender keyword (this captures links like "Current Tenders" that
# point to generic pages).
STRONG_ANCHOR_KEYWORDS: list[str] = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "sourcing", "bids", "tenders", "scm", "advertised",
    "bulletin", "supply chain",
]

# ------------------------------------------------------------------
# Skip lists – paths/patterns that are never tender‑related
# ------------------------------------------------------------------
# To avoid wasting time on non‑tender pages, we skip URLs whose path
# contains any of these fragments. This also reduces database noise.
# ------------------------------------------------------------------
SKIP_PATH_FRAGMENTS: list[str] = [
    "/login", "/admin", "/logout", "/register", "/wp-admin",
    "/cart", "/checkout", "?s=", "/tag/", "/category/feed",
    "/newsletter", "/news-and-media", "/media-releases", "/budget/",
    "/performance-contracts", "/long-term-borrowing", "/annual-report",
    "/financial-statement", "/organogram", "/vacancy", "/vacancies",
    "/council", "/gallery", "/awarded-tenders", "/tenders-awarded",
]

# URLs containing any of these fragments are treated as soft 404s
# (the server returned 200 but the page is effectively not found).
SOFT_404_FRAGMENTS: list[str] = [
    "/help?e=404", "/error", "/not-found", "404", "/page-not-found",
]

# File extensions that will never contain tender listings
SKIP_EXTENSIONS: list[str] = [
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".jpg", ".png", ".gif", ".mp4",
]


def _is_tender_url(url: str, anchor_text: str = "") -> bool:
    """
    Determine if a URL is likely to be a tender listing.

    Checks both the URL string and the anchor text against the
    keyword lists defined above. Case‑insensitive comparison.
    """
    url_l    = url.lower()
    anchor_l = anchor_text.lower()
    return (
        any(kw in url_l    for kw in TENDER_KEYWORDS) or
        any(kw in anchor_l for kw in STRONG_ANCHOR_KEYWORDS)
    )


def _same_domain(base: str, url: str) -> bool:
    """
    Return True if `url` has the same netloc (domain) as `base`.
    This keeps the crawl scoped to the target website.
    """
    return urlparse(url).netloc == urlparse(base).netloc


def _should_skip(url: str) -> bool:
    """
    Return True if the URL should be excluded from crawling.

    Filters out:
    - Files with specific extensions (PDFs, images, etc.)
    - Admin, login, gallery, and other non‑tender paths
    - URLs with "download=" (file downloads)
    """
    lower = url.lower()
    if any(lower.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    if any(frag in lower for frag in SKIP_PATH_FRAGMENTS):
        return True
    if "download=" in lower:
        return True
    return False


def _is_stale_year_url(url: str) -> bool:
    """
    Detect URLs that contain a year older than (current year - 1),
    e.g., ".../tenders-2022/..." when the current year is 2024.
    These are likely outdated archives and are skipped.
    """
    current_year = datetime.now(timezone.utc).year
    years = re.findall(r'20\d{2}', url)
    return any(int(y) < (current_year - 1) for y in years)


def _is_soft_404(final_url: str) -> bool:
    """
    Detect pages that returned HTTP 200 but are actually error pages
    (e.g., the site's custom "Page Not Found" page).
    """
    lower = final_url.lower()
    return any(frag in lower for frag in SOFT_404_FRAGMENTS)


def _load_robots(base_url: str) -> Optional[RobotFileParser]:
    """
    Fetch and parse the robots.txt file for the given base URL.

    Returns a RobotFileParser object or None if the file couldn't
    be fetched (e.g., network error). The result is used to check
    whether a specific URL is allowed to be crawled.
    """
    try:
        parsed     = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp
    except Exception:
        return None


def _ssl_verify(url: str) -> bool:
    """
    Determine whether SSL verification should be performed for this URL.

    Returns False (don't verify) for domains in the SSL exemption list,
    True otherwise. This is a pragmatic workaround for government servers
    with broken or self‑signed certificates.
    """
    host = urlparse(url).netloc.lower().replace("www.", "")
    return not any(host == d or host.endswith(f".{d}") for d in _SSL_EXEMPT_DOMAINS)


async def crawl_site(
    seed_url:     str,
    max_depth:    int   = DEFAULT_MAX_DEPTH,
    max_pages:    int   = DEFAULT_MAX_PAGES,
    polite_delay: float = 1.0,
) -> List[Dict]:
    """
    Perform a breadth‑first crawl of a single site starting from `seed_url`.

    Algorithm:
    1. Initialise a FIFO queue with (seed_url, depth=0).
    2. Track `visited` and `queued` sets to avoid duplicates.
    3. Fetch robots.txt once and cache it.
    4. For each URL:
       - Apply skip filters (extensions, paths, stale years, robots.txt).
       - Fetch the page with a polite delay.
       - If successful (HTTP 200, no soft 404), record the result.
       - If depth < max_depth, extract all same‑domain anchor links,
         filter by tender keywords, and add them to the queue.
    5. Stop when the queue is empty or `max_pages` have been visited.

    Returns:
    A list of dicts, each containing:
      url, final_url, depth, status_code, discovered_at, seed_url
    """
    # FIFO queue for BFS – each entry is (url, depth)
    queue:   deque[Tuple[str, int]] = deque([(seed_url, 0)])
    visited: Set[str]               = {seed_url}
    queued:  Set[str]               = {seed_url}   # tracks what's been added to the queue
    results: List[Dict]             = []

    # Load robots.txt once for the whole site
    robots = _load_robots(seed_url)

    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
        "Cache-Control":   "no-cache",
    }

    # Decide SSL verification based on the domain
    ssl_verify = _ssl_verify(seed_url)

    # Create a single HTTP client for the entire crawl of this site.
    # Keep‑alive connections are reused across pages for speed.
    async with httpx.AsyncClient(
        timeout=30,
        headers=headers,
        follow_redirects=True,
        verify=ssl_verify,
        limits=httpx.Limits(max_keepalive_connections=10),
    ) as client:

        pages_visited = 0

        while queue and pages_visited < max_pages:
            url, depth = queue.popleft()

            # Apply URL‑level filters before making a network request
            if _should_skip(url):
                continue
            if _is_stale_year_url(url):
                logger.debug(f"[CRAWLER] Skipping stale URL: {url}")
                continue
            if robots and not robots.can_fetch("*", url):
                logger.debug(f"[CRAWLER] robots.txt disallows: {url}")
                continue

            try:
                # Politeness delay – be respectful to the server
                await asyncio.sleep(polite_delay)
                response = await client.get(url)
                pages_visited += 1
                visited.add(url)

                final_url = str(response.url)

                # Check if the server redirected to a soft 404
                if _is_soft_404(final_url):
                    logger.debug(f"[CRAWLER] Soft 404: {url}")
                    continue

                # Only record successful (200) responses
                if response.status_code != 200:
                    logger.debug(f"[CRAWLER] HTTP {response.status_code}: {url}")
                    continue

                # Save this result – it will be stored in the database later
                results.append({
                    "url":           url,
                    "final_url":     final_url,
                    "depth":         depth,
                    "status_code":   response.status_code,
                    "discovered_at": datetime.now(timezone.utc),
                    "seed_url":      seed_url,
                })

                # Stop following links if we've reached the max depth
                if depth >= max_depth:
                    continue

                # Parse the page and discover new links
                soup = BeautifulSoup(response.text, "lxml")
                for tag in soup.find_all("a", href=True):
                    href   = tag["href"].strip()
                    anchor = tag.get_text(strip=True)

                    # Skip JavaScript links
                    if not href or href.startswith("javascript:"):
                        continue

                    # Resolve relative URLs and strip fragments
                    full_url = urljoin(url, href).split("#")[0]

                    # Only follow links within the same domain
                    if not full_url.startswith("http"):
                        continue
                    if not _same_domain(seed_url, full_url):
                        continue
                    # Skip if already seen or queued
                    if full_url in visited or full_url in queued:
                        continue
                    # Apply filters to the new URL
                    if _should_skip(full_url):
                        continue
                    if _is_stale_year_url(full_url):
                        continue
                    # Only follow if it looks like a tender
                    if not _is_tender_url(full_url, anchor):
                        continue

                    # Add to the BFS queue
                    queue.append((full_url, depth + 1))
                    queued.add(full_url)

            # Specific exception handling for network‑related issues
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


def _persist_crawl_results(db: Session, site_name: str, seed_url: str, urls: List[Dict]) -> None:
    """
    Store discovered URLs in the CrawlResult table.

    Deduplication: URLs are matched by MD5 hash. If a URL already exists,
    its `last_seen_at` timestamp is updated. Otherwise a new row is inserted.

    The whole batch is committed atomically. If the batch commit fails,
    the transaction is rolled back and the error is logged (the crawl
    itself is not affected).
    """
    if not urls:
        return

    now = datetime.now(timezone.utc)
    # Compute hashes for incoming URLs
    incoming_hashes = [hashlib.md5(e["url"].encode()).hexdigest() for e in urls]
    # Fetch all existing hashes in one query
    existing: Set[str] = {
        row[0] for row in
        db.query(models.CrawlResult.url_hash)
        .filter(models.CrawlResult.url_hash.in_(incoming_hashes))
        .all()
    }

    # Process each URL: update if exists, insert if new
    for entry in urls:
        url_hash = hashlib.md5(entry["url"].encode()).hexdigest()
        if url_hash in existing:
            # Update the timestamp and mark as active
            try:
                db.query(models.CrawlResult).filter(
                    models.CrawlResult.url_hash == url_hash
                ).update({"last_seen_at": now, "is_active": True}, synchronize_session=False)
            except Exception as e:
                db.rollback()
                logger.debug(f"[CRAWLER] Update failed for {entry['url'][:80]}: {e}")
        else:
            # Insert a new row
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

    # Commit the batch
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[CRAWLER] Batch commit failed for {site_name}: {e}")


# ------------------------------------------------------------------
# Crawl Targets – list of all municipal/national sites to crawl
# ------------------------------------------------------------------
# Each entry defines:
# - name:     display name (used in logs and as site_name in DB)
# - seed_url: starting URL for the BFS crawl
# - max_depth: how many link levels to follow
# - max_pages: maximum number of pages to visit (prevents runaway crawls)
# ------------------------------------------------------------------
CRAWL_TARGETS: list[Dict] = [
    {"name": "City of Johannesburg",  "seed_url": "https://www.joburg.org.za/work_/TendersQuotations/Pages/Tenders.aspx", "max_depth": 2, "max_pages": 30},
    {"name": "City of Tshwane",       "seed_url": "https://www.tshwane.gov.za/?page_id=2194",                             "max_depth": 2, "max_pages": 30},
    {"name": "City of Ekurhuleni",    "seed_url": "https://www.ekurhuleni.gov.za/tenders",                                "max_depth": 3, "max_pages": 50},
    {"name": "Sedibeng District",     "seed_url": "https://www.sedibeng.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "West Rand District",    "seed_url": "https://www.westranddm.gov.za/tenders",                                "max_depth": 2, "max_pages": 30},
    {"name": "City of Cape Town",     "seed_url": "https://web1.capetown.gov.za/web1/procurementportal/",                 "max_depth": 2, "max_pages": 30},
    {"name": "Stellenbosch",          "seed_url": "https://www.stellenbosch.gov.za/tenders",                              "max_depth": 2, "max_pages": 30},
    {"name": "George Municipality",   "seed_url": "https://www.george.gov.za/tenders",                                    "max_depth": 2, "max_pages": 30},
    {"name": "Garden Route District", "seed_url": "https://www.gardenroute.gov.za/tenders",                               "max_depth": 2, "max_pages": 30},
    {"name": "Cape Winelands",        "seed_url": "https://www.capewinelands.gov.za/tenders",                             "max_depth": 2, "max_pages": 30},
    {"name": "eThekwini Municipality","seed_url": "https://www.durban.gov.za/pages/government/procurement",               "max_depth": 3, "max_pages": 40},
    {"name": "Msunduzi Municipality", "seed_url": "https://www.msunduzi.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "Umgungundlovu District","seed_url": "https://www.umdm.gov.za/tenders",                                      "max_depth": 2, "max_pages": 30},
    {"name": "Ugu District",          "seed_url": "https://www.ugu.gov.za/tenders",                                       "max_depth": 2, "max_pages": 30},
    {"name": "Zululand District",     "seed_url": "https://www.zululand.org.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "Buffalo City Metro",    "seed_url": "https://www.buffalocity.gov.za/tenders",                               "max_depth": 3, "max_pages": 40},
    {"name": "Nelson Mandela Bay",    "seed_url": "https://www.nelsonmandelabay.gov.za/tenders",                          "max_depth": 3, "max_pages": 40},
    {"name": "OR Tambo District",     "seed_url": "https://www.ortambodm.gov.za/tenders",                                 "max_depth": 2, "max_pages": 30},
    {"name": "Amathole District",     "seed_url": "https://www.amathole.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "Mangaung Municipality", "seed_url": "https://www.mangaung.co.za/category/tenders-bids/",                    "max_depth": 2, "max_pages": 30},
    {"name": "Fezile Dabi District",  "seed_url": "https://www.feziledabi.gov.za/tenders",                                "max_depth": 2, "max_pages": 30},
    {"name": "Lejweleputswa District","seed_url": "https://www.lejweleputswa.gov.za/tenders",                             "max_depth": 2, "max_pages": 30},
    {"name": "Polokwane Municipality","seed_url": "https://www.polokwane.gov.za/index.php/tenders",                       "max_depth": 2, "max_pages": 30},
    {"name": "Capricorn District",    "seed_url": "https://www.cdm.org.za/tenders",                                       "max_depth": 2, "max_pages": 30},
    {"name": "Vhembe District",       "seed_url": "https://www.vhembe.gov.za/tenders",                                    "max_depth": 2, "max_pages": 30},
    {"name": "Mopani District",       "seed_url": "https://www.mopani.gov.za/tenders",                                    "max_depth": 2, "max_pages": 30},
    {"name": "Waterberg District",    "seed_url": "https://www.waterberg.gov.za/tenders",                                 "max_depth": 2, "max_pages": 30},
    {"name": "Mbombela Municipality", "seed_url": "https://www.mbombela.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "Ehlanzeni District",    "seed_url": "https://www.ehlanzeni.gov.za/tenders",                                 "max_depth": 2, "max_pages": 30},
    {"name": "Gert Sibande District", "seed_url": "https://www.gertsibande.gov.za/tenders",                               "max_depth": 2, "max_pages": 30},
    {"name": "Nkangala District",     "seed_url": "https://www.nkangaladm.gov.za/tenders",                                "max_depth": 2, "max_pages": 30},
    {"name": "Rustenburg Municipality","seed_url": "https://www.rustenburg.gov.za/tenders",                               "max_depth": 2, "max_pages": 30},
    {"name": "Bojanala District",     "seed_url": "https://www.bojanala.gov.za/tenders",                                  "max_depth": 2, "max_pages": 30},
    {"name": "Ngaka Modiri Molema",   "seed_url": "https://www.nmmdm.gov.za/tenders",                                     "max_depth": 2, "max_pages": 30},
    {"name": "NC Provincial Govt",    "seed_url": "https://www.ncgov.co.za/tenders",                                      "max_depth": 3, "max_pages": 40},
    {"name": "Sol Plaatje Municipality","seed_url": "https://www.solplaatje.org.za/tenders",                              "max_depth": 2, "max_pages": 20},
    {"name": "Frances Baard District","seed_url": "https://francesbaard.gov.za/tenders/",                                 "max_depth": 2, "max_pages": 20},
    {"name": "Namakwa District",      "seed_url": "https://www.namakwa-dm.gov.za/request-for-tenders/",                   "max_depth": 2, "max_pages": 20},
    {"name": "eTenders Portal",       "seed_url": "https://www.etenders.gov.za",                                          "max_depth": 2, "max_pages": 40},
    {"name": "Municipalities.co.za",  "seed_url": "https://municipalities.co.za/tenders",                                 "max_depth": 2, "max_pages": 40},
]


async def run_crawler(db: Optional[Session] = None, polite_delay: float = 1.0) -> Dict[str, List[Dict]]:
    """
    Run the crawler against all configured CRAWL_TARGETS in parallel.

    Concurrency is controlled by MAX_CONCURRENT_SITES (semaphore).

    If a database session is provided (`db`), discovered URLs are
    persisted immediately after each site is crawled.

    Returns:
    A dictionary mapping site name → list of discovered URL dicts.
    """
    sem = asyncio.Semaphore(MAX_CONCURRENT_SITES)
    crawl_index: Dict[str, List[Dict]] = {}

    async def _crawl_one(target: Dict) -> Tuple[str, List[Dict]]:
        """Crawl a single site, respecting the semaphore."""
        name = target.get("name", "Unknown")
        seed = target.get("seed_url", "")
        async with sem:
            try:
                urls = await crawl_site(
                    seed_url=seed,
                    max_depth=target.get("max_depth", DEFAULT_MAX_DEPTH),
                    max_pages=target.get("max_pages", DEFAULT_MAX_PAGES),
                    polite_delay=polite_delay,
                )
                # Persist results to the database if a session was provided
                if db is not None and urls:
                    _persist_crawl_results(db, name, seed, urls)
                return name, urls
            except Exception as e:
                logger.error(f"[CRAWLER] {name} failed: {e}")
                return name, []

    # Run all crawls concurrently
    results = await asyncio.gather(*[_crawl_one(t) for t in CRAWL_TARGETS], return_exceptions=True)

    # Collect results, ignoring task‑level exceptions (already logged)
    for item in results:
        if isinstance(item, Exception):
            logger.error(f"[CRAWLER] Task-level exception: {item}")
            continue
        name, urls = item
        crawl_index[name] = urls

    total_urls = sum(len(v) for v in crawl_index.values())
    sites_ok   = len([v for v in crawl_index.values() if v])
    logger.info(f"[CRAWLER] Complete — {total_urls} URLs from {sites_ok}/{len(CRAWL_TARGETS)} sites")
    return crawl_index