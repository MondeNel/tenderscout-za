"""
crawler.py — Tender URL Discovery Crawler
==========================================
Breadth-First Search (BFS) web crawler that discovers tender-related URLs
by starting from seed URLs and following links containing tender keywords.

This is a URL DISCOVERY system — it finds WHERE tenders might be located,
but does NOT extract the actual tender data (title, closing date, etc.).

The discovered URLs are saved to the CrawlResult table. A separate scraper
pipeline should then visit these URLs to extract full tender details.

Architecture:
    - TENDER_KEYWORDS: Terms that indicate a page might contain tenders
    - SKIP_PATH_FRAGMENTS: URL patterns to avoid (admin, login, media, etc.)
    - crawl_site(): BFS crawler for a single seed URL
    - CRAWL_TARGETS: List of seed URLs to crawl (filtered to working sites)
    - run_crawler(): Concurrent crawler across all targets
    - _persist_crawl_results(): Saves discovered URLs to database

NOTE: Dead domains have been removed from CRAWL_TARGETS to reduce noise.
"""

import httpx
import asyncio
import logging
import re
import hashlib
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# =============================================================================
# KEYWORD FILTERING
# =============================================================================
# These keywords determine which links the crawler follows.
# A URL or its anchor text must contain at least one of these to be queued.
# =============================================================================

TENDER_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "supply", "contract", "bids", "tenders", "sourcing", "award",
]

# Strong anchor keywords — if anchor text contains these, follow even if URL doesn't
STRONG_ANCHOR_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "sourcing", "bids", "tenders",
]

# =============================================================================
# URL FILTERING — Patterns to skip
# =============================================================================

# Path fragments that indicate non-tender pages (admin, login, media, etc.)
SKIP_PATH_FRAGMENTS = [
    "/login", "/admin", "/logout", "/register", "/wp-admin",
    "/cart", "/checkout", "?s=", "/tag/", "/category/feed",
    "/newsletter", "/news-and-media", "/media-releases", "/budget/",
    "/performance-contracts", "/long-term-borrowing", "/annual-report",
    "/financial-statement", "/organogram", "/vacancy", "/vacancies",
    "/council", "/gallery", "/awarded-tenders", "/tenders-awarded",
]

# URL fragments that indicate a soft 404 or error page
SOFT_404_FRAGMENTS = [
    "/help?e=404", "/error", "/not-found", "404", "/page-not-found",
]

# File extensions to skip (binary files, not HTML pages)
SKIP_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".jpg", ".png", ".gif"]

# Regex to extract year from URL (for stale content filtering)
_STALE_YEAR_RE = re.compile(r'year=(20[0-9]{2})')


# =============================================================================
# URL VALIDATION FUNCTIONS
# =============================================================================

def _is_tender_url(url: str, anchor_text: str = "") -> bool:
    """
    Determine if a URL is likely to contain tender information.
    
    Checks both the URL itself and the anchor text for tender keywords.
    
    Args:
        url: Full URL to check
        anchor_text: Text of the link (if available)
        
    Returns:
        True if URL or anchor contains tender keywords
    """
    url_lower = url.lower()
    anchor_lower = anchor_text.lower()
    
    # Check URL for tender keywords
    if any(kw in url_lower for kw in TENDER_KEYWORDS):
        return True
    
    # Check anchor text for strong keywords (more reliable than URL)
    if any(kw in anchor_lower for kw in STRONG_ANCHOR_KEYWORDS):
        return True
    
    return False


def _same_domain(base: str, url: str) -> bool:
    """
    Check if two URLs belong to the same domain.
    
    This prevents the crawler from wandering off to external sites.
    
    Args:
        base: Base/seed URL
        url: URL to check
        
    Returns:
        True if same domain
    """
    return urlparse(url).netloc == urlparse(base).netloc


def _should_skip(url: str) -> bool:
    """
    Determine if a URL should be skipped entirely.
    
    Skips:
        - Binary files (PDF, DOC, etc.)
        - Admin/login pages
        - Media/news pages
        - Download links
        - Awarded/closed tender pages
    
    Args:
        url: URL to check
        
    Returns:
        True if URL should be skipped
    """
    lower = url.lower()
    
    # Skip binary files
    if any(lower.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    
    # Skip known non-tender path patterns
    if any(frag in lower for frag in SKIP_PATH_FRAGMENTS):
        return True
    
    # Skip download links
    if "download=" in lower:
        return True
    
    return False


def _is_stale_year_url(url: str) -> bool:
    """
    Check if URL contains a year parameter that's in the past.
    
    Example: ?year=2023 would be stale in 2026.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL references a past year
    """
    match = _STALE_YEAR_RE.search(url)
    if match:
        year = int(match.group(1))
        return year < datetime.utcnow().year
    return False


def _is_soft_404(final_url: str) -> bool:
    """
    Check if the final URL (after redirects) indicates a 404/error page.
    
    Args:
        final_url: URL after following redirects
        
    Returns:
        True if URL appears to be an error page
    """
    lower = final_url.lower()
    return any(frag in lower for frag in SOFT_404_FRAGMENTS)


def _load_robots(base_url: str) -> Optional[RobotFileParser]:
    """
    Load and parse robots.txt for a domain.
    
    Respects robots.txt to be a good web citizen.
    
    Args:
        base_url: Base URL of the site
        
    Returns:
        RobotFileParser instance, or None if robots.txt can't be loaded
    """
    try:
        rp = RobotFileParser()
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp.set_url(robots_url)
        rp.read()
        return rp
    except Exception:
        return None


# =============================================================================
# BFS CRAWLER
# =============================================================================

async def crawl_site(
    seed_url: str,
    max_depth: int = 3,
    max_pages: int = 50,
    polite_delay: float = 1.0,
) -> List[Dict]:
    """
    Breadth-First Search crawler for a single seed URL.
    
    Starts at seed_url, follows links containing tender keywords, and returns
    a list of verified live URLs that likely contain tender information.
    
    The crawler:
        - Respects robots.txt
        - Stays on the same domain
        - Skips binary files and non-tender pages
        - Implements polite delays between requests
    
    Args:
        seed_url: Starting URL for the crawl
        max_depth: Maximum link depth to follow (0 = only seed_url)
        max_pages: Maximum number of pages to visit (safety limit)
        polite_delay: Seconds to wait between requests
        
    Returns:
        List of dicts, each containing:
            - url: Discovered URL
            - final_url: URL after redirects
            - depth: How many links from seed
            - status_code: HTTP status
            - discovered_at: ISO timestamp
            - seed_url: Original seed URL
    """
    visited: Set[str] = set()
    results: List[Dict] = []
    queue: List[Tuple[str, int]] = [(seed_url, 0)]  # (url, depth)
    
    # Load robots.txt for politeness
    robots = _load_robots(seed_url)

    # Browser-like headers to avoid blocking
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    async with httpx.AsyncClient(
        timeout=30,  # Increased from 15 to 30 for slow sites
        headers=headers, 
        follow_redirects=True, 
        verify=False,
        limits=httpx.Limits(max_keepalive_connections=10),
    ) as client:
        pages_visited = 0

        while queue and pages_visited < max_pages:
            url, depth = queue.pop(0)  # BFS: take from front

            # -----------------------------------------------------------------
            # Pre-visit validation
            # -----------------------------------------------------------------
            if url in visited:
                continue
            if _should_skip(url):
                continue
            if _is_stale_year_url(url):
                logger.debug(f"[CRAWLER] Skipping stale year URL: {url}")
                continue
            if robots and not robots.can_fetch("*", url):
                logger.debug(f"[CRAWLER] robots.txt disallows: {url}")
                continue

            visited.add(url)

            try:
                # Be polite — wait between requests
                await asyncio.sleep(polite_delay)
                
                response = await client.get(url)
                pages_visited += 1

                # -----------------------------------------------------------------
                # Post-visit validation
                # -----------------------------------------------------------------
                final_url = str(response.url)
                
                # Check for soft 404 after redirects
                if _is_soft_404(final_url):
                    logger.debug(f"[CRAWLER] Soft 404: {url} → {final_url}")
                    continue

                if response.status_code != 200:
                    logger.debug(f"[CRAWLER] {response.status_code} — {url}")
                    continue

                # -----------------------------------------------------------------
                # Record successful discovery
                # -----------------------------------------------------------------
                results.append({
                    "url": url,
                    "final_url": final_url,  # After redirects
                    "depth": depth,
                    "status_code": response.status_code,
                    "discovered_at": datetime.utcnow().isoformat(),
                    "seed_url": seed_url,
                })

                # -----------------------------------------------------------------
                # Don't follow links if we've reached max depth
                # -----------------------------------------------------------------
                if depth >= max_depth:
                    continue

                # -----------------------------------------------------------------
                # Extract and queue new links
                # -----------------------------------------------------------------
                soup = BeautifulSoup(response.text, "lxml")
                
                for tag in soup.find_all("a", href=True):
                    href = tag["href"].strip()
                    anchor = tag.get_text(strip=True)
                    
                    # Skip empty or javascript links
                    if not href or href.startswith("javascript:"):
                        continue
                    
                    # Resolve relative URLs
                    full_url = urljoin(url, href).split("#")[0]  # Remove fragments

                    # Validation for queuing
                    if not full_url.startswith("http"):
                        continue
                    if not _same_domain(seed_url, full_url):
                        continue
                    if full_url in visited:
                        continue
                    if _should_skip(full_url):
                        continue
                    if _is_stale_year_url(full_url):
                        continue
                    if not _is_tender_url(full_url, anchor):
                        continue

                    # Add to queue for later visiting
                    queue.append((full_url, depth + 1))

            except httpx.TimeoutException:
                logger.warning(f"[CRAWLER] Timeout: {url}")
            except httpx.ConnectError as e:
                logger.warning(f"[CRAWLER] Connection error {url}: {e}")
            except httpx.ReadError as e:
                logger.warning(f"[CRAWLER] Read error (server disconnect) {url}: {e}")
            except httpx.RequestError as e:
                logger.warning(f"[CRAWLER] Request error {url}: {e}")
            except Exception as e:
                logger.error(f"[CRAWLER] Unexpected error {url}: {e}")

    logger.info(
        f"[CRAWLER] {seed_url} → {len(results)} live tender URLs "
        f"({pages_visited} pages visited)"
    )
    return results


# =============================================================================
# CRAWL TARGETS — Filtered to working sites only
# =============================================================================
# Dead domains (DNS failures) have been removed to reduce noise.
# These are the starting points for the crawler to discover tender pages.
# =============================================================================

CRAWL_TARGETS = [
    # =========================================================================
    # METROS — Confirmed working
    # =========================================================================
    {"name": "City of Cape Town",      "seed_url": "https://web1.capetown.gov.za/web1/procurementportal/", "max_depth": 2, "max_pages": 30},
    {"name": "City of Johannesburg", "seed_url": "https://www.joburg.org.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "City of Ekurhuleni",     "seed_url": "https://www.ekurhuleni.gov.za/tenders",                "max_depth": 3, "max_pages": 50},
    {"name": "Buffalo City Metro",     "seed_url": "https://www.buffalocity.gov.za/tenders",               "max_depth": 3, "max_pages": 40},
    {"name": "Nelson Mandela Bay",     "seed_url": "https://www.nelsonmandelabay.gov.za/tenders",          "max_depth": 3, "max_pages": 40},
    
    # =========================================================================
    # NORTHERN CAPE — Working sites only
    # =========================================================================
    {"name": "Northern Cape Provincial Government", "seed_url": "https://www.ncgov.co.za/tenders",         "max_depth": 3, "max_pages": 40},
    {"name": "Northern Cape DEDAT",    "seed_url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824", "max_depth": 1, "max_pages": 20},
    {"name": "Sol Plaatje Municipality", "seed_url": "https://www.solplaatje.org.za/tenders",              "max_depth": 2, "max_pages": 20},
    {"name": "Richtersveld Municipality", "seed_url": "https://www.richtersveld.gov.za/tenders",           "max_depth": 2, "max_pages": 15},
    {"name": "Hantam Municipality",     "seed_url": "https://www.hantam.gov.za/tenders",                   "max_depth": 2, "max_pages": 15},
    {"name": "Karoo Hoogland Municipality", "seed_url": "https://www.karoohoogland.gov.za/tenders",        "max_depth": 2, "max_pages": 15},
    {"name": "Siyathemba Municipality", "seed_url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders", "max_depth": 2, "max_pages": 20},
    {"name": "Gamagara Municipality",   "seed_url": "https://www.gamagara.gov.za/tenders",                 "max_depth": 2, "max_pages": 15},
    
    # =========================================================================
    # AGGREGATORS — Nationwide coverage
    # =========================================================================
    {"name": "Municipalities.co.za (Northern Cape)", "seed_url": "https://municipalities.co.za/tenders/index/7/northern-cape", "max_depth": 2, "max_pages": 30},
    {"name": "eTenders Portal (National)", "seed_url": "https://www.etenders.gov.za",                       "max_depth": 2, "max_pages": 40},
    {"name": "EasyTenders (Northern Cape)", "seed_url": "https://easytenders.co.za/tenders-in/northern-cape", "max_depth": 2, "max_pages": 30},
    {"name": "OnlineTenders (Northern Cape)", "seed_url": "https://www.onlinetenders.co.za/tenders/northern-cape", "max_depth": 2, "max_pages": 30},
    {"name": "TenderAlerts",             "seed_url": "https://tenderalerts.co.za",                          "max_depth": 2, "max_pages": 30},
    
    # NOTE: These sites have issues and are disabled for now:
    # - City of Tshwane: Timeout issues
    # - eThekwini Municipality: URL may have changed
    # - Mangaung Municipality: URL may have changed
    # - sa-tenders.co.za: Timeout issues
    # - tendersbulletins.co.za: DNS failure
    # - Many Northern Cape municipalities: DNS failures (domains don't exist)
]


# =============================================================================
# DATABASE PERSISTENCE
# =============================================================================

def _persist_crawl_results(db, site_name: str, seed_url: str, urls: List[Dict]):
    """
    Save discovered URLs to the CrawlResult table.
    
    Args:
        db: SQLAlchemy database session
        site_name: Name of the site being crawled
        seed_url: Original seed URL
        urls: List of discovered URL dicts from crawl_site()
    """
    if db is None:
        return
        
    try:
        import models
        from sqlalchemy.exc import IntegrityError
        
        for entry in urls:
            url_hash = hashlib.md5(entry["url"].encode()).hexdigest()
            
            try:
                existing = db.query(models.CrawlResult).filter(
                    models.CrawlResult.url_hash == url_hash
                ).first()
                
                if existing:
                    # Update existing record
                    existing.last_seen_at = datetime.utcnow()
                    existing.is_active = True
                    existing.status_code = entry.get("status_code", existing.status_code)
                else:
                    # Create new record
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
                    
                db.commit()
                
            except IntegrityError:
                db.rollback()
                logger.debug(f"[CRAWLER] Duplicate URL skipped: {entry['url'][:80]}")
            except Exception as e:
                db.rollback()
                logger.error(f"[CRAWLER] Persist error for {entry['url'][:80]}: {e}")
                
    except Exception as e:
        logger.error(f"[CRAWLER] DB persist failed for {site_name}: {e}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def run_crawler(db=None) -> Dict[str, List[Dict]]:
    """
    Run the crawler across all CRAWL_TARGETS concurrently.
    
    This is the main entry point that orchestrates crawling all seed URLs.
    Results are both returned and persisted to the database (if db provided).
    
    Args:
        db: Optional SQLAlchemy database session for persistence
        
    Returns:
        Dictionary mapping site_name → list of discovered URL dicts
    """
    async def crawl_one(target: Dict) -> tuple:
        """Crawl a single target and return (name, urls)."""
        try:
            urls = await crawl_site(
                seed_url=target["seed_url"],
                max_depth=target.get("max_depth", 3),
                max_pages=target.get("max_pages", 50),
            )
            
            # Persist to database if session provided
            if db is not None and urls:
                _persist_crawl_results(db, target["name"], target["seed_url"], urls)
                
            return target["name"], urls
        except Exception as e:
            logger.error(f"[CRAWLER] {target['name']} failed: {e}")
            return target["name"], []

    # Run all crawls concurrently
    tasks = [crawl_one(t) for t in CRAWL_TARGETS]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    crawl_index: Dict[str, List[Dict]] = {}
    for item in results_raw:
        if isinstance(item, Exception):
            logger.error(f"[CRAWLER] Site task failed: {item}")
            continue
            
        name, urls = item
        crawl_index[name] = urls
        logger.info(f"[CRAWLER] {name}: {len(urls)} discovered URLs")

    total_urls = sum(len(urls) for urls in crawl_index.values())
    logger.info(f"[CRAWLER] TOTAL: {total_urls} URLs across {len(crawl_index)} sites")
    
    return crawl_index