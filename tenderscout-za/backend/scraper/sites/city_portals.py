import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
import logging

from scraper.utils import (
    make_content_hash, detect_industry, detect_municipality, detect_town,
    detect_province, clean_text, get_headers, is_likely_expired, is_closing_date_expired
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Portal registry
# ---------------------------------------------------------------------------
# Rule: province ALWAYS comes from config unless allow_province_detection=True.
# allow_province_detection=True is only for aggregator-style portals where a
# single page lists tenders from multiple provinces (e.g. municipalities.co.za).

CITY_PORTALS = [
    # ========================================================================
    # GAUTENG
    # ========================================================================
    {"name": "City of Johannesburg",  "url": "https://www.joburg.org.za/tenders",                                   "province": "Gauteng",       "town": "Johannesburg", "scrape_type": "links",    "allow_province_detection": False},
    {"name": "City of Tshwane",       "url": "https://www.tshwane.gov.za/?page_id=2194",                            "province": "Gauteng",       "town": "Pretoria",     "scrape_type": "links",    "allow_province_detection": False},
    {"name": "City of Ekurhuleni",    "url": "https://www.ekurhuleni.gov.za/tenders",                               "province": "Gauteng",       "town": "Ekurhuleni",   "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # WESTERN CAPE
    # ========================================================================
    {"name": "City of Cape Town",     "url": "https://web1.capetown.gov.za/web1/procurementportal/",                "province": "Western Cape",  "town": "Cape Town",    "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # KWAZULU-NATAL
    # ========================================================================
    {"name": "eThekwini Municipality","url": "https://www.durban.gov.za/tenders",                                   "province": "KwaZulu-Natal", "town": "Durban",       "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # EASTERN CAPE
    # ========================================================================
    {"name": "Buffalo City Metro",    "url": "https://www.buffalocity.gov.za/tenders",                              "province": "Eastern Cape",  "town": "East London",  "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Nelson Mandela Bay",    "url": "https://www.nelsonmandelabay.gov.za/tenders",                         "province": "Eastern Cape",  "town": "Gqeberha",     "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # FREE STATE
    # ========================================================================
    {"name": "Mangaung Municipality", "url": "https://www.mangaung.co.za/tenders",                                  "province": "Free State",    "town": "Bloemfontein", "scrape_type": "links",    "allow_province_detection": False},

    # ========================================================================
    # NORTHERN CAPE — PROVINCIAL
    # ========================================================================
    {"name": "Northern Cape Provincial Government", "url": "https://www.ncgov.co.za/tenders",                       "province": "Northern Cape", "town": "Kimberley",    "scrape_type": "standard", "allow_province_detection": False},
    {"name": "Northern Cape DEDAT",                 "url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824", "province": "Northern Cape", "town": "Kimberley", "scrape_type": "phoca", "allow_province_detection": False},

    # ========================================================================
    # NORTHERN CAPE — FRANCES BAARD DISTRICT
    # ========================================================================
    {"name": "Sol Plaatje Municipality",     "url": "https://www.solplaatje.org.za/tenders",                        "province": "Northern Cape", "town": "Kimberley",    "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Dikgatlong Municipality",      "url": "https://www.dikgatlong.gov.za/tenders",                        "province": "Northern Cape", "town": "Barkly West",  "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Magareng Municipality",        "url": "https://www.magareng.gov.za/index.php/tenders",                "province": "Northern Cape", "town": "Warrenton",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Phokwane Municipality",        "url": "https://www.phokwane.gov.za/tenders",                          "province": "Northern Cape", "town": "Hartswater",   "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Frances Baard District",       "url": "https://www.francesbaarddc.gov.za/tenders",                    "province": "Northern Cape", "town": "Kimberley",    "scrape_type": "phoca",    "allow_province_detection": False},

    # ========================================================================
    # NORTHERN CAPE — ZF MGCAWU DISTRICT
    # ========================================================================
    {"name": "Dawid Kruiper Municipality",   "url": "https://www.dawidkruiper.gov.za/tenders",                      "province": "Northern Cape", "town": "Upington",     "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kai !Garib Municipality",      "url": "https://www.kaigarib.gov.za/tenders",                          "province": "Northern Cape", "town": "Kakamas",      "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "//Khara Hais Municipality",    "url": "https://www.kharahais.gov.za/tenders",                         "province": "Northern Cape", "town": "Upington",     "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "!Kheis Municipality",          "url": "https://www.kheis.gov.za/tenders",                             "province": "Northern Cape", "town": "Groblershoop", "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Tsantsabane Municipality",     "url": "https://www.tsantsabane.gov.za/index.php/tenders",             "province": "Northern Cape", "town": "Postmasburg",  "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "ZF Mgcawu District",           "url": "https://www.zfmgcawudc.gov.za/tenders",                        "province": "Northern Cape", "town": "Upington",     "scrape_type": "phoca",    "allow_province_detection": False},

    # ========================================================================
    # NORTHERN CAPE — NAMAKWA DISTRICT
    # ========================================================================
    {"name": "Richtersveld Municipality",    "url": "https://www.richtersveld.gov.za/tenders",                      "province": "Northern Cape", "town": "Port Nolloth", "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Nama Khoi Municipality",       "url": "https://www.namakhoi.gov.za/tenders",                          "province": "Northern Cape", "town": "Springbok",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kamiesberg Municipality",      "url": "https://www.kamiesberg.gov.za/tenders",                        "province": "Northern Cape", "town": "Garies",       "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Hantam Municipality",          "url": "https://www.hantam.gov.za/tenders",                            "province": "Northern Cape", "town": "Calvinia",     "scrape_type": "hantam",   "allow_province_detection": False},
    {"name": "Karoo Hoogland Municipality",  "url": "https://www.karoohoogland.gov.za/tenders",                     "province": "Northern Cape", "town": "Sutherland",   "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Khai-Ma Municipality",         "url": "https://www.khai-ma.gov.za/tenders",                           "province": "Northern Cape", "town": "Pofadder",     "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Namakwa District",             "url": "https://www.namakwadc.gov.za/tenders",                         "province": "Northern Cape", "town": "Springbok",    "scrape_type": "phoca",    "allow_province_detection": False},

    # ========================================================================
    # NORTHERN CAPE — PIXLEY KA SEME DISTRICT
    # ========================================================================
    {"name": "Ubuntu Municipality",          "url": "https://www.ubuntu.gov.za/tenders",                            "province": "Northern Cape", "town": "Victoria West","scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Umsobomvu Municipality",       "url": "https://www.umsobomvu.gov.za/tenders",                         "province": "Northern Cape", "town": "Colesberg",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Emthanjeni Municipality",      "url": "https://www.emthanjeni.gov.za/tenders",                        "province": "Northern Cape", "town": "De Aar",       "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kareeberg Municipality",       "url": "https://www.kareeberg.gov.za/tenders",                         "province": "Northern Cape", "town": "Carnarvon",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Renosterberg Municipality",    "url": "https://www.renosterberg.gov.za/tenders",                      "province": "Northern Cape", "town": "Petrusville",  "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Thembelihle Municipality",     "url": "https://www.thembelihle.gov.za/tenders",                       "province": "Northern Cape", "town": "Hopetown",     "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Siyathemba Municipality",      "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders", "province": "Northern Cape", "town": "Prieska", "scrape_type": "phoca",  "allow_province_detection": False},
    {"name": "Siyancuma Municipality",       "url": "https://www.siyancuma.gov.za/tenders",                         "province": "Northern Cape", "town": "Douglas",      "scrape_type": "siyancuma","allow_province_detection": False},
    {"name": "Pixley ka Seme District",      "url": "https://www.pixleydc.gov.za/tenders",                          "province": "Northern Cape", "town": "De Aar",       "scrape_type": "phoca",    "allow_province_detection": False},

    # ========================================================================
    # NORTHERN CAPE — JOHN TAOLO GAETSEWE DISTRICT
    # ========================================================================
    {"name": "Joe Morolong Municipality",    "url": "https://www.joemorolog.gov.za/tenders",                        "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Gamagara Municipality",        "url": "https://www.gamagara.gov.za/tenders",                          "province": "Northern Cape", "town": "Kathu",        "scrape_type": "gamagara", "allow_province_detection": False},
    {"name": "Ga-Segonyana Municipality",    "url": "https://www.ga-segonyana.gov.za/tenders",                      "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "John Taolo Gaetsewe District", "url": "https://www.johntaologaetsewedc.gov.za/tenders",               "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "phoca",    "allow_province_detection": False},

    # ========================================================================
    # AGGREGATOR — NC-specific (multi-province detection enabled)
    # ========================================================================
    {"name": "Municipalities.co.za (Northern Cape)", "url": "https://municipalities.co.za/tenders/index/7/northern-cape", "province": "Northern Cape", "town": None, "scrape_type": "standard", "allow_province_detection": True},
]

TENDER_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "supply", "contract"]

NAV_WORDS = {
    "home", "about", "contact", "login", "forgot", "gallery", "council",
    "notice", "vacancy", "vacancies", "budget", "annual report",
    "financial statement", "organogram", "sitemap", "privacy", "terms",
}


def _get_base_url(city: Dict) -> str:
    """Extract clean base (scheme + netloc) from city URL."""
    parsed = urlparse(city["url"])
    return f"{parsed.scheme}://{parsed.netloc}"


def _build_result(
    title: str,
    href: str,
    city: Dict,
    listing_url: str,
    closing_date: str = "",
    extra_text: str = "",
) -> Optional[Dict]:
    """
    Build a normalised tender result dict.
    Returns None if the tender is expired or title is invalid.
    Province always comes from config unless allow_province_detection=True.
    """
    if not title or len(title.strip()) < 5:
        return None

    # Resolve document URL
    doc_url = None
    if href:
        if href.startswith("http") and any(
            href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".zip"]
        ):
            doc_url = href
        elif any(ext in href.lower() for ext in [".pdf", ".doc", ".docx"]):
            doc_url = href if href.startswith("http") else None

    # Province assignment
    detection_text = f"{title} {extra_text}"
    if city.get("allow_province_detection", False):
        detected = detect_province(detection_text)
        province = detected if detected else city["province"]
    else:
        province = city["province"]  # Always trust the source

    municipality = detect_municipality(detection_text, province)
    town = detect_town(detection_text, province) or city.get("town")

    # Discard expired tenders
    if closing_date and is_closing_date_expired(closing_date):
        logger.debug(f"Skipping expired tender: {title[:60]} (closes {closing_date})")
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
        "source_url": listing_url,
        "document_url": doc_url,
        "source_site": urlparse(city["url"]).netloc.replace("www.", ""),
        "reference_number": "",
        "contact_info": "",
        "content_hash": make_content_hash(title, listing_url),
    }


# ---------------------------------------------------------------------------
# Site-specific scrapers
# ---------------------------------------------------------------------------

async def scrape_gamagara(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """Gamagara Municipality — parses structured text blocks."""
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        text = soup.get_text()
        tender_pattern = r'(GM\d{4}-\d+)\s+(.*?)(?=Closing:.*?)(Closing:\s*[^G]+)'
        for match in re.finditer(tender_pattern, text, re.DOTALL | re.IGNORECASE):
            ref_num = match.group(1).strip()
            title = clean_text(match.group(2))
            closing_date_str = match.group(3).replace('Closing:', '').strip()
            pdf_links = re.findall(r'https://[^"\s]+\.pdf', text[match.start():match.end() + 500])
            doc_url = pdf_links[0] if pdf_links else None
            if not title or len(title) < 5:
                continue
            result = _build_result(title, doc_url, city, city["url"], closing_date_str, extra_text=ref_num)
            if result:
                result["reference_number"] = ref_num
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (gamagara) scrape failed: {e}")
    return results


async def scrape_siyancuma(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """Siyancuma Municipality — PDF links with inline closing dates."""
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            return results
        soup = BeautifulSoup(response.text, "lxml")
        base = _get_base_url(city)
        for link in soup.select('a[href*=".pdf"]'):
            href = link.get('href', '')
            title = clean_text(link.get_text())
            if not title or len(title) < 5:
                continue
            if not any(kw in title.lower() for kw in TENDER_KEYWORDS):
                continue
            full_url = href if href.startswith("http") else urljoin(base, href)
            parent_text = link.parent.get_text() if link.parent else ""
            date_match = re.search(r'Closing\s*Date[:\s]*([\d/]+)', parent_text, re.IGNORECASE)
            closing_date = date_match.group(1) if date_match else ""
            result = _build_result(title, full_url, city, city["url"], closing_date)
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (siyancuma) scrape failed: {e}")
    return results


async def scrape_hantam(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """Hantam Municipality — follows a 'View All' or 'tender-documents' link."""
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            return results
        soup = BeautifulSoup(response.text, "lxml")
        base = _get_base_url(city)

        # Try to find a "view all" or documents sub-page
        view_all_link = (
            soup.select_one('a[href*="tender-documents"]')
            or soup.select_one('a[href*="tenders"]')
        )
        if not view_all_link:
            return results

        href = view_all_link.get('href', '')
        doc_page_url = href if href.startswith("http") else urljoin(base, href)

        doc_response = await client.get(doc_page_url)
        if doc_response.status_code != 200:
            return results

        doc_soup = BeautifulSoup(doc_response.text, "lxml")
        for link in doc_soup.select('a[href*=".pdf"]'):
            href = link.get('href', '')
            title = clean_text(link.get_text())
            if not title or len(title) < 5:
                continue
            doc_url = href if href.startswith("http") else urljoin(base, href)
            result = _build_result(title, doc_url, city, doc_page_url)
            if result:
                results.append(result)
    except Exception as e:
        logger.exception(f"{city['name']} (hantam) scrape failed: {e}")
    return results


# ---------------------------------------------------------------------------
# Generic scrapers
# ---------------------------------------------------------------------------

async def scrape_phoca(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """Joomla/WordPress sites using Phoca Download component."""
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        # FIX: derive base from city URL, not hardcoded siyathemba
        base = _get_base_url(city)

        candidates = (
            soup.select("div.phocadownload a, span.phocadownload a")
            + soup.select("a[href*='.pdf'], a[href*='download'], a[title]")
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

            # Try to extract a closing date from surrounding text
            parent_text = link.parent.get_text() if link.parent else ""
            date_match = re.search(r'(?:Closing|Closes)[:\s]*([\d/\w\s]+?)(?:\n|$)', parent_text, re.IGNORECASE)
            closing_date = clean_text(date_match.group(1)) if date_match else ""

            result = _build_result(title, full_url, city, city["url"], closing_date)
            if result:
                results.append(result)

    except Exception as e:
        logger.exception(f"{city['name']} (phoca) scrape failed: {e}")
    return results


async def scrape_links(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """Generic link-based scraper."""
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
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
        logger.exception(f"{city['name']} (links) scrape failed: {e}")
    return results


async def scrape_standard(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """Generic scraper — includes parent element text for richer context."""
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
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
        logger.exception(f"{city['name']} (standard) scrape failed: {e}")
    return results


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def scrape_city(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    scrape_type = city.get("scrape_type", "links")
    dispatch = {
        "gamagara":  scrape_gamagara,
        "siyancuma": scrape_siyancuma,
        "hantam":    scrape_hantam,
        "phoca":     scrape_phoca,
        "standard":  scrape_standard,
        "links":     scrape_links,
    }
    handler = dispatch.get(scrape_type, scrape_links)
    return await handler(client, city)


async def scrape() -> List[Dict]:
    results = []
    async with httpx.AsyncClient(
        timeout=30, headers=get_headers(), follow_redirects=True, verify=False
    ) as client:
        for city in CITY_PORTALS:
            try:
                city_results = await scrape_city(client, city)
                results.extend(city_results)
                logger.info(f"{city['name']}: {len(city_results)} tenders")
            except Exception as e:
                logger.error(f"{city['name']}: scrape failed — {e}")
    return results