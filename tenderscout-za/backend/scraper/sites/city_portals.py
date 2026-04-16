import httpx
from bs4 import BeautifulSoup
from scraper.utils import (
    make_content_hash, detect_industry, detect_municipality,
    detect_town, clean_text, get_headers, is_likely_expired
)
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Portal registry
# ---------------------------------------------------------------------------
# Rule: province is ALWAYS taken from the config — never from text detection.
# Text detection is unreliable (e.g. "Northern Cape" matching "Cape Town").
# Each portal entry owns its province; detect_* helpers are only used for
# municipality / town within that province.
# ---------------------------------------------------------------------------

CITY_PORTALS = [
    # ── GAUTENG ─────────────────────────────────────────────────────────────
    {"name": "City of Johannesburg",  "url": "https://www.joburg.org.za/work_/Pages/Tenders/Tenders.aspx",                                               "province": "Gauteng",        "town": "Johannesburg", "scrape_type": "links"},
    {"name": "City of Tshwane",       "url": "https://www.tshwane.gov.za/Sites/Departments/Financial-Services/Pages/Tenders.aspx",                       "province": "Gauteng",        "town": "Pretoria",     "scrape_type": "links"},
    {"name": "City of Ekurhuleni",    "url": "https://www.ekurhuleni.gov.za/tenders",                                                                     "province": "Gauteng",        "town": "Ekurhuleni",   "scrape_type": "links"},

    # ── WESTERN CAPE ─────────────────────────────────────────────────────────
    {"name": "City of Cape Town",     "url": "https://www.capetown.gov.za/work/tenders",                                                                  "province": "Western Cape",   "town": "Cape Town",    "scrape_type": "links"},

    # ── KWAZULU-NATAL ────────────────────────────────────────────────────────
    {"name": "eThekwini Municipality","url": "https://www.durban.gov.za/City_Services/finance/SCM/Pages/Quotations-Tenders.aspx",                         "province": "KwaZulu-Natal",  "town": "Durban",       "scrape_type": "links"},

    # ── EASTERN CAPE ─────────────────────────────────────────────────────────
    {"name": "Buffalo City Metro",    "url": "https://www.buffalocity.gov.za/tenders",                                                                    "province": "Eastern Cape",   "town": "East London",  "scrape_type": "links"},
    {"name": "Nelson Mandela Bay",    "url": "https://www.nelsonmandelabay.gov.za/tenders",                                                               "province": "Eastern Cape",   "town": "Gqeberha",     "scrape_type": "links"},

    # ── FREE STATE ───────────────────────────────────────────────────────────
    {"name": "Mangaung Municipality", "url": "https://www.mangaung.co.za/tenders",                                                                        "province": "Free State",     "town": "Bloemfontein", "scrape_type": "links"},

    # ========================================================================
    # NORTHERN CAPE — full coverage
    # ========================================================================

    # -- Provincial portal ---------------------------------------------------
    {"name": "Northern Cape Provincial Government", "url": "https://www.ncgov.co.za/tenders",                                                            "province": "Northern Cape",  "town": "Kimberley",    "scrape_type": "standard"},
    {"name": "Northern Cape DEDAT",                 "url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824", "province": "Northern Cape", "town": "Kimberley", "scrape_type": "phoca"},

    # -- Frances Baard District (Kimberley region) ---------------------------
    {"name": "Sol Plaatje Municipality",     "url": "https://www.solplaatje.org.za/tenders",                                                             "province": "Northern Cape",  "town": "Kimberley",    "scrape_type": "links"},
    {"name": "Dikgatlong Municipality",      "url": "https://www.dikgatlong.gov.za/tenders",                                                             "province": "Northern Cape",  "town": "Barkly West",  "scrape_type": "phoca"},
    {"name": "Magareng Municipality",        "url": "https://www.magareng.gov.za/index.php/tenders",                                                     "province": "Northern Cape",  "town": "Warrenton",    "scrape_type": "phoca"},
    {"name": "Phokwane Municipality",        "url": "https://www.phokwane.gov.za/tenders",                                                               "province": "Northern Cape",  "town": "Hartswater",   "scrape_type": "phoca"},
    {"name": "Frances Baard District",       "url": "https://www.francesbaarddc.gov.za/tenders",                                                         "province": "Northern Cape",  "town": "Kimberley",    "scrape_type": "phoca"},

    # -- ZF Mgcawu District (Upington region) --------------------------------
    {"name": "Dawid Kruiper Municipality",   "url": "https://www.dawidkruiper.gov.za/tenders",                                                           "province": "Northern Cape",  "town": "Upington",     "scrape_type": "phoca"},
    {"name": "Kai Garib Municipality",       "url": "https://www.kaigariblm.gov.za/tenders",                                                            "province": "Northern Cape",  "town": "Kakamas",      "scrape_type": "phoca"},
    {"name": "Khara Hais Municipality",      "url": "https://www.kharahais.gov.za/tenders",                                                             "province": "Northern Cape",  "town": "Upington",     "scrape_type": "phoca"},
    {"name": "Kheis Municipality",           "url": "https://www.kheis.gov.za/tenders",                                                                 "province": "Northern Cape",  "town": "Groblershoop", "scrape_type": "phoca"},
    {"name": "Tsantsabane Municipality",     "url": "https://www.tsantsabane.gov.za/index.php/tenders",                                                 "province": "Northern Cape",  "town": "Postmasburg",  "scrape_type": "phoca"},
    {"name": "ZF Mgcawu District",           "url": "https://www.zfmgcawudc.gov.za/tenders",                                                            "province": "Northern Cape",  "town": "Upington",     "scrape_type": "phoca"},

    # -- Namakwa District (Springbok region) ---------------------------------
    {"name": "Richtersveld Municipality",    "url": "https://www.richtersveld.gov.za/tenders",                                                          "province": "Northern Cape",  "town": "Port Nolloth", "scrape_type": "phoca"},
    {"name": "Nama Khoi Municipality",       "url": "https://www.namakhoi.gov.za/tenders",                                                              "province": "Northern Cape",  "town": "Springbok",    "scrape_type": "phoca"},
    {"name": "Kamiesberg Municipality",      "url": "https://www.kamiesberg.gov.za/tenders",                                                            "province": "Northern Cape",  "town": "Garies",       "scrape_type": "phoca"},
    {"name": "Hantam Municipality",          "url": "https://www.hantam.gov.za/tenders",                                                                "province": "Northern Cape",  "town": "Calvinia",     "scrape_type": "phoca"},
    {"name": "Karoo Hoogland Municipality",  "url": "https://www.karoohoogland.gov.za/tenders",                                                         "province": "Northern Cape",  "town": "Sutherland",   "scrape_type": "phoca"},
    {"name": "Khai-Ma Municipality",         "url": "https://www.khai-ma.gov.za/tenders",                                                               "province": "Northern Cape",  "town": "Pofadder",     "scrape_type": "phoca"},
    {"name": "Namakwa District",             "url": "https://www.namakwadc.gov.za/tenders",                                                             "province": "Northern Cape",  "town": "Springbok",    "scrape_type": "phoca"},

    # -- Pixley ka Seme District (De Aar / Prieska region) -------------------
    {"name": "Siyathemba Municipality",          "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders",                           "province": "Northern Cape",  "town": "Prieska",      "scrape_type": "phoca"},
    {"name": "Siyathemba Municipality (Quotes)", "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/quotations",                        "province": "Northern Cape",  "town": "Prieska",      "scrape_type": "phoca"},
    {"name": "Ubuntu Municipality",              "url": "https://www.ubuntu.gov.za/tenders",                                                            "province": "Northern Cape",  "town": "Victoria West","scrape_type": "phoca"},
    {"name": "Umsobomvu Municipality",           "url": "https://www.umsobomvu.gov.za/tenders",                                                         "province": "Northern Cape",  "town": "Colesberg",    "scrape_type": "phoca"},
    {"name": "Emthanjeni Municipality",          "url": "https://www.emthanjeni.gov.za/tenders",                                                        "province": "Northern Cape",  "town": "De Aar",       "scrape_type": "phoca"},
    {"name": "Kareeberg Municipality",           "url": "https://www.kareeberg.gov.za/tenders",                                                         "province": "Northern Cape",  "town": "Carnarvon",    "scrape_type": "phoca"},
    {"name": "Renosterberg Municipality",        "url": "https://www.renosterberg.gov.za/tenders",                                                      "province": "Northern Cape",  "town": "Petrusville",  "scrape_type": "phoca"},
    {"name": "Thembelihle Municipality",         "url": "https://www.thembelihle.gov.za/tenders",                                                       "province": "Northern Cape",  "town": "Hopetown",     "scrape_type": "phoca"},
    {"name": "Siyancuma Municipality",           "url": "https://www.siyancuma.gov.za/tenders",                                                         "province": "Northern Cape",  "town": "Douglas",      "scrape_type": "phoca"},
    {"name": "Pixley ka Seme District",          "url": "https://www.pixleydc.gov.za/tenders",                                                          "province": "Northern Cape",  "town": "De Aar",       "scrape_type": "phoca"},

    # -- John Taolo Gaetsewe District (Kuruman region) -----------------------
    {"name": "Joe Morolong Municipality",    "url": "https://www.joemorolog.gov.za/tenders",                                                            "province": "Northern Cape",  "town": "Kuruman",      "scrape_type": "phoca"},
    {"name": "Gamagara Municipality",        "url": "https://www.gamagara.gov.za/tenders",                                                             "province": "Northern Cape",  "town": "Kathu",        "scrape_type": "phoca"},
    {"name": "Ga-Segonyana Municipality",    "url": "https://www.gasegonyana.gov.za/tenders",                                                          "province": "Northern Cape",  "town": "Kuruman",      "scrape_type": "phoca"},
    {"name": "John Taolo Gaetsewe District", "url": "https://www.johntaologaetsewedc.gov.za/tenders",                                                  "province": "Northern Cape",  "town": "Kuruman",      "scrape_type": "phoca"},

    # -- Aggregators (NC-specific) -------------------------------------------
    {"name": "Municipalities.co.za (Northern Cape)", "url": "https://municipalities.co.za/tenders/index/7/northern-cape",                              "province": "Northern Cape",  "town": None,           "scrape_type": "standard"},
]

TENDER_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "supply", "contract"]


def _build_result(title: str, href: str, city: Dict, listing_url: str) -> Dict:
    """
    Build a tender result dict.
    IMPORTANT: province always comes from city config — never from text detection.
    municipality and town are detected within the known province only.
    """
    doc_url = None
    if href and href.startswith("http") and any(
        href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".zip"]
    ):
        doc_url = href
    elif href and any(ext in href.lower() for ext in [".pdf", ".doc", ".docx"]):
        doc_url = href if href.startswith("http") else None

    # Province is ALWAYS from config — source is ground truth
    province = city["province"]

    # Municipality and town: detect within this province, fall back to config town
    municipality = detect_municipality(title, province)
    town = detect_town(title, province) or city.get("town")

    return {
        "title": title,
        "description": f"Tender from {city['name']}. Visit their website to view full details.",
        "issuing_body": city["name"],
        "province": province,
        "municipality": municipality,
        "town": town,
        "industry_category": detect_industry(title),
        "closing_date": "",
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

            results.append(_build_result(title, full_url, city, city["url"]))

    except Exception as e:
        logger.error(f"{city['name']} (phoca) scrape failed: {e}")

    return results


async def scrape_links(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        base = city["url"].split("/")[2]

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 10:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue

            full_url = href if href.startswith("http") else f"https://{base}{href}"
            results.append(_build_result(text, full_url, city, city["url"]))

    except Exception as e:
        logger.error(f"{city['name']} scrape failed: {e}")

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
        base = city["url"].split("/")[2]

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 8:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue

            full_url = href if href.startswith("http") else f"https://{base}{href}"
            results.append(_build_result(text, full_url, city, city["url"]))

    except Exception as e:
        logger.error(f"{city['name']} (standard) scrape failed: {e}")

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
        timeout=20, headers=get_headers(), follow_redirects=True, verify=False
    ) as client:
        for city in CITY_PORTALS:
            city_results = await scrape_city(client, city)
            results.extend(city_results)
            logger.info(f"{city['name']}: {len(city_results)} tenders")
    return results