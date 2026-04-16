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
from sqlalchemy.orm import Session
from database import SessionLocal
import models

logger = logging.getLogger(__name__)

TENDER_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "supply", "contract", "bids", "tenders"]
SKIP_PATH_FRAGMENTS = ["/login", "/admin", "/logout", "/register", "/wp-admin", "/cart", "/checkout", "?s=", "/tag/", "/category/feed", "/newsletter", "/news-and-media", "/media-releases", "/budget/", "/performance-contracts", "/long-term-borrowing", "/annual-report", "/financial-statement", "/organogram", "/vacancy", "/vacancies", "/council", "/gallery"]
SOFT_404_FRAGMENTS = ["/help?e=404", "/error", "/not-found", "404", "/page-not-found"]
STRONG_ANCHOR_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "sourcing", "bids", "tenders"]
SKIP_TENDER_PATHS = ['/awarded', '/closed', '/archive']

_robots_cache = {}

def _is_tender_url(url: str, anchor_text: str = "") -> bool:
    url_lower = url.lower()
    anchor_lower = anchor_text.lower()
    # Negative check first
    if any(frag in url_lower for frag in SKIP_TENDER_PATHS):
        return False
    if any(kw in url_lower for kw in TENDER_KEYWORDS):
        return True
    if any(kw in anchor_lower for kw in STRONG_ANCHOR_KEYWORDS):
        return True
    return False

def _same_domain(base: str, url: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc

def _should_skip(url: str) -> bool:
    lower = url.lower()
    if any(lower.endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]):
        return True
    if any(frag in lower for frag in SKIP_PATH_FRAGMENTS):
        return True
    if "download=" in lower:
        return True
    return False

def _is_stale_year_url(url: str) -> bool:
    match = re.search(r'year=(20[0-9]{2})', url)
    if match:
        year = int(match.group(1))
        return year < datetime.utcnow().year
    return False

def _is_soft_404(final_url: str) -> bool:
    lower = final_url.lower()
    return any(frag in lower for frag in SOFT_404_FRAGMENTS)

def _load_robots(base_url: str) -> Optional[RobotFileParser]:
    domain = urlparse(base_url).netloc
    if domain in _robots_cache:
        return _robots_cache[domain]
    try:
        rp = RobotFileParser()
        robots_url = f"{urlparse(base_url).scheme}://{domain}/robots.txt"
        rp.set_url(robots_url)
        rp.read()
        _robots_cache[domain] = rp
        return rp
    except Exception:
        return None

def is_url_crawled(url: str, db: Session) -> bool:
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return db.query(models.CrawlResult).filter(models.CrawlResult.url_hash == url_hash).first() is not None

async def crawl_site(
    seed_url: str,
    max_depth: int = 3,
    max_pages: int = 50,
    polite_delay: float = 1.0,
    db: Session = None
) -> List[Dict]:
    visited: Set[str] = set()
    results: List[Dict] = []
    queue: List[tuple] = [(seed_url, 0)]
    robots = _load_robots(seed_url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True, verify=True) as client:
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
                final_url = str(response.url)
                if _is_soft_404(final_url):
                    logger.debug(f"[CRAWLER] Soft 404: {url} → {final_url}")
                    continue
                if response.status_code != 200:
                    logger.debug(f"[CRAWLER] {response.status_code} — {url}")
                    continue
                if db and is_url_crawled(url, db):
                    logger.debug(f"[CRAWLER] Already crawled: {url}")
                else:
                    results.append({
                        "url": url,
                        "depth": depth,
                        "status_code": response.status_code,
                        "discovered_at": datetime.utcnow().isoformat(),
                        "seed_url": seed_url,
                    })
                if depth >= max_depth:
                    continue
                soup = BeautifulSoup(response.text, "lxml")
                for tag in soup.find_all("a", href=True):
                    href = tag["href"].strip()
                    anchor = tag.get_text(strip=True)
                    full_url = urljoin(url, href).split("#")[0]
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
            except Exception as e:
                logger.error(f"[CRAWLER] Error {url}: {e}")
    logger.info(f"[CRAWLER] {seed_url} → {len(results)} new URLs ({pages_visited} pages visited)")
    return results

def store_crawl_results(db: Session, site_name: str, seed_url: str, urls: list):
    for entry in urls:
        url = entry["url"]
        url_hash = hashlib.md5(url.encode()).hexdigest()
        existing = db.query(models.CrawlResult).filter(models.CrawlResult.url_hash == url_hash).first()
        if existing:
            existing.last_seen_at = datetime.utcnow()
            existing.is_active = True
        else:
            db.add(models.CrawlResult(
                site_name=site_name,
                seed_url=seed_url,
                discovered_url=url,
                depth=entry.get("depth", 0),
                status_code=entry.get("status_code", 200),
                url_hash=url_hash,
            ))
    db.commit()

async def run_crawler(db: Session = None) -> Dict[str, List[Dict]]:
    from scraper.sites.city_portals import CITY_PORTALS
    CRAWL_TARGETS = [
        {"name": c["name"], "seed_url": c["url"], "max_depth": 2, "max_pages": 30}
        for c in CITY_PORTALS
    ]
    async def crawl_one(target: Dict) -> tuple:
        urls = await crawl_site(
            seed_url=target["seed_url"],
            max_depth=target.get("max_depth", 2),
            max_pages=target.get("max_pages", 30),
            db=db
        )
        return target["name"], urls
    tasks = [crawl_one(t) for t in CRAWL_TARGETS]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)
    crawl_index: Dict[str, List[Dict]] = {}
    for item in results_raw:
        if isinstance(item, Exception):
            logger.error(f"[CRAWLER] Task failed: {item}")
            continue
        name, urls = item
        crawl_index[name] = urls
        if db:
            store_crawl_results(db, name, next((t["seed_url"] for t in CRAWL_TARGETS if t["name"] == name), ""), urls)
        logger.info(f"[CRAWLER] {name}: {len(urls)} new URLs")
    return crawl_index