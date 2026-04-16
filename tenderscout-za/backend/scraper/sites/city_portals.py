import httpx
from bs4 import BeautifulSoup
from scraper.utils import (
    make_content_hash, detect_industry, detect_municipality, detect_town,
    detect_province, clean_text, get_headers, is_likely_expired, is_closing_date_expired
)
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Portal registry
# ---------------------------------------------------------------------------
CITY_PORTALS = [
    # GAUTENG
    {"name": "City of Johannesburg",  "url": "https://www.joburg.org.za/work_/Pages/Tenders/Tenders.aspx",                  "province": "Gauteng",        "town": "Johannesburg", "scrape_type": "links", "allow_province_detection": False},
    {"name": "City of Tshwane",       "url": "https://www.tshwane.gov.za/Sites/Departments/Financial-Services/Pages/Tenders.aspx",                  "province": "Gauteng",        "town": "Pretoria",     "scrape_type": "links", "allow_province_detection": False},
    {"name": "City of Ekurhuleni",    "url": "https://www.ekurhuleni.gov.za/tenders",                                                               "province": "Gauteng",        "town": "Ekurhuleni",   "scrape_type": "links", "allow_province_detection": False},
    # WESTERN CAPE
    {"name": "City of Cape Town",     "url": "https://www.capetown.gov.za/work/tenders",                                                            "province": "Western Cape",   "town": "Cape Town",    "scrape_type": "links", "allow_province_detection": False},
    # KWAZULU-NATAL
    {"name": "eThekwini Municipality","url": "https://www.durban.gov.za/City_Services/finance/SCM/Pages/Quotations-Tenders.aspx",                   "province": "KwaZulu-Natal",  "town": "Durban",       "scrape_type": "links", "allow_province_detection": False},
    # EASTERN CAPE
    {"name": "Buffalo City Metro",    "url": "https://www.buffalocity.gov.za/tenders",                                                              "province": "Eastern Cape",   "town": "East London",  "scrape_type": "links", "allow_province_detection": False},
    {"name": "Nelson Mandela Bay",    "url": "https://www.nelsonmandelabay.gov.za/tenders",                                                         "province": "Eastern Cape",   "town": "Gqeberha",     "scrape_type": "links", "allow_province_detection": False},
    # FREE STATE
    {"name": "Mangaung Municipality", "url": "https://www.mangaung.co.za/tenders",                                                                  "province": "Free State",     "town": "Bloemfontein", "scrape_type": "links", "allow_province_detection": False},
    # NORTHERN CAPE
    {"name": "Northern Cape Provincial Government", "url": "https://www.ncgov.co.za/tenders",                                                      "province": "Northern Cape",  "town": "Kimberley",    "scrape_type": "standard", "allow_province_detection": True},
    {"name": "Northern Cape DEDAT",                 "url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824", "province": "Northern Cape", "town": "Kimberley", "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Sol Plaatje Municipality",     "url": "https://www.solplaatje.org.za/tenders",                                                       "province": "Northern Cape",  "town": "Kimberley",    "scrape_type": "links", "allow_province_detection": False},
    {"name": "Dikgatlong Municipality",      "url": "https://www.dikgatlong.gov.za/tenders",                                                       "province": "Northern Cape",  "town": "Barkly West",  "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Magareng Municipality",        "url": "https://www.magareng.gov.za/index.php/tenders",                                               "province": "Northern Cape",  "town": "Warrenton",    "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Phokwane Municipality",        "url": "https://www.phokwane.gov.za/tenders",                                                         "province": "Northern Cape",  "town": "Hartswater",   "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Frances Baard District",       "url": "https://www.francesbaarddc.gov.za/tenders",                                                   "province": "Northern Cape",  "town": "Kimberley",    "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Dawid Kruiper Municipality",   "url": "https://www.dawidkruiper.gov.za/tenders",                                                     "province": "Northern Cape",  "town": "Upington",     "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Kai Garib Municipality",       "url": "https://www.kaigariblm.gov.za/tenders",                                                      "province": "Northern Cape",  "town": "Kakamas",      "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Khara Hais Municipality",      "url": "https://www.kharahais.gov.za/tenders",                                                       "province": "Northern Cape",  "town": "Upington",     "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Kheis Municipality",           "url": "https://www.kheis.gov.za/tenders",                                                           "province": "Northern Cape",  "town": "Groblershoop", "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Tsantsabane Municipality",     "url": "https://www.tsantsabane.gov.za/index.php/tenders",                                           "province": "Northern Cape",  "town": "Postmasburg",  "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "ZF Mgcawu District",           "url": "https://www.zfmgcawudc.gov.za/tenders",                                                      "province": "Northern Cape",  "town": "Upington",     "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Richtersveld Municipality",    "url": "https://www.richtersveld.gov.za/tenders",                                                    "province": "Northern Cape",  "town": "Port Nolloth", "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Nama Khoi Municipality",       "url": "https://www.namakhoi.gov.za/tenders",                                                        "province": "Northern Cape",  "town": "Springbok",    "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Kamiesberg Municipality",      "url": "https://www.kamiesberg.gov.za/tenders",                                                      "province": "Northern Cape",  "town": "Garies",       "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Hantam Municipality",          "url": "https://www.hantam.gov.za/tenders",                                                          "province": "Northern Cape",  "town": "Calvinia",     "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Karoo Hoogland Municipality",  "url": "https://www.karoohoogland.gov.za/tenders",                                                   "province": "Northern Cape",  "town": "Sutherland",   "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Khai-Ma Municipality",         "url": "https://www.khai-ma.gov.za/tenders",                                                         "province": "Northern Cape",  "town": "Pofadder",     "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Namakwa District",             "url": "https://www.namakwadc.gov.za/tenders",                                                       "province": "Northern Cape",  "town": "Springbok",    "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Siyathemba Municipality",          "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders",                     "province": "Northern Cape",  "town": "Prieska",      "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Siyathemba Municipality (Quotes)", "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/quotations",                  "province": "Northern Cape",  "town": "Prieska",      "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Ubuntu Municipality",              "url": "https://www.ubuntu.gov.za/tenders",                                                      "province": "Northern Cape",  "town": "Victoria West","scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Umsobomvu Municipality",           "url": "https://www.umsobomvu.gov.za/tenders",                                                   "province": "Northern Cape",  "town": "Colesberg",    "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Emthanjeni Municipality",          "url": "https://www.emthanjeni.gov.za/tenders",                                                  "province": "Northern Cape",  "town": "De Aar",       "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Kareeberg Municipality",           "url": "https://www.kareeberg.gov.za/tenders",                                                   "province": "Northern Cape",  "town": "Carnarvon",    "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Renosterberg Municipality",        "url": "https://www.renosterberg.gov.za/tenders",                                                "province": "Northern Cape",  "town": "Petrusville",  "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Thembelihle Municipality",         "url": "https://www.thembelihle.gov.za/tenders",                                                 "province": "Northern Cape",  "town": "Hopetown",     "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Siyancuma Municipality",           "url": "https://www.siyancuma.gov.za/tenders",                                                   "province": "Northern Cape",  "town": "Douglas",      "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Pixley ka Seme District",          "url": "https://www.pixleydc.gov.za/tenders",                                                    "province": "Northern Cape",  "town": "De Aar",       "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Joe Morolong Municipality",    "url": "https://www.joemorolog.gov.za/tenders",                                                      "province": "Northern Cape",  "town": "Kuruman",      "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Gamagara Municipality",        "url": "https://www.gamagara.gov.za/tenders",                                                       "province": "Northern Cape",  "town": "Kathu",        "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Ga-Segonyana Municipality",    "url": "https://www.gasegonyana.gov.za/tenders",                                                    "province": "Northern Cape",  "town": "Kuruman",      "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "John Taolo Gaetsewe District", "url": "https://www.johntaologaetsewedc.gov.za/tenders",                                            "province": "Northern Cape",  "town": "Kuruman",      "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Municipalities.co.za (Northern Cape)", "url": "https://municipalities.co.za/tenders/index/7/northern-cape",                        "province": "Northern Cape",  "town": None,           "scrape_type": "standard", "allow_province_detection": True},
]

TENDER_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "supply", "contract"]

def extract_closing_date_from_page(soup: BeautifulSoup) -> str:
    """Extract closing date from page content. Returns string or empty."""
    patterns = [
        r"closing\s*date:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"closes:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"bid\s*closing\s*date:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    ]
    text = soup.get_text()
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""

def _build_result(title: str, href: str, city: Dict, listing_url: str, closing_date: str = "", extra_text: str = "") -> Optional[Dict]:
    """
    Build a tender result dict. Returns None if expired or invalid.
    """
    doc_url = None
    if href and href.startswith("http") and any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".zip"]):
        doc_url = href
    elif href and any(ext in href.lower() for ext in [".pdf", ".doc", ".docx"]):
        doc_url = href if href.startswith("http") else None

    detection_text = f"{title} {extra_text}"

    # Determine province
    if city.get("allow_province_detection", False):
        detected = detect_province(detection_text)
        province = detected if detected else city["province"]
    else:
        province = city["province"]

    municipality = detect_municipality(detection_text, province)
    town = detect_town(detection_text, province) or city.get("town")

    # Skip if closing date is expired (only if date is provided)
    if closing_date and is_closing_date_expired(closing_date):
        logger.debug(f"Skipping expired tender: {title} (closes {closing_date})")
        return None

    return {
        "title": title,
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
        "source_site": city["url"].split("/")[2],
        "reference_number": "",
        "contact_info": "",
        "content_hash": make_content_hash(title, listing_url),
    }

async def scrape_phoca(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        closing_date = extract_closing_date_from_page(soup)

        candidates = (
            soup.select("div.phocadownload a, span.phocadownload a")
            + soup.select("a[href*='.pdf'], a[href*='download'], a[title]")
        )

        NAV_WORDS = {
            "home", "about", "contact", "login", "forgot", "gallery", "council",
            "notice", "vacancy", "vacancies", "budget", "annual report",
            "financial statement", "organogram",
        }

        seen = set()
        for link in candidates:
            href = link.get("href", "")
            title = clean_text(link.get("title") or link.get_text())
            if not title or len(title) < 5:
                continue
            if any(n in title.lower() for n in NAV_WORDS):
                continue

            base = city["url"].split("/")[2]
            full_url = href if href.startswith("http") else f"https://{base}{href}"

            if title in seen:
                continue
            seen.add(title)

            if is_likely_expired(title, full_url if full_url.startswith("http") else city["url"]):
                continue

            result = _build_result(title, full_url, city, city["url"], closing_date)
            if result:
                results.append(result)

    except Exception as e:
        logger.exception(f"{city['name']} (phoca) scrape failed: {e}")

    return results

async def scrape_links(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        closing_date = extract_closing_date_from_page(soup)
        base = city["url"].split("/")[2]

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 10:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue

            full_url = href if href.startswith("http") else f"https://{base}{href}"
            result = _build_result(text, full_url, city, city["url"], closing_date)
            if result:
                results.append(result)

    except Exception as e:
        logger.exception(f"{city['name']} scrape failed: {e}")

    return results

async def scrape_standard(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """Generic scraper for portals that don't fit phoca/links patterns."""
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        closing_date = extract_closing_date_from_page(soup)
        base = city["url"].split("/")[2]

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 8:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue

            full_url = href if href.startswith("http") else f"https://{base}{href}"
            
            # Try to find parent container for extra context
            parent = link
            extra_text = ""
            for _ in range(5):
                parent = parent.parent
                if parent and parent.name in ['div', 'article', 'li', 'tr']:
                    container_text = parent.get_text()
                    if len(container_text) > len(text) + 20:
                        extra_text = container_text
                        break
            
            detection_text = f"{text} {extra_text}"
            result = _build_result(text, full_url, city, city["url"], closing_date, extra_text=detection_text)
            if result:
                results.append(result)

    except Exception as e:
        logger.exception(f"{city['name']} (standard) scrape failed: {e}")

    return results

async def scrape_city(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    scrape_type = city.get("scrape_type", "links")
    if scrape_type == "phoca":
        return await scrape_phoca(client, city)
    if scrape_type == "standard":
        return await scrape_standard(client, city)
    return await scrape_links(client, city)

async def scrape() -> List[Dict]:
    results = []
    async with httpx.AsyncClient(
        timeout=20, headers=get_headers(), follow_redirects=True, verify=True
    ) as client:
        for city in CITY_PORTALS:
            city_results = await scrape_city(client, city)
            results.extend(city_results)
            logger.info(f"{city['name']}: {len(city_results)} tenders")
    return results