import httpx
import asyncio
import logging
import re
import hashlib
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from typing import List, Dict, Set, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Keywords that suggest a URL is tender-related
TENDER_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "supply", "contract", "bids", "tenders", "sourcing", "award"
]

# Paths disallowed regardless of robots.txt (common admin/login paths)
SKIP_PATH_FRAGMENTS = [
    "/login", "/admin", "/logout", "/register", "/wp-admin",
    "/cart", "/checkout", "?s=", "/tag/", "/category/feed",
    "/newsletter",
    "/news-and-media",
    "/media-releases",
    "/budget/",
    "/performance-contracts",
    "/long-term-borrowing",
    "/annual-report",
    "/financial-statement",
    "/organogram",
    "/vacancy",
    "/vacancies",
    "/council",
    "/gallery",
]

# Final URL fragments that indicate a soft 404 / error page
SOFT_404_FRAGMENTS = [
    "/help?e=404", "/error", "/not-found", "404", "/page-not-found",
]

# Regex to detect stale year query params (e.g. ?year=2023)
_STALE_YEAR_RE = re.compile(r'year=(20[0-9]{2})')


STRONG_ANCHOR_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "sourcing", "bids", "tenders",
]

def _is_tender_url(url: str, anchor_text: str = "") -> bool:
    url_lower = url.lower()
    anchor_lower = anchor_text.lower()
    # URL path contains a keyword � structural signal, always accept
    if any(kw in url_lower for kw in TENDER_KEYWORDS):
        return True
    # Anchor-text-only match � require stronger/more specific keyword
    # to avoid false positives like "performance contracts"
    if any(kw in anchor_lower for kw in STRONG_ANCHOR_KEYWORDS):
        return True
    return False


def _same_domain(base: str, url: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc


def _should_skip(url: str) -> bool:
    lower = url.lower()
    # Skip downloadable documents — we want listing pages only
    if any(lower.endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]):
        return True
    # Skip common non-tender admin/nav paths
    if any(frag in lower for frag in SKIP_PATH_FRAGMENTS):
        return True
    # Phoca Download (Joomla) triggers file downloads via query param — skip them
    # e.g. ?option=com_phocadownload&...&download=355:some-file
    if "download=" in lower:
        return True
    return False


def _is_stale_year_url(url: str) -> bool:
    """Returns True if the URL targets a year older than the current year."""
    match = _STALE_YEAR_RE.search(url)
    if match:
        year = int(match.group(1))
        return year < datetime.utcnow().year
    return False


def _is_soft_404(final_url: str) -> bool:
    """
    Detects soft 404s — pages where the server followed a redirect and
    returned HTTP 200 but landed on an error/not-found page.
    """
    lower = final_url.lower()
    return any(frag in lower for frag in SOFT_404_FRAGMENTS)


def _load_robots(base_url: str) -> Optional[RobotFileParser]:
    try:
        rp = RobotFileParser()
        robots_url = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}/robots.txt"
        rp.set_url(robots_url)
        rp.read()
        return rp
    except Exception:
        return None


async def crawl_site(
    seed_url: str,
    max_depth: int = 3,
    max_pages: int = 50,
    polite_delay: float = 1.0,
) -> List[Dict]:
    """
    BFS crawler. Starts at seed_url, walks internal links up to max_depth.
    Returns a list of verified live URLs that appear to be tender-related.

    Each result dict contains:
        url, depth, status_code, discovered_at, seed_url
    """
    visited: Set[str] = set()
    results: List[Dict] = []
    # Queue entries: (url, depth)
    queue: List[tuple] = [(seed_url, 0)]
    robots = _load_robots(seed_url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=15,
        headers=headers,
        follow_redirects=True,
        verify=False,
    ) as client:
        pages_visited = 0

        while queue and pages_visited < max_pages:
            url, depth = queue.pop(0)

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
                await asyncio.sleep(polite_delay)
                response = await client.get(url)
                pages_visited += 1

                # Detect soft 404s — redirected to an error page but returned 200
                final_url = str(response.url)
                if _is_soft_404(final_url):
                    logger.debug(f"[CRAWLER] Soft 404: {url} → {final_url}")
                    continue

                if response.status_code != 200:
                    logger.debug(f"[CRAWLER] {response.status_code} — {url}")
                    continue

                # Record as a verified live tender-related URL
                results.append({
                    "url": url,
                    "depth": depth,
                    "status_code": response.status_code,
                    "discovered_at": datetime.utcnow().isoformat(),
                    "seed_url": seed_url,
                })

                # Don't go deeper than max_depth
                if depth >= max_depth:
                    continue

                # Parse page and enqueue internal tender links
                soup = BeautifulSoup(response.text, "lxml")
                for tag in soup.find_all("a", href=True):
                    href = tag["href"].strip()
                    anchor = tag.get_text(strip=True)

                    # Resolve relative URLs
                    full_url = urljoin(url, href)
                    # Strip fragment identifiers
                    full_url = full_url.split("#")[0]

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

                    queue.append((full_url, depth + 1))

            except httpx.TimeoutException:
                logger.warning(f"[CRAWLER] Timeout: {url}")
            except httpx.RequestError as e:
                logger.warning(f"[CRAWLER] Request error {url}: {e}")
            except Exception as e:
                logger.error(f"[CRAWLER] Unexpected error {url}: {e}")

    logger.info(
        f"[CRAWLER] {seed_url} → {len(results)} live tender URLs "
        f"({pages_visited} pages visited)"
    )
    return results


# ---------------------------------------------------------------------------
# Site configs — mirrors CITY_PORTALS but adds crawler tuning per site
# ---------------------------------------------------------------------------

CRAWL_TARGETS = [
    {
        "name": "City of Cape Town",
        "seed_url": "https://www.capetown.gov.za/work/tenders",
        "max_depth": 2,
        "max_pages": 30,
    },
    {
        "name": "City of Johannesburg",
        "seed_url": "https://www.joburg.org.za/work_/Pages/Tenders/Tenders.aspx",
        "max_depth": 2,
        "max_pages": 30,
    },
    {
        "name": "City of Tshwane",
        "seed_url": "https://www.tshwane.gov.za/Sites/Departments/Financial-Services/Pages/Tenders.aspx",
        "max_depth": 2,
        "max_pages": 30,
    },
    {
        "name": "City of Ekurhuleni",
        "seed_url": "https://www.ekurhuleni.gov.za/tenders",
        "max_depth": 3,
        "max_pages": 50,
    },
    {
        "name": "eThekwini Municipality",
        "seed_url": "https://www.durban.gov.za/City_Services/finance/SCM/Pages/Quotations-Tenders.aspx",
        "max_depth": 2,
        "max_pages": 30,
    },
    {
        "name": "Buffalo City Metro",
        "seed_url": "https://www.buffalocity.gov.za/tenders",
        "max_depth": 3,
        "max_pages": 40,
    },
    {
        "name": "Mangaung Municipality",
        "seed_url": "https://www.mangaung.co.za/tenders",
        "max_depth": 2,
        "max_pages": 30,
    },
    {
        "name": "Nelson Mandela Bay",
        "seed_url": "https://www.nelsonmandelabay.gov.za/tenders",
        "max_depth": 3,
        "max_pages": 40,
    },
    {
        "name": "Siyathemba Municipality",
        "seed_url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders",
        "max_depth": 2,
        "max_pages": 20,
    },
    {
        "name": "Northern Cape DEDAT",
        "seed_url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824",
        "max_depth": 1,
        "max_pages": 20,
    },
    {
        "name": "sa-tenders.co.za",
        "seed_url": "https://sa-tenders.co.za/tenders",
        "max_depth": 2,
        "max_pages": 40,
    },
]


async def run_crawler() -> Dict[str, List[Dict]]:
    """
    Runs the crawler across all CRAWL_TARGETS concurrently (per-site sequential
    to stay polite, sites run in parallel).

    Returns a dict keyed by site name → list of verified live tender URLs.
    """
    async def crawl_one(target: Dict) -> tuple:
        urls = await crawl_site(
            seed_url=target["seed_url"],
            max_depth=target.get("max_depth", 3),
            max_pages=target.get("max_pages", 50),
        )
        return target["name"], urls

    tasks = [crawl_one(t) for t in CRAWL_TARGETS]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    crawl_index: Dict[str, List[Dict]] = {}
    for item in results_raw:
        if isinstance(item, Exception):
            logger.error(f"[CRAWLER] Site task failed: {item}")
            continue
        name, urls = item
        crawl_index[name] = urls
        logger.info(f"[CRAWLER] {name}: {len(urls)} verified URLs")

    return crawl_index