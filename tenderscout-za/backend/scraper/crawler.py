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

TENDER_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "supply", "contract", "bids", "tenders", "sourcing", "award",
]

SKIP_PATH_FRAGMENTS = [
    "/login", "/admin", "/logout", "/register", "/wp-admin",
    "/cart", "/checkout", "?s=", "/tag/", "/category/feed",
    "/newsletter", "/news-and-media", "/media-releases", "/budget/",
    "/performance-contracts", "/long-term-borrowing", "/annual-report",
    "/financial-statement", "/organogram", "/vacancy", "/vacancies",
    "/council", "/gallery",
]

SOFT_404_FRAGMENTS = [
    "/help?e=404", "/error", "/not-found", "404", "/page-not-found",
]

_STALE_YEAR_RE = re.compile(r'year=(20[0-9]{2})')

STRONG_ANCHOR_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "sourcing", "bids", "tenders",
]


def _is_tender_url(url: str, anchor_text: str = "") -> bool:
    url_lower = url.lower()
    anchor_lower = anchor_text.lower()
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
    match = _STALE_YEAR_RE.search(url)
    if match:
        year = int(match.group(1))
        return year < datetime.utcnow().year
    return False


def _is_soft_404(final_url: str) -> bool:
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
    visited: Set[str] = set()
    results: List[Dict] = []
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
        timeout=15, headers=headers, follow_redirects=True, verify=False
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

                final_url = str(response.url)
                if _is_soft_404(final_url):
                    logger.debug(f"[CRAWLER] Soft 404: {url} → {final_url}")
                    continue

                if response.status_code != 200:
                    logger.debug(f"[CRAWLER] {response.status_code} — {url}")
                    continue

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
# Crawl targets — mirrors CITY_PORTALS
# ---------------------------------------------------------------------------

CRAWL_TARGETS = [
    # ── Metros / large cities ──────────────────────────────────────────────
    {"name": "City of Cape Town",      "seed_url": "https://www.capetown.gov.za/work/tenders",                                                      "max_depth": 2, "max_pages": 30},
    {"name": "City of Johannesburg",   "seed_url": "https://www.joburg.org.za/work_/Pages/Tenders/Tenders.aspx",                                   "max_depth": 2, "max_pages": 30},
    {"name": "City of Tshwane",        "seed_url": "https://www.tshwane.gov.za/Sites/Departments/Financial-Services/Pages/Tenders.aspx",           "max_depth": 2, "max_pages": 30},
    {"name": "City of Ekurhuleni",     "seed_url": "https://www.ekurhuleni.gov.za/tenders",                                                        "max_depth": 3, "max_pages": 50},
    {"name": "eThekwini Municipality", "seed_url": "https://www.durban.gov.za/City_Services/finance/SCM/Pages/Quotations-Tenders.aspx",            "max_depth": 2, "max_pages": 30},
    {"name": "Buffalo City Metro",     "seed_url": "https://www.buffalocity.gov.za/tenders",                                                       "max_depth": 3, "max_pages": 40},
    {"name": "Mangaung Municipality",  "seed_url": "https://www.mangaung.co.za/tenders",                                                           "max_depth": 2, "max_pages": 30},
    {"name": "Nelson Mandela Bay",     "seed_url": "https://www.nelsonmandelabay.gov.za/tenders",                                                  "max_depth": 3, "max_pages": 40},

    # ── Northern Cape — provincial ──────────────────────────────────────────
    {"name": "Northern Cape Provincial Government", "seed_url": "https://www.ncgov.co.za/tenders",                                                 "max_depth": 3, "max_pages": 40},
    {"name": "Northern Cape DEDAT",    "seed_url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824", "max_depth": 1, "max_pages": 20},

    # ── Northern Cape — Frances Baard ──────────────────────────────────────
    {"name": "Sol Plaatje Municipality",     "seed_url": "https://www.solplaatje.org.za/tenders",                   "max_depth": 2, "max_pages": 20},
    {"name": "Dikgatlong Municipality",      "seed_url": "https://www.dikgatlong.gov.za/tenders",                   "max_depth": 2, "max_pages": 15},
    {"name": "Magareng Municipality",        "seed_url": "https://www.magareng.gov.za/index.php/tenders",           "max_depth": 2, "max_pages": 15},
    {"name": "Phokwane Municipality",        "seed_url": "https://www.phokwane.gov.za/tenders",                     "max_depth": 2, "max_pages": 15},
    {"name": "Frances Baard District",       "seed_url": "https://www.francesbaarddc.gov.za/tenders",               "max_depth": 2, "max_pages": 20},

    # ── Northern Cape — ZF Mgcawu ───────────────────────────────────────────
    {"name": "Dawid Kruiper Municipality",   "seed_url": "https://www.dawidkruiper.gov.za/tenders",                 "max_depth": 2, "max_pages": 20},
    {"name": "Kai Garib Municipality",       "seed_url": "https://www.kaigariblm.gov.za/tenders",                  "max_depth": 2, "max_pages": 15},
    {"name": "Khara Hais Municipality",      "seed_url": "https://www.kharahais.gov.za/tenders",                   "max_depth": 2, "max_pages": 15},
    {"name": "Kheis Municipality",           "seed_url": "https://www.kheis.gov.za/tenders",                       "max_depth": 2, "max_pages": 15},
    {"name": "Tsantsabane Municipality",     "seed_url": "https://www.tsantsabane.gov.za/index.php/tenders",       "max_depth": 2, "max_pages": 15},
    {"name": "ZF Mgcawu District",           "seed_url": "https://www.zfmgcawudc.gov.za/tenders",                  "max_depth": 2, "max_pages": 20},

    # ── Northern Cape — Namakwa ─────────────────────────────────────────────
    {"name": "Richtersveld Municipality",    "seed_url": "https://www.richtersveld.gov.za/tenders",                "max_depth": 2, "max_pages": 15},
    {"name": "Nama Khoi Municipality",       "seed_url": "https://www.namakhoi.gov.za/tenders",                    "max_depth": 2, "max_pages": 15},
    {"name": "Kamiesberg Municipality",      "seed_url": "https://www.kamiesberg.gov.za/tenders",                  "max_depth": 2, "max_pages": 15},
    {"name": "Hantam Municipality",          "seed_url": "https://www.hantam.gov.za/tenders",                      "max_depth": 2, "max_pages": 15},
    {"name": "Karoo Hoogland Municipality",  "seed_url": "https://www.karoohoogland.gov.za/tenders",               "max_depth": 2, "max_pages": 15},
    {"name": "Khai-Ma Municipality",         "seed_url": "https://www.khai-ma.gov.za/tenders",                     "max_depth": 2, "max_pages": 15},
    {"name": "Namakwa District",             "seed_url": "https://www.namakwadc.gov.za/tenders",                   "max_depth": 2, "max_pages": 20},

    # ── Northern Cape — Pixley ka Seme ──────────────────────────────────────
    {"name": "Siyathemba Municipality",      "seed_url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders", "max_depth": 2, "max_pages": 20},
    {"name": "Ubuntu Municipality",          "seed_url": "https://www.ubuntu.gov.za/tenders",                      "max_depth": 2, "max_pages": 15},
    {"name": "Umsobomvu Municipality",       "seed_url": "https://www.umsobomvu.gov.za/tenders",                   "max_depth": 2, "max_pages": 15},
    {"name": "Emthanjeni Municipality",      "seed_url": "https://www.emthanjeni.gov.za/tenders",                  "max_depth": 2, "max_pages": 15},
    {"name": "Kareeberg Municipality",       "seed_url": "https://www.kareeberg.gov.za/tenders",                   "max_depth": 2, "max_pages": 15},
    {"name": "Renosterberg Municipality",    "seed_url": "https://www.renosterberg.gov.za/tenders",                "max_depth": 2, "max_pages": 15},
    {"name": "Thembelihle Municipality",     "seed_url": "https://www.thembelihle.gov.za/tenders",                 "max_depth": 2, "max_pages": 15},
    {"name": "Siyancuma Municipality",       "seed_url": "https://www.siyancuma.gov.za/tenders",                   "max_depth": 2, "max_pages": 15},
    {"name": "Pixley ka Seme District",      "seed_url": "https://www.pixleydc.gov.za/tenders",                    "max_depth": 2, "max_pages": 20},

    # ── Northern Cape — John Taolo Gaetsewe ─────────────────────────────────
    {"name": "Joe Morolong Municipality",    "seed_url": "https://www.joemorolog.gov.za/tenders",                  "max_depth": 2, "max_pages": 15},
    {"name": "Gamagara Municipality",        "seed_url": "https://www.gamagara.gov.za/tenders",                    "max_depth": 2, "max_pages": 15},
    {"name": "Ga-Segonyana Municipality",    "seed_url": "https://www.gasegonyana.gov.za/tenders",                 "max_depth": 2, "max_pages": 15},
    {"name": "John Taolo Gaetsewe District", "seed_url": "https://www.johntaologaetsewedc.gov.za/tenders",        "max_depth": 2, "max_pages": 20},

    # ── Aggregators ──────────────────────────────────────────────────────────
    {"name": "sa-tenders.co.za",                     "seed_url": "https://sa-tenders.co.za/tenders",                                              "max_depth": 2, "max_pages": 40},
    {"name": "Municipalities.co.za (Northern Cape)", "seed_url": "https://municipalities.co.za/tenders/index/7/northern-cape",                    "max_depth": 2, "max_pages": 30},
    {"name": "eTenders Portal",                      "seed_url": "https://www.etenders.gov.za",                                                   "max_depth": 2, "max_pages": 40},
    {"name": "EasyTenders (Northern Cape)",          "seed_url": "https://easytenders.co.za/tenders-in/northern-cape",                           "max_depth": 2, "max_pages": 30},
    {"name": "OnlineTenders (Northern Cape)",        "seed_url": "https://www.onlinetenders.co.za/tenders/northern-cape",                        "max_depth": 2, "max_pages": 30},
    {"name": "TenderAlerts",                         "seed_url": "https://tenderalerts.co.za",                                                   "max_depth": 2, "max_pages": 30},
    {"name": "tendersbulletins.co.za (Northern Cape)", "seed_url": "https://tendersbulletins.co.za/location/northern-cape",                      "max_depth": 2, "max_pages": 30},
]


async def run_crawler() -> Dict[str, List[Dict]]:
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