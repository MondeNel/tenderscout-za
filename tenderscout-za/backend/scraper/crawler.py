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

from datetime import datetime, timezone
from loguru import logger


logger = logging.getLogger(__name__)

# =============================================================================
# KEYWORD FILTERING
# =============================================================================
# These keywords determine which links the crawler follows.
# A URL or its anchor text must contain at least one of these to be queued.
# =============================================================================

# Expanded to include SCM, Bulletin, and common SA municipal variants
TENDER_KEYWORDS = [
    # Core English Keywords
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "supply", "contract", "bids", "tenders", "sourcing", "award",
    "scm", "bulletin", "advertised", "advert", "proposal",
    
    # Common SA Municipal Terminology
    "supply-chain", "request-for-quotation", "current-tenders", 
    "formal-quotation", "bidding-document", "tender-bulletin",
    
    # Regional/Afrikaans variants (Found in NC/WC/NW provinces)
    "navraag", "tendernommer", "kwotasie"
]

# Strong anchor keywords — prioritize these for link clicking/following
STRONG_ANCHOR_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "sourcing", "bids", "tenders", "scm", "advertised", 
    "bulletin", "supply chain"
]

# Configuration Constants
MAX_CONCURRENT_SITES = 5  # Adjust based on your server resources
DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_PAGES = 50

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


def _is_stale_year_url(self, url: str) -> bool:
    current_year = datetime.now().year
    years = re.findall(r'20\d{2}', url)
    # Allow current year and previous year for fiscal cycle overlap
    return any(int(y) < (current_year - 1) for y in years)

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

# =============================================================================
# CRAWL TARGETS — Balanced coverage across all 9 provinces
# =============================================================================
# Each province has metropolitan + district municipalities for balanced coverage.
# Dead domains and failing sites have been removed.
# =============================================================================

CRAWL_TARGETS = [
    # =========================================================================
    # GAUTENG (Economic hub — 3 metros)
    # =========================================================================
    {"name": "City of Johannesburg", "seed_url": "https://www.joburg.org.za/work_/TendersQuotations/Pages/Tenders.aspx", "max_depth": 2, "max_pages": 30},
    {"name": "City of Tshwane", "seed_url": "https://www.tshwane.gov.za/?page_id=2194", "max_depth": 2, "max_pages": 30},
    {"name": "City of Ekurhuleni", "seed_url": "https://www.ekurhuleni.gov.za/tenders", "max_depth": 3, "max_pages": 50},
    {"name": "Sedibeng District", "seed_url": "https://www.sedibeng.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "West Rand District", "seed_url": "https://www.westranddm.gov.za/tenders", "max_depth": 2, "max_pages": 30},

    # =========================================================================
    # WESTERN CAPE (Metro + key municipalities + district)
    # =========================================================================
    {"name": "City of Cape Town", "seed_url": "https://web1.capetown.gov.za/web1/procurementportal/", "max_depth": 2, "max_pages": 30},
    {"name": "Stellenbosch Municipality", "seed_url": "https://www.stellenbosch.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Drakenstein Municipality", "seed_url": "https://www.drakenstein.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "George Municipality", "seed_url": "https://www.george.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Garden Route District", "seed_url": "https://www.gardenroute.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Cape Winelands District", "seed_url": "https://www.capewinelands.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Overberg District", "seed_url": "https://www.odm.org.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "West Coast District", "seed_url": "https://www.westcoastdm.co.za/tenders", "max_depth": 2, "max_pages": 30},

    # =========================================================================
    # KWAZULU-NATAL (Metro + key municipalities + districts)
    # =========================================================================
    {"name": "eThekwini Municipality", "seed_url": "https://www.durban.gov.za/pages/government/procurement", "max_depth": 3, "max_pages": 40},
    {"name": "Msunduzi Municipality", "seed_url": "https://www.msunduzi.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Newcastle Municipality", "seed_url": "https://www.newcastle.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Umgungundlovu District", "seed_url": "https://www.umdm.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "King Cetshwayo District", "seed_url": "https://www.kingcetshwayo.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Ugu District", "seed_url": "https://www.ugu.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Zululand District", "seed_url": "https://www.zululand.org.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Harry Gwala District", "seed_url": "https://www.harrygwaladm.gov.za/tenders", "max_depth": 2, "max_pages": 30},

    # =========================================================================
    # EASTERN CAPE (2 metros + key districts)
    # =========================================================================
    {"name": "Buffalo City Metro", "seed_url": "https://www.buffalocity.gov.za/tenders", "max_depth": 3, "max_pages": 40},
    {"name": "Nelson Mandela Bay", "seed_url": "https://www.nelsonmandelabay.gov.za/tenders", "max_depth": 3, "max_pages": 40},
    {"name": "Sarah Baartman District", "seed_url": "https://www.sarahbaartman.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Chris Hani District", "seed_url": "https://www.chrishanidm.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Joe Gqabi District", "seed_url": "https://www.jgdm.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "O.R. Tambo District", "seed_url": "https://www.ortambodm.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Alfred Nzo District", "seed_url": "https://www.andm.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Amathole District", "seed_url": "https://www.amathole.gov.za/tenders", "max_depth": 2, "max_pages": 30},

    # =========================================================================
    # FREE STATE (Metro + all districts)
    # =========================================================================
    {"name": "Mangaung Municipality", "seed_url": "https://www.mangaung.co.za/category/tenders-bids/", "max_depth": 2, "max_pages": 30},
    {"name": "Fezile Dabi District", "seed_url": "https://www.feziledabi.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Lejweleputswa District", "seed_url": "https://www.lejweleputswa.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Thabo Mofutsanyana District", "seed_url": "https://www.thabomofutsanyana.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Xhariep District", "seed_url": "https://www.xhariep.gov.za/tenders", "max_depth": 2, "max_pages": 30},

    # =========================================================================
    # LIMPOPO (Capital + all districts)
    # =========================================================================
    {"name": "Polokwane Municipality", "seed_url": "https://www.polokwane.gov.za/index.php/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Capricorn District", "seed_url": "https://www.cdm.org.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Vhembe District", "seed_url": "https://www.vhembe.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Mopani District", "seed_url": "https://www.mopani.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Waterberg District", "seed_url": "https://www.waterberg.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Sekhukhune District", "seed_url": "https://www.sekhukhunedistrict.gov.za/tenders", "max_depth": 2, "max_pages": 30},

    # =========================================================================
    # MPUMALANGA (Capital + all districts)
    # =========================================================================
    {"name": "Mbombela Municipality", "seed_url": "https://www.mbombela.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Ehlanzeni District", "seed_url": "https://www.ehlanzeni.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Gert Sibande District", "seed_url": "https://www.gertsibande.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Nkangala District", "seed_url": "https://www.nkangaladm.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Steve Tshwete Municipality", "seed_url": "https://www.stevetshwetelm.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Govan Mbeki Municipality", "seed_url": "https://www.govanmbeki.gov.za/tenders", "max_depth": 2, "max_pages": 30},

    # =========================================================================
    # NORTH WEST (Capital + all districts)
    # =========================================================================
    {"name": "Mahikeng Municipality", "seed_url": "https://www.mahikeng.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Rustenburg Municipality", "seed_url": "https://www.rustenburg.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Bojanala District", "seed_url": "https://www.bojanala.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Dr Kenneth Kaunda District", "seed_url": "https://www.kaundadistrict.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Ngaka Modiri Molema District", "seed_url": "https://www.nmmdm.gov.za/tenders", "max_depth": 2, "max_pages": 30},
    {"name": "Dr Ruth Segomotsi Mompati District", "seed_url": "https://www.ruthsegomotsimompati.gov.za/tenders", "max_depth": 2, "max_pages": 30},

    # =========================================================================
    # NORTHERN CAPE (Provincial + key municipalities)
    # =========================================================================
    {"name": "Northern Cape Provincial Government", "seed_url": "https://www.ncgov.co.za/tenders", "max_depth": 3, "max_pages": 40},
    {"name": "Northern Cape DEDAT", "seed_url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824", "max_depth": 1, "max_pages": 20},
    {"name": "Sol Plaatje Municipality", "seed_url": "https://www.solplaatje.org.za/tenders", "max_depth": 2, "max_pages": 20},
    {"name": "Frances Baard District", "seed_url": "https://francesbaard.gov.za/tenders/", "max_depth": 2, "max_pages": 20},
    {"name": "ZF Mgcawu District", "seed_url": "https://www.zfm-dm.gov.za/documents/?dir=4302", "max_depth": 1, "max_pages": 20},
    {"name": "Namakwa District", "seed_url": "https://www.namakwa-dm.gov.za/request-for-tenders/", "max_depth": 2, "max_pages": 20},
    {"name": "Pixley ka Seme District", "seed_url": "https://www.pksdm.gov.za/tenders.html", "max_depth": 2, "max_pages": 20},
    {"name": "John Taolo Gaetsewe District", "seed_url": "https://taologaetsewe.gov.za/request-for-quotations/", "max_depth": 2, "max_pages": 20},

    # =========================================================================
    # AGGREGATORS — Nationwide coverage (scrape ALL provinces)
    # =========================================================================
    {"name": "eTenders Portal (National)", "seed_url": "https://www.etenders.gov.za", "max_depth": 2, "max_pages": 40},
    {"name": "Municipalities.co.za", "seed_url": "https://municipalities.co.za/tenders", "max_depth": 2, "max_pages": 40},
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

async def run_crawler(db: Optional[any] = None) -> Dict[str, List[Dict]]:
    """
    Orchestrates the BFS crawl across all CRAWL_TARGETS with concurrency limiting.
    
    Implements a Semaphore to prevent overwhelming government servers and 
    uses modern UTC handling for Python 3.12+.
    """
    # 1. Initialize concurrency control
    sem = asyncio.Semaphore(MAX_CONCURRENT_SITES)
    crawl_index: Dict[str, List[Dict]] = {}
    
    # Modern UTC timestamp for logging/metadata
    start_time = datetime.now(timezone.utc)
    logger.info(f"[CRAWLER] Starting batch crawl for {len(CRAWL_TARGETS)} targets at {start_time}")

    async def crawl_one(target: Dict) -> tuple:
        """
        Wrapped crawler logic for a single municipality.
        Uses a semaphore to limit simultaneous connections.
        """
        name = target.get("name", "Unknown")
        seed = target.get("seed_url")
        
        async with sem:
            try:
                logger.info(f"[CRAWLER] [{name}] Queueing crawl...")
                
                # Execute the BFS crawl
                urls = await crawl_site(
                    seed_url=seed,
                    max_depth=target.get("max_depth", DEFAULT_MAX_DEPTH),
                    max_pages=target.get("max_pages", DEFAULT_MAX_PAGES),
                )
                
                # Immediate Persistence: Don't wait for the whole batch to finish
                if db is not None and urls:
                    try:
                        # Ensure your persistence logic handles session commits safely
                        _persist_crawl_results(db, name, seed, urls)
                        logger.success(f"[CRAWLER] [{name}] Persisted {len(urls)} URLs.")
                    except Exception as db_err:
                        logger.error(f"[DATABASE] [{name}] Persistence failed: {db_err}")
                
                return name, urls

            except Exception as e:
                logger.error(f"[CRAWLER] [{name}] Failed during execution: {str(e)}")
                return name, []

    # 2. Create tasks with the Semaphore wrapper
    tasks = [crawl_one(t) for t in CRAWL_TARGETS]
    
    # 3. Execute concurrently and gather results
    # return_exceptions=True prevents one crash from killing the whole batch
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. Post-processing and Metric Reporting
    for item in results_raw:
        if isinstance(item, Exception):
            # This handles errors that occurred outside the try/except in crawl_one
            logger.critical(f"[CRAWLER] Fatal task error: {item}")
            continue
            
        name, urls = item
        crawl_index[name] = urls
        if urls:
            logger.info(f"[CRAWLER] [{name}] Completed: {len(urls)} URLs found.")
        else:
            logger.warning(f"[CRAWLER] [{name}] Completed: 0 URLs found.")

    # 5. Final Summary
    total_urls = sum(len(urls) for urls in crawl_index.values())
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    
    logger.info(
        f"--- [CRAWLER SUMMARY] ---\n"
        f"Total Sites Attempted: {len(CRAWL_TARGETS)}\n"
        f"Sites with Data:      {len([v for v in crawl_index.values() if v])}\n"
        f"Total URLs Discovered: {total_urls}\n"
        f"Execution Time:        {duration:.2f}s\n"
        f"-------------------------"
    )
    
    return crawl_index