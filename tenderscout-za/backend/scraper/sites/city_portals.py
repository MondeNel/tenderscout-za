"""
City and Municipal Tender Portal Scraper (Production‑Ready)
===========================================================
Scrapes tender/bid/RFQ listings from 60+ South African municipal
and district government websites.

v2 fixes:
- Custom SSL context to bypass broken government certificates
- Retry with exponential backoff for transient network errors
- Single fetch_with_retry utility applied to all HTTP requests
"""

import ssl
import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
import logging

from scraper.utils import (
    make_content_hash,
    detect_industry,
    detect_municipality,
    detect_town,
    detect_province,
    clean_text,
    get_headers,
    is_likely_expired,
    is_closing_date_expired,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry utility
# ---------------------------------------------------------------------------
RETRY_EXCEPTIONS = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.ReadError,
)


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> httpx.Response:
    """
    GET a URL with exponential backoff on transient network errors.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            return await client.get(url)
        except RETRY_EXCEPTIONS as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                break
            delay = base_delay * (2**attempt)
            logger.warning(
                "Retry %d/%d for %s after %.1fs: %s",
                attempt + 1,
                max_retries,
                url,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


# =============================================================================
# PORTAL REGISTRY
# =============================================================================
CITY_PORTALS = [
    # GAUTENG
    {"name": "City of Johannesburg",  "url": "https://www.joburg.org.za/tenders",                                 "province": "Gauteng",       "town": "Johannesburg", "scrape_type": "links",    "allow_province_detection": False},
    {"name": "City of Tshwane",       "url": "https://www.tshwane.gov.za/?page_id=2194",                          "province": "Gauteng",       "town": "Pretoria",     "scrape_type": "links",    "allow_province_detection": False},
    {"name": "City of Ekurhuleni",    "url": "https://www.ekurhuleni.gov.za/tenders",                             "province": "Gauteng",       "town": "Ekurhuleni",   "scrape_type": "links",    "allow_province_detection": False},
    # WESTERN CAPE
    {"name": "City of Cape Town",     "url": "https://web1.capetown.gov.za/web1/procurementportal/",              "province": "Western Cape",  "town": "Cape Town",    "scrape_type": "links",    "allow_province_detection": False},
    # KWAZULU-NATAL
    {"name": "eThekwini Municipality","url": "https://www.durban.gov.za/tenders",                                 "province": "KwaZulu-Natal", "town": "Durban",       "scrape_type": "links",    "allow_province_detection": False},
    # FREE STATE
    {"name": "Mangaung Municipality", "url": "https://www.mangaung.co.za/tenders",                                "province": "Free State",    "town": "Bloemfontein", "scrape_type": "phoca",    "allow_province_detection": False},
    # EASTERN CAPE
    {"name": "Buffalo City Metro",                   "url": "https://www.buffalocity.gov.za/tenders",             "province": "Eastern Cape",  "town": "East London",  "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Buffalo City Metro (Tenders)",         "url": "https://www.buffalocity.gov.za/tenders/formal-tenders","province": "Eastern Cape", "town": "East London",  "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Nelson Mandela Bay",                   "url": "https://www.nelsonmandelabay.gov.za/tenders",         "province": "Eastern Cape",  "town": "Gqeberha",     "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Matatiele Local Municipality",         "url": "https://www.matatiele.gov.za/tenders",               "province": "Eastern Cape",  "town": "Matatiele",    "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Ntabankulu Local Municipality",        "url": "https://www.ntabankulu.gov.za/tenders",              "province": "Eastern Cape",  "town": "Ntabankulu",   "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Umzimvubu Local Municipality",         "url": "https://www.umzimvubu.gov.za/tenders",               "province": "Eastern Cape",  "town": "Mount Frere",  "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Winnie Madikizela-Mandela Municipality","url": "https://www.wmmm.gov.za/tenders",                   "province": "Eastern Cape",  "town": "Lusikisiki",   "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Amahlathi Local Municipality",         "url": "https://www.amahlathi.gov.za/tenders",               "province": "Eastern Cape",  "town": "Stutterheim",  "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Great Kei Local Municipality",         "url": "https://www.greatkei.gov.za/tenders",                "province": "Eastern Cape",  "town": "Komani",       "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Mbhashe Local Municipality",           "url": "https://www.mbhashe.gov.za/tenders",                 "province": "Eastern Cape",  "town": "Butterworth",  "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Mnquma Local Municipality",            "url": "https://www.mnquma.gov.za/tenders",                  "province": "Eastern Cape",  "town": "Butterworth",  "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Ngqushwa Local Municipality",          "url": "https://www.ngqushwa.gov.za/tenders",                "province": "Eastern Cape",  "town": "Peddie",       "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Raymond Mhlaba Local Municipality",   "url": "https://www.raymondmhlaba.gov.za/tenders",            "province": "Eastern Cape",  "town": "Fort Beaufort","scrape_type": "links",    "allow_province_detection": False},
    {"name": "Dr AB Xuma Local Municipality",        "url": "https://www.drabxuma.gov.za/tenders",                "province": "Eastern Cape",  "town": "Tarkastad",    "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Emalahleni Local Municipality",        "url": "https://www.emalahleni.gov.za/tenders",              "province": "Eastern Cape",  "town": "Komani",       "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Enoch Mgijima Local Municipality",     "url": "https://www.enochmgijima.gov.za/tenders",            "province": "Eastern Cape",  "town": "Queenstown",   "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Inxuba Yethemba Municipality",         "url": "https://www.inxubayethemba.gov.za/tenders",          "province": "Eastern Cape",  "town": "Tarkastad",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Sakhisizwe Local Municipality",        "url": "https://www.sakhisizwe.gov.za/tenders",              "province": "Eastern Cape",  "town": "Elliot",       "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Elundini Local Municipality (RFQs)",   "url": "https://www.elundini.gov.za/rfqs",                   "province": "Eastern Cape",  "town": "Maclear",      "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Elundini Local Municipality (Tenders)","url": "https://www.elundini.gov.za/tenders",                "province": "Eastern Cape",  "town": "Maclear",      "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Senqu Local Municipality",             "url": "https://www.senqu.gov.za/tenders",                   "province": "Eastern Cape",  "town": "Aliwal North", "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Joe Gqabi District Municipality",      "url": "https://www.joegqabidm.gov.za/tenders",              "province": "Eastern Cape",  "town": "Aliwal North", "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Inkwanca Local Municipality",          "url": "https://www.inkwanca.gov.za/tenders",                "province": "Eastern Cape",  "town": "Komani",       "scrape_type": "links",    "allow_province_detection": False},
    {"name": "King Sabata Dalindyebo Municipality",  "url": "https://www.ksdm.gov.za/tenders",                    "province": "Eastern Cape",  "town": "Mthatha",      "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Mhlontlo Local Municipality",          "url": "https://www.mhlontlo.gov.za/tenders",                "province": "Eastern Cape",  "town": "Tsolo",        "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Nyandeni Local Municipality",          "url": "https://www.nyandeni.gov.za/tenders",                "province": "Eastern Cape",  "town": "Ngcobo",       "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Port St Johns Municipality",           "url": "https://www.portstjohns.gov.za/tenders",             "province": "Eastern Cape",  "town": "Port St Johns","scrape_type": "links",    "allow_province_detection": False},
    {"name": "Blue Crane Route Municipality",        "url": "https://www.bluecraneroute.gov.za/tenders",          "province": "Eastern Cape",  "town": "Somerset East","scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kouga Local Municipality",             "url": "https://www.kouga.gov.za/tenders",                   "province": "Eastern Cape",  "town": "Humansdorp",   "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Koukamma Local Municipality",          "url": "https://www.koukamma.gov.za/tenders",                "province": "Eastern Cape",  "town": "Kareedouw",    "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Makana Local Municipality",            "url": "https://www.makana.gov.za/tenders",                  "province": "Eastern Cape",  "town": "Makhanda",     "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Ndlambe Local Municipality",           "url": "https://www.ndlambe.gov.za/tenders",                 "province": "Eastern Cape",  "town": "Port Alfred",  "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Sunday's River Valley Municipality",   "url": "https://www.srvlm.gov.za/tenders",                   "province": "Eastern Cape",  "town": "Kirkwood",     "scrape_type": "links",    "allow_province_detection": False},
    # NORTHERN CAPE
    {"name": "Northern Cape Provincial Government", "url": "https://www.ncgov.co.za/tenders",                     "province": "Northern Cape", "town": "Kimberley",    "scrape_type": "standard", "allow_province_detection": False},
    {"name": "Northern Cape DEDAT",                 "url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824", "province": "Northern Cape", "town": "Kimberley", "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Dikgatlong Municipality",      "url": "https://dikgatlong.gov.za/tenders-quotations/tenders",        "province": "Northern Cape", "town": "Barkly West",  "scrape_type": "dikgatlong","allow_province_detection": False},
    {"name": "Magareng Municipality",        "url": "https://www.magareng.gov.za/index.php/tenders-quotations/tenders", "province": "Northern Cape", "town": "Warrenton", "scrape_type": "dikgatlong", "allow_province_detection": False},
    {"name": "Phokwane Municipality",        "url": "https://phokwane.gov.za/category/tenders-quotations/",        "province": "Northern Cape", "town": "Hartswater",   "scrape_type": "wp_posts", "allow_province_detection": False},
    {"name": "Frances Baard District",       "url": "https://francesbaard.gov.za/tenders/",                        "province": "Northern Cape", "town": "Kimberley",    "scrape_type": "frances_baard","allow_province_detection": False},
    {"name": "Dawid Kruiper Municipality",   "url": "https://web.dkm.gov.za/bids",                                 "province": "Northern Cape", "town": "Upington",     "scrape_type": "dawid_kruiper","allow_province_detection": False},
    {"name": "Kai !Garib Municipality",      "url": "https://www.kaigarib.gov.za/tenders",                         "province": "Northern Cape", "town": "Kakamas",      "scrape_type": "links",    "allow_province_detection": False},
    {"name": "ZF Mgcawu District",           "url": "https://www.zfmgcawudc.gov.za/tenders",                       "province": "Northern Cape", "town": "Upington",     "scrape_type": "zfm_district","allow_province_detection": False},
    {"name": "Richtersveld Municipality",    "url": "https://www.richtersveld.gov.za/tenders",                     "province": "Northern Cape", "town": "Port Nolloth", "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Nama Khoi Municipality",       "url": "https://www.namakhoi.gov.za/tenders",                         "province": "Northern Cape", "town": "Springbok",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kamiesberg Municipality",      "url": "https://www.kamiesberg.gov.za/tenders",                       "province": "Northern Cape", "town": "Garies",       "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Hantam Municipality",          "url": "https://www.hantam.gov.za/tenders",                           "province": "Northern Cape", "town": "Calvinia",     "scrape_type": "hantam",   "allow_province_detection": False},
    {"name": "Karoo Hoogland Municipality",  "url": "https://www.karoohoogland.gov.za/tenders",                    "province": "Northern Cape", "town": "Sutherland",   "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Khai-Ma Municipality",         "url": "https://www.khai-ma.gov.za/tenders",                          "province": "Northern Cape", "town": "Pofadder",     "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Namakwa District",             "url": "https://www.namakwadc.gov.za/tenders",                        "province": "Northern Cape", "town": "Springbok",    "scrape_type": "namakwa_district","allow_province_detection": False},
    {"name": "Ubuntu Municipality",          "url": "https://www.ubuntu.gov.za/tenders",                           "province": "Northern Cape", "town": "Victoria West","scrape_type": "links",    "allow_province_detection": False},
    {"name": "Umsobomvu Municipality",       "url": "https://www.umsobomvu.gov.za/tenders",                        "province": "Northern Cape", "town": "Colesberg",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Emthanjeni Municipality",      "url": "https://www.emthanjeni.gov.za/tenders",                       "province": "Northern Cape", "town": "De Aar",       "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kareeberg Municipality",       "url": "https://www.kareeberg.gov.za/tenders",                        "province": "Northern Cape", "town": "Carnarvon",    "scrape_type": "kareeberg","allow_province_detection": False},
    {"name": "Siyathemba Municipality",      "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders", "province": "Northern Cape", "town": "Prieska", "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Siyathemba Municipality (Quotes)", "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/quotations", "province": "Northern Cape", "town": "Prieska", "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Siyancuma Municipality",       "url": "https://siyancuma.gov.za/document-library/tenders/",          "province": "Northern Cape", "town": "Douglas",      "scrape_type": "siyancuma","allow_province_detection": False},
    {"name": "Pixley ka Seme District",      "url": "https://www.pixleydc.gov.za/tenders",                         "province": "Northern Cape", "town": "De Aar",       "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Joe Morolong Municipality",    "url": "https://www.joemorolog.gov.za/tenders",                       "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Gamagara Municipality",        "url": "https://www.gamagara.gov.za/opportunities/tenders/",          "province": "Northern Cape", "town": "Kathu",        "scrape_type": "gamagara", "allow_province_detection": False},
    {"name": "Ga-Segonyana Municipality",    "url": "https://ga-segonyana.gov.za/Tenders.html",                    "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "ga_segonyana","allow_province_detection": False},
    {"name": "John Taolo Gaetsewe District", "url": "https://www.johntaologaetsewedc.gov.za/tenders",              "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Municipalities.co.za (Northern Cape)", "url": "https://municipalities.co.za/tenders/index/7/northern-cape", "province": "Northern Cape", "town": None, "scrape_type": "standard", "allow_province_detection": True},
]

TENDER_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement",
    "supply", "contract", "quote", "appointment"
]

NAV_WORDS = {
    "home", "about", "contact", "login", "forgot", "gallery", "council",
    "notice", "vacancy", "vacancies", "budget", "annual report",
    "financial statement", "organogram", "sitemap", "privacy", "terms",
    "facebook", "twitter", "instagram",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _get_base_url(city: Dict) -> str:
    parsed = urlparse(city["url"])
    return f"{parsed.scheme}://{parsed.netloc}"


def _build_result(
    title: str, href: str, city: Dict, listing_url: str,
    closing_date: str = "", extra_text: str = "",
) -> Optional[Dict]:
    if not title or len(title.strip()) < 5:
        return None

    doc_url = None
    if href:
        if href.startswith("http") and any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".zip"]):
            doc_url = href
        elif any(ext in href.lower() for ext in [".pdf", ".doc", ".docx"]):
            doc_url = href if href.startswith("http") else None

    if doc_url:
        source_url = doc_url
    elif href and href.startswith("http") and href != listing_url and not href.endswith((".pdf", ".doc", ".docx", ".zip")):
        source_url = href
    else:
        source_url = listing_url

    detection_text = f"{title} {extra_text}"
    if city.get("allow_province_detection", False):
        detected = detect_province(detection_text)
        province = detected if detected else city["province"]
    else:
        province = city["province"]

    municipality = detect_municipality(detection_text, province) or city["name"]
    town = detect_town(detection_text, province) or city.get("town")

    if closing_date and is_closing_date_expired(closing_date):
        return None

    return {
        "title": title.strip(),
        "description": f"Tender from {city['name']}. Visit their website to view full details.",
        "issuing_body": city["name"],
        "province": province,
        "municipality": municipality,
        "town": town,
        "industry_category": detect_industry(detection_text),
        "closing_date": closing_date,
        "posted_date": "",
        "source_url": source_url,
        "document_url": doc_url,
        "source_site": urlparse(city["url"]).netloc.replace("www.", ""),
        "reference_number": "",
        "contact_info": "",
        "content_hash": make_content_hash(title, source_url, closing_date or ""),
    }


# =============================================================================
# Site‑specific scrapers (each now uses fetch_with_retry)
# =============================================================================
async def scrape_wp_posts(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        response = await fetch_with_retry(client, city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results
        soup = BeautifulSoup(response.text, "lxml")
        articles = soup.select("article, .post, .entry")
        for art in articles:
            title_el = art.select_one("h1, h2, h3, h4, .entry-title")
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 8:
                continue
            link_el = art.select_one("a[href]")
            href = link_el.get("href", "") if link_el else city["url"]
            body_text = art.get_text()
            date_match = re.search(r'(?:Closing|Close|Closes)[:\s]*([\d/]+)', body_text, re.IGNORECASE)
            closing_date = date_match.group(1) if date_match else ""
            result = _build_result(title, href, city, city["url"], closing_date)
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (wp_posts) failed: {e}")
    return results


async def scrape_frances_baard(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        response = await fetch_with_retry(client, city["url"])
        if response.status_code != 200:
            return results
        soup = BeautifulSoup(response.text, "lxml")
        base = _get_base_url(city)
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not href or ".pdf" not in href.lower():
                continue
            parent = link.parent
            sibling_text = ""
            if parent:
                for el in [parent, parent.parent]:
                    if el:
                        t = clean_text(el.get_text())
                        if len(t) > 10 and t.lower() not in ("click to download", "download"):
                            sibling_text = t
                            break
            if not sibling_text or sibling_text.lower() in ("click to download", "download"):
                filename = href.split("/")[-1].split("?")[0]
                sibling_text = filename.replace("-", " ").replace("_", " ").replace(".pdf", "").strip()
            if not sibling_text or len(sibling_text) < 5:
                continue
            full_url = href if href.startswith("http") else urljoin(base, href)
            if is_likely_expired(sibling_text, full_url):
                continue
            result = _build_result(sibling_text, full_url, city, city["url"])
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (frances_baard) failed: {e}")
    return results


async def scrape_dikgatlong(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        base = _get_base_url(city)
        api_paths = [
            "/index.php?option=com_phocadownload&view=category&id=1",
            "/index.php?option=com_phocadownload&view=category&id=2",
            "/index.php?option=com_phocadownload&view=categories",
        ]
        found_any = False
        for path in api_paths:
            try:
                r = await fetch_with_retry(client, urljoin(base, path))
                if r.status_code == 200 and len(r.text) > 500:
                    soup = BeautifulSoup(r.text, "lxml")
                    for link in soup.select("a[href*='.pdf'], a[href*='phocadownload']"):
                        href = link.get("href", "")
                        title = clean_text(link.get("title") or link.get_text())
                        if not title or len(title) < 5:
                            continue
                        full_url = href if href.startswith("http") else urljoin(base, href)
                        result = _build_result(title, full_url, city, city["url"])
                        if result:
                            results.append(result)
                            found_any = True
            except Exception:
                pass
        if not found_any:
            r = await fetch_with_retry(client, city["url"])
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                for link in soup.select("a[href]"):
                    href = link.get("href", "")
                    text = clean_text(link.get_text())
                    if not text or len(text) < 10:
                        continue
                    if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                        continue
                    full_url = href if href.startswith("http") else urljoin(base, href)
                    result = _build_result(text, full_url, city, city["url"])
                    if result:
                        results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (dikgatlong) failed: {e}")
    return results


async def scrape_dawid_kruiper(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    base = _get_base_url(city)
    urls_to_try = [city["url"], urljoin(base, "/documents")]
    for url in urls_to_try:
        try:
            r = await fetch_with_retry(client, url)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                text = clean_text(link.get_text())
                if not text or len(text) < 8:
                    continue
                if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                    continue
                full_url = href if href.startswith("http") else urljoin(base, href)
                result = _build_result(text, full_url, city, city["url"])
                if result:
                    results.append(result)
        except Exception as e:
            logger.warning(f"{city['name']} dawid_kruiper url {url} failed: {e}")
    return results


async def scrape_ga_segonyana(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base_path = city["url"].rsplit("/", 1)[0] + "/"
        for row in soup.select("table tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 1:
                continue
            title_cell = cells[0]
            closing_cell = cells[1] if len(cells) > 1 else None
            link_el = title_cell.select_one("a[href]")
            if not link_el:
                continue
            title = clean_text(link_el.get_text())
            if not title or len(title) < 5 or title.lower() in ("tender advert", "closing date"):
                continue
            href = link_el.get("href", "")
            full_url = href if href.startswith("http") else urljoin(base_path, href)
            closing_date = clean_text(closing_cell.get_text()) if closing_cell else ""
            result = _build_result(title, full_url, city, city["url"], closing_date)
            if result:
                results.append(result)
        if not results:
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                if ".pdf" not in href.lower() and "download" not in href.lower():
                    continue
                title = clean_text(link.get_text())
                if not title or len(title) < 5:
                    title = href.split("/")[-1].replace("-", " ").replace("_", " ")
                    title = re.sub(r'\.pdf$', '', title, flags=re.IGNORECASE).strip()
                full_url = href if href.startswith("http") else urljoin(base_path, href)
                if is_likely_expired(title, full_url):
                    continue
                result = _build_result(title, full_url, city, city["url"])
                if result:
                    results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (ga_segonyana) failed: {e}")
    return results


async def scrape_gamagara(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 8:
                continue
            if "view" in text.lower() or "download" in text.lower():
                continue
            if not any(kw in text.lower() for kw in TENDER_KEYWORDS):
                if not any(ext in href.lower() for ext in [".pdf", "download", "view"]):
                    continue
            full_url = href if href.startswith("http") else urljoin(base, href)
            result = _build_result(text, full_url, city, city["url"])
            if result:
                results.append(result)
        if not results:
            page_text = soup.get_text()
            tender_pattern = re.compile(
                r'([A-Z][A-Z0-9\s\-/]{8,80})\s+(?:View|Download)',
                re.MULTILINE,
            )
            for match in tender_pattern.finditer(page_text):
                title = clean_text(match.group(1))
                if title and len(title) >= 8:
                    result = _build_result(title, city["url"], city, city["url"])
                    if result:
                        results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (gamagara) failed: {e}")
    return results


async def scrape_zfm_district(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        for link in soup.select("a[href*='.pdf']"):
            href = link.get("href", "")
            title = clean_text(link.get_text())
            if not title or len(title) < 5:
                title = href.split("/")[-1].replace("-", " ").replace("_", " ").replace(".pdf", "").strip()
            full_url = href if href.startswith("http") else urljoin(base, href)
            if is_likely_expired(title, full_url):
                continue
            result = _build_result(title, full_url, city, city["url"])
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (zfm_district) failed: {e}")
    return results


async def scrape_namakwa_district(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    return await scrape_links(client, city)


async def scrape_kareeberg(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 8:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue
            full_url = href if href.startswith("http") else urljoin(base, href)
            result = _build_result(text, full_url, city, city["url"])
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (kareeberg) failed: {e}")
    return results


async def scrape_siyancuma(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        for link in soup.select("a[href*='.pdf']"):
            href = link.get("href", "")
            title = clean_text(link.get_text())
            if not title or len(title) < 5:
                title = href.split("/")[-1].replace("-", " ").replace("_", " ").replace(".pdf", "").strip()
            full_url = href if href.startswith("http") else urljoin(base, href)
            if is_likely_expired(title, full_url):
                continue
            parent_text = link.parent.get_text() if link.parent else ""
            date_match = re.search(r'Closing\s*Date[:\s]*([\d/]+)', parent_text, re.IGNORECASE)
            closing_date = date_match.group(1) if date_match else ""
            result = _build_result(title, full_url, city, city["url"], closing_date)
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (siyancuma) failed: {e}")
    return results


async def scrape_hantam(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        base = _get_base_url(city)
        cat_url = urljoin(base, "/category/tender-adverts/")
        r = await fetch_with_retry(client, cat_url)
        if r.status_code != 200:
            r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        for art in soup.select("article, .post"):
            title_el = art.select_one("h1, h2, h3, .entry-title")
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 8:
                continue
            link_el = art.select_one("a[href]")
            href = link_el.get("href", city["url"]) if link_el else city["url"]
            result = _build_result(title, href, city, city["url"])
            if result:
                results.append(result)
        for link in soup.select("a[href*='.pdf']"):
            href = link.get("href", "")
            title = clean_text(link.get_text())
            if not title or len(title) < 5:
                continue
            full_url = href if href.startswith("http") else urljoin(base, href)
            result = _build_result(title, full_url, city, cat_url)
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (hantam) failed: {e}")
    return results


# =============================================================================
# Generic scrapers
# =============================================================================
async def scrape_phoca(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            logger.warning(f"{city['name']} returned {r.status_code}")
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        candidates = (
            soup.select("div.phocadownload a, span.phocadownload a") +
            soup.select("a[href*='.pdf'], a[href*='download'], a[title]")
        )
        seen = set()
        for link in candidates:
            href = link.get("href", "")
            title = clean_text(link.get("title") or link.get_text())
            if not title or len(title) < 5:
                continue
            if any(n in title.lower() for n in NAV_WORDS):
                continue
            if title in seen:
                continue
            seen.add(title)
            full_url = href if href.startswith("http") else urljoin(base, href)
            if is_likely_expired(title, full_url):
                continue
            parent_text = link.parent.get_text() if link.parent else ""
            date_match = re.search(r'(?:Closing|Closes)[:\s]*([\d/\w\s]+?)(?:\n|$)', parent_text, re.IGNORECASE)
            closing_date = clean_text(date_match.group(1)) if date_match else ""
            result = _build_result(title, full_url, city, city["url"], closing_date)
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (phoca) failed: {e}")
    return results


async def scrape_links(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            logger.warning(f"{city['name']} returned {r.status_code}")
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 10:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue
            full_url = href if href.startswith("http") else urljoin(base, href)
            result = _build_result(text, full_url, city, city["url"])
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (links) failed: {e}")
    return results


async def scrape_standard(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        r = await fetch_with_retry(client, city["url"])
        if r.status_code != 200:
            logger.warning(f"{city['name']} returned {r.status_code}")
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 8:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue
            full_url = href if href.startswith("http") else urljoin(base, href)
            parent = link.parent
            extra_text = clean_text(parent.get_text()) if parent else ""
            result = _build_result(text, full_url, city, city["url"], extra_text=extra_text)
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (standard) failed: {e}")
    return results


# =============================================================================
# Dispatcher
# =============================================================================
DISPATCH = {
    "wp_posts": scrape_wp_posts,
    "frances_baard": scrape_frances_baard,
    "dikgatlong": scrape_dikgatlong,
    "dawid_kruiper": scrape_dawid_kruiper,
    "ga_segonyana": scrape_ga_segonyana,
    "gamagara": scrape_gamagara,
    "zfm_district": scrape_zfm_district,
    "namakwa_district": scrape_namakwa_district,
    "kareeberg": scrape_kareeberg,
    "siyancuma": scrape_siyancuma,
    "hantam": scrape_hantam,
    "phoca": scrape_phoca,
    "standard": scrape_standard,
    "links": scrape_links,
}


async def scrape_city(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    handler = DISPATCH.get(city.get("scrape_type", "links"), scrape_links)
    return await handler(client, city)


# =============================================================================
# Main entry point – creates a robust AsyncClient with SSL context & retries
# =============================================================================
async def scrape() -> List[Dict]:
    results = []

    # Custom SSL context to bypass broken government certificates
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    async with httpx.AsyncClient(
        timeout=30,
        headers=get_headers(),
        follow_redirects=True,
        verify=ctx,
        trust_env=False,
        http2=False,
    ) as client:
        for city in CITY_PORTALS:
            try:
                city_results = await scrape_city(client, city)
                results.extend(city_results)
                logger.debug(f"{city['name']}: {len(city_results)} tenders")
            except Exception as e:
                logger.error(f"{city['name']}: scrape failed — {e}")

    return results