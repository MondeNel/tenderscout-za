"""
City and Municipal Tender Portal Scraper
=========================================
This module scrapes tender/bid/RFQ listings directly from South African
municipal and city government websites.

Architecture:
- CITY_PORTALS: Configuration registry for all target websites
- Site-specific scrapers: Custom handlers for websites with unique HTML structures
- Generic scrapers: Fallback handlers for common patterns (Phoca, standard links)
- Dispatcher: Routes each portal to its appropriate handler

The module is designed to be run as part of a larger scraping pipeline that
aggregates tenders from multiple sources (aggregators, bulletins, etc.)
"""

import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
import logging

# -----------------------------------------------------------------------------
# Import utility functions from the shared scraper utilities module
# -----------------------------------------------------------------------------
from scraper.utils import (
    make_content_hash,      # Creates unique hash for deduplication
    detect_industry,        # Classifies tender by industry category
    detect_municipality,    # Extracts municipality name from text
    detect_town,            # Extracts town/city name from text
    detect_province,        # Extracts province from text
    clean_text,             # Normalizes whitespace and removes junk characters
    get_headers,            # Returns browser-like HTTP headers to avoid blocking
    is_likely_expired,      # Heuristic check for expired tenders
    is_closing_date_expired, # Checks if a given date is in the past
)

logger = logging.getLogger(__name__)

# =============================================================================
# PORTAL REGISTRY
# =============================================================================
# Each entry defines a municipal website to scrape.
#
# Fields:
#   - name: Display name of the municipality
#   - url: The page URL containing tender listings
#   - province: Default province for tenders from this source
#   - town: Default town/city for tenders from this source
#   - scrape_type: Which handler function to use (see dispatcher below)
#   - allow_province_detection: If True, attempt to detect province from tender text
#                               (useful for aggregators covering multiple provinces)
# =============================================================================

CITY_PORTALS = [
    # ========================================================================
    # GAUTENG — Major metropolitan municipalities
    # ========================================================================
    {"name": "City of Johannesburg",  "url": "https://www.joburg.org.za/tenders",                                 "province": "Gauteng",       "town": "Johannesburg", "scrape_type": "links",    "allow_province_detection": False},
    {"name": "City of Tshwane",       "url": "https://www.tshwane.gov.za/?page_id=2194",                          "province": "Gauteng",       "town": "Pretoria",     "scrape_type": "links",    "allow_province_detection": False},
    {"name": "City of Ekurhuleni",    "url": "https://www.ekurhuleni.gov.za/tenders",                             "province": "Gauteng",       "town": "Ekurhuleni",   "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # WESTERN CAPE
    # ========================================================================
    {"name": "City of Cape Town",     "url": "https://web1.capetown.gov.za/web1/procurementportal/",              "province": "Western Cape",  "town": "Cape Town",    "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # KWAZULU-NATAL
    # ========================================================================
    {"name": "eThekwini Municipality","url": "https://www.durban.gov.za/tenders",                                 "province": "KwaZulu-Natal", "town": "Durban",       "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # FREE STATE
    # ========================================================================
    {"name": "Mangaung Municipality", "url": "https://www.mangaung.co.za/tenders",                                "province": "Free State",    "town": "Bloemfontein", "scrape_type": "phoca",    "allow_province_detection": False},
    # ========================================================================
    # EASTERN CAPE — Comprehensive coverage of local and district municipalities
    # ========================================================================
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
    {"name": "Port St Johns Municipality",           "url": "https://www.portst johns.gov.za/tenders",            "province": "Eastern Cape",  "town": "Port St Johns","scrape_type": "links",    "allow_province_detection": False},
    {"name": "Blue Crane Route Municipality",        "url": "https://www.bluecraneroute.gov.za/tenders",          "province": "Eastern Cape",  "town": "Somerset East","scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kouga Local Municipality",             "url": "https://www.kouga.gov.za/tenders",                   "province": "Eastern Cape",  "town": "Humansdorp",   "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Koukamma Local Municipality",          "url": "https://www.koukamma.gov.za/tenders",                "province": "Eastern Cape",  "town": "Kareedouw",    "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Makana Local Municipality",            "url": "https://www.makana.gov.za/tenders",                  "province": "Eastern Cape",  "town": "Makhanda",     "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Ndlambe Local Municipality",           "url": "https://www.ndlambe.gov.za/tenders",                 "province": "Eastern Cape",  "town": "Port Alfred",  "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Sunday's River Valley Municipality",   "url": "https://www.srvlm.gov.za/tenders",                   "province": "Eastern Cape",  "town": "Kirkwood",     "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # NORTHERN CAPE — PROVINCIAL GOVERNMENT
    # ========================================================================
    {"name": "Northern Cape Provincial Government", "url": "https://www.ncgov.co.za/tenders",                     "province": "Northern Cape", "town": "Kimberley",    "scrape_type": "standard", "allow_province_detection": False},
    {"name": "Northern Cape DEDAT",                 "url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824", "province": "Northern Cape", "town": "Kimberley", "scrape_type": "phoca", "allow_province_detection": False},
    # ========================================================================
    # NORTHERN CAPE — FRANCES BAARD DISTRICT MUNICIPALITIES
    # ========================================================================
    # Note: Sol Plaatje (Kimberley) times out — skipped until site stabilizes
    {"name": "Dikgatlong Municipality",      "url": "https://dikgatlong.gov.za/tenders-quotations/tenders",        "province": "Northern Cape", "town": "Barkly West",  "scrape_type": "dikgatlong","allow_province_detection": False},
    {"name": "Magareng Municipality",        "url": "https://www.magareng.gov.za/index.php/tenders-quotations/tenders", "province": "Northern Cape", "town": "Warrenton", "scrape_type": "dikgatlong", "allow_province_detection": False},
    {"name": "Phokwane Municipality",        "url": "https://phokwane.gov.za/category/tenders-quotations/",        "province": "Northern Cape", "town": "Hartswater",   "scrape_type": "wp_posts", "allow_province_detection": False},
    {"name": "Frances Baard District",       "url": "https://francesbaard.gov.za/tenders/",                        "province": "Northern Cape", "town": "Kimberley",    "scrape_type": "frances_baard","allow_province_detection": False},
    # ========================================================================
    # NORTHERN CAPE — ZF MGCAWU DISTRICT MUNICIPALITIES
    # ========================================================================
    {"name": "Dawid Kruiper Municipality",   "url": "https://web.dkm.gov.za/bids",                                 "province": "Northern Cape", "town": "Upington",     "scrape_type": "dawid_kruiper","allow_province_detection": False},
    {"name": "Kai !Garib Municipality",      "url": "https://www.kaigarib.gov.za/tenders",                         "province": "Northern Cape", "town": "Kakamas",      "scrape_type": "links",    "allow_province_detection": False},
    {"name": "ZF Mgcawu District",           "url": "https://www.zfmgcawudc.gov.za/tenders",                       "province": "Northern Cape", "town": "Upington",     "scrape_type": "zfm_district","allow_province_detection": False},
    # ========================================================================
    # NORTHERN CAPE — NAMAKWA DISTRICT MUNICIPALITIES
    # ========================================================================
    {"name": "Richtersveld Municipality",    "url": "https://www.richtersveld.gov.za/tenders",                     "province": "Northern Cape", "town": "Port Nolloth", "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Nama Khoi Municipality",       "url": "https://www.namakhoi.gov.za/tenders",                         "province": "Northern Cape", "town": "Springbok",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kamiesberg Municipality",      "url": "https://www.kamiesberg.gov.za/tenders",                       "province": "Northern Cape", "town": "Garies",       "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Hantam Municipality",          "url": "https://www.hantam.gov.za/tenders",                           "province": "Northern Cape", "town": "Calvinia",     "scrape_type": "hantam",   "allow_province_detection": False},
    {"name": "Karoo Hoogland Municipality",  "url": "https://www.karoohoogland.gov.za/tenders",                    "province": "Northern Cape", "town": "Sutherland",   "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Khai-Ma Municipality",         "url": "https://www.khai-ma.gov.za/tenders",                          "province": "Northern Cape", "town": "Pofadder",     "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Namakwa District",             "url": "https://www.namakwadc.gov.za/tenders",                        "province": "Northern Cape", "town": "Springbok",    "scrape_type": "namakwa_district","allow_province_detection": False},
    # ========================================================================
    # NORTHERN CAPE — PIXLEY KA SEME DISTRICT MUNICIPALITIES
    # ========================================================================
    {"name": "Ubuntu Municipality",          "url": "https://www.ubuntu.gov.za/tenders",                           "province": "Northern Cape", "town": "Victoria West","scrape_type": "links",    "allow_province_detection": False},
    {"name": "Umsobomvu Municipality",       "url": "https://www.umsobomvu.gov.za/tenders",                        "province": "Northern Cape", "town": "Colesberg",    "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Emthanjeni Municipality",      "url": "https://www.emthanjeni.gov.za/tenders",                       "province": "Northern Cape", "town": "De Aar",       "scrape_type": "phoca",    "allow_province_detection": False},
    {"name": "Kareeberg Municipality",       "url": "https://www.kareeberg.gov.za/tenders",                        "province": "Northern Cape", "town": "Carnarvon",    "scrape_type": "kareeberg","allow_province_detection": False},
    {"name": "Siyathemba Municipality",      "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders", "province": "Northern Cape", "town": "Prieska", "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Siyathemba Municipality (Quotes)", "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/quotations", "province": "Northern Cape", "town": "Prieska", "scrape_type": "phoca", "allow_province_detection": False},
    {"name": "Siyancuma Municipality",       "url": "https://siyancuma.gov.za/document-library/tenders/",          "province": "Northern Cape", "town": "Douglas",      "scrape_type": "siyancuma","allow_province_detection": False},
    {"name": "Pixley ka Seme District",      "url": "https://www.pixleydc.gov.za/tenders",                         "province": "Northern Cape", "town": "De Aar",       "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # NORTHERN CAPE — JOHN TAOLO GAETSEWE DISTRICT MUNICIPALITIES
    # ========================================================================
    {"name": "Joe Morolong Municipality",    "url": "https://www.joemorolog.gov.za/tenders",                       "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "links",    "allow_province_detection": False},
    {"name": "Gamagara Municipality",        "url": "https://www.gamagara.gov.za/opportunities/tenders/",          "province": "Northern Cape", "town": "Kathu",        "scrape_type": "gamagara", "allow_province_detection": False},
    {"name": "Ga-Segonyana Municipality",    "url": "https://ga-segonyana.gov.za/Tenders.html",                    "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "ga_segonyana","allow_province_detection": False},
    {"name": "John Taolo Gaetsewe District", "url": "https://www.johntaologaetsewedc.gov.za/tenders",              "province": "Northern Cape", "town": "Kuruman",      "scrape_type": "links",    "allow_province_detection": False},
    # ========================================================================
    # AGGREGATOR — Northern Cape specific (municipalities.co.za provincial page)
    # ========================================================================
    {"name": "Municipalities.co.za (Northern Cape)", "url": "https://municipalities.co.za/tenders/index/7/northern-cape", "province": "Northern Cape", "town": None, "scrape_type": "standard", "allow_province_detection": True},
]

# -----------------------------------------------------------------------------
# KEYWORD FILTERING
# -----------------------------------------------------------------------------
# These keywords are used to identify tender-related links from generic
# navigation links. A link must contain at least one of these in its text
# or URL to be considered a potential tender.
# -----------------------------------------------------------------------------
TENDER_KEYWORDS = [
    "tender", "bid", "rfq", "rfp", "quotation", "procurement", 
    "supply", "contract", "quote", "appointment"
]

# -----------------------------------------------------------------------------
# NAVIGATION FILTERING
# -----------------------------------------------------------------------------
# Words that indicate a link is site navigation rather than a tender listing.
# Titles containing these words are skipped to reduce false positives.
# -----------------------------------------------------------------------------
NAV_WORDS = {
    "home", "about", "contact", "login", "forgot", "gallery", "council",
    "notice", "vacancy", "vacancies", "budget", "annual report",
    "financial statement", "organogram", "sitemap", "privacy", "terms",
    "facebook", "twitter", "instagram",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_base_url(city: Dict) -> str:
    """
    Extract the base URL (scheme + domain) from a portal's full URL.
    
    Example:
        Input:  {"url": "https://www.example.gov.za/tenders/page"}
        Output: "https://www.example.gov.za"
    
    This is used to resolve relative links (e.g., "/downloads/file.pdf")
    into absolute URLs.
    
    Args:
        city: Portal configuration dictionary containing a 'url' key
        
    Returns:
        Base URL string (scheme://netloc)
    """
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
    Construct a standardized tender result dictionary from scraped data.
    
    This is the core normalization function — it takes raw scraped data
    and produces a consistent output format that the database expects.
    
    Processing steps:
        1. Validate title (minimum length, not empty)
        2. Identify document URLs (PDF, DOC, etc.)
        3. Detect or assign geographic information (province, municipality, town)
        4. Detect industry category from text
        5. Check if tender is expired (skip if so)
        6. Generate unique content hash for deduplication
    
    Args:
        title: The tender title/link text
        href: The URL the link points to (may be relative)
        city: Portal configuration dictionary
        listing_url: The page URL where this tender was found
        closing_date: Extracted closing date string (if available)
        extra_text: Additional context text (e.g., parent element content)
        
    Returns:
        Standardized tender dict, or None if the result should be filtered out
    """
    # -------------------------------------------------------------------------
    # Basic validation — skip empty or suspiciously short titles
    # -------------------------------------------------------------------------
    if not title or len(title.strip()) < 5:
        return None

    # -------------------------------------------------------------------------
    # Document URL detection
    # If the link points directly to a downloadable file (PDF, DOC, etc.),
    # capture it as the document_url. Otherwise it remains None.
    # -------------------------------------------------------------------------
    doc_url = None
    if href:
        # Case 1: Absolute URL that ends with a document extension
        if href.startswith("http") and any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".zip"]):
            doc_url = href
        # Case 2: URL contains document extension somewhere (e.g., with query params)
        elif any(ext in href.lower() for ext in [".pdf", ".doc", ".docx"]):
            doc_url = href if href.startswith("http") else None

    # -------------------------------------------------------------------------
    # Geographic detection
    # Combine title and any extra context text for better detection accuracy
    # -------------------------------------------------------------------------
    detection_text = f"{title} {extra_text}"
    
    # Determine province: either detect from text or use the portal's default
    if city.get("allow_province_detection", False):
        detected = detect_province(detection_text)
        province = detected if detected else city["province"]
    else:
        province = city["province"]

    # Determine municipality: try to detect, fall back to portal name
    municipality = detect_municipality(detection_text, province) or city["name"]
    
    # Determine town: try to detect, fall back to portal's default town
    town = detect_town(detection_text, province) or city.get("town")

    # -------------------------------------------------------------------------
    # Expiry filtering — skip tenders with closing dates in the past
    # -------------------------------------------------------------------------
    if closing_date and is_closing_date_expired(closing_date):
        return None

    # -------------------------------------------------------------------------
    # Build and return the standardized result dictionary
    # -------------------------------------------------------------------------
    return {
        "title": title.strip(),
        "description": f"Tender from {city['name']}. Visit their website to view full details.",
        "issuing_body": city["name"],
        "province": province,
        "municipality": municipality,
        "town": town,
        "industry_category": detect_industry(detection_text),
        "closing_date": closing_date,
        "posted_date": "",  # Most municipal sites don't show posted dates
        "source_url": listing_url,
        "document_url": doc_url,
        "source_site": urlparse(city["url"]).netloc.replace("www.", ""),
        "reference_number": "",  # To be filled by site-specific scrapers if available
        "contact_info": "",      # To be filled by site-specific scrapers if available
        "content_hash": make_content_hash(title, listing_url),  # For deduplication
    }


# =============================================================================
# SITE-SPECIFIC SCRAPERS
# =============================================================================
# Each function below handles a website with a unique HTML structure that
# doesn't work with the generic scrapers. They're registered by name in the
# dispatcher at the bottom of the file.
# =============================================================================

async def scrape_wp_posts(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """
    Scraper for WordPress sites that list tenders as blog posts.
    
    Pattern:
        - Tenders are published as posts/articles
        - Each post has an entry-title heading and a permalink
        - Closing dates are embedded in the post body text
    
    Used for: Phokwane Municipality
    
    Args:
        client: HTTPX async client for making requests
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        # Fetch the tender listing page
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results
            
        soup = BeautifulSoup(response.text, "lxml")
        
        # WordPress typically uses <article> elements or divs with class "post" or "entry"
        articles = soup.select("article, .post, .entry")
        
        for art in articles:
            # Extract title from heading element
            title_el = art.select_one("h1, h2, h3, h4, .entry-title")
            if not title_el:
                continue
                
            title = clean_text(title_el.get_text())
            if not title or len(title) < 8:
                continue
                
            # Get the permalink (usually the title is wrapped in an <a> tag)
            link_el = art.select_one("a[href]")
            href = link_el.get("href", "") if link_el else city["url"]
            
            # Try to find a closing date in the post body text
            body_text = art.get_text()
            date_match = re.search(r'(?:Closing|Close|Closes)[:\s]*([\d/]+)', body_text, re.IGNORECASE)
            closing_date = date_match.group(1) if date_match else ""
            
            # Build the standardized result
            result = _build_result(title, href, city, city["url"], closing_date)
            if result:
                results.append(result)
                
    except Exception as e:
        logger.exception(f"{city['name']} (wp_posts) failed: {e}")
        
    return results


async def scrape_frances_baard(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """
    Scraper for Frances Baard District Municipality.
    
    Pattern:
        - Tenders are PDF files linked from the page
        - Each link is labeled "Click to Download"
        - The actual tender title is in text adjacent to the link
        
    Strategy:
        Find all PDF links, then look at surrounding elements for descriptive text.
        If no text found, derive title from the PDF filename.
        
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            return results
            
        soup = BeautifulSoup(response.text, "lxml")
        base = _get_base_url(city)
        
        # Find all links that point to PDF files (look for wp-content or .pdf in href)
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not href or ".pdf" not in href.lower():
                continue
                
            # Try to find descriptive text in parent or grandparent elements
            parent = link.parent
            sibling_text = ""
            if parent:
                # Check up to 2 levels up for readable text
                for el in [parent, parent.parent]:
                    if el:
                        t = clean_text(el.get_text())
                        # Filter out the generic "Click to Download" text
                        if len(t) > 10 and t.lower() not in ("click to download", "download"):
                            sibling_text = t
                            break
                            
            # Fallback: derive title from the PDF filename
            if not sibling_text or sibling_text.lower() in ("click to download", "download"):
                filename = href.split("/")[-1].split("?")[0]
                sibling_text = filename.replace("-", " ").replace("_", " ").replace(".pdf", "").strip()
                
            if not sibling_text or len(sibling_text) < 5:
                continue
                
            # Build absolute URL
            full_url = href if href.startswith("http") else urljoin(base, href)
            
            # Skip if the tender appears to be expired
            if is_likely_expired(sibling_text, full_url):
                continue
                
            result = _build_result(sibling_text, full_url, city, city["url"])
            if result:
                results.append(result)
                
    except Exception as e:
        logger.exception(f"{city['name']} (frances_baard) failed: {e}")
        
    return results


async def scrape_dikgatlong(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """
    Scraper for Dikgatlong and Magareng Municipalities.
    
    Pattern:
        - Joomla sites with Phoca Download component
        - Content is loaded via AJAX/JavaScript
        - We attempt to fetch the underlying API endpoints directly
        
    Strategy:
        1. Try common Phoca Download API paths
        2. If that fails, fall back to scraping the page for tender keywords
        
    Used for: Dikgatlong Municipality, Magareng Municipality
    
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        base = _get_base_url(city)
        
        # ---------------------------------------------------------------------
        # Strategy 1: Try direct Phoca Download API endpoints
        # These often return the document list in HTML format
        # ---------------------------------------------------------------------
        api_paths = [
            "/index.php?option=com_phocadownload&view=category&id=1",
            "/index.php?option=com_phocadownload&view=category&id=2",
            "/index.php?option=com_phocadownload&view=categories",
        ]
        
        found_any = False
        for path in api_paths:
            try:
                r = await client.get(urljoin(base, path))
                if r.status_code == 200 and len(r.text) > 500:
                    soup = BeautifulSoup(r.text, "lxml")
                    # Look for links containing .pdf or phocadownload in href
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
                pass  # Silently try next path
                
        # ---------------------------------------------------------------------
        # Strategy 2: Fallback — scrape the main page for tender keywords
        # ---------------------------------------------------------------------
        if not found_any:
            r = await client.get(city["url"])
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                for link in soup.select("a[href]"):
                    href = link.get("href", "")
                    text = clean_text(link.get_text())
                    if not text or len(text) < 10:
                        continue
                    # Check if text or URL contains tender keywords
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
    """
    Scraper for Dawid Kruiper Municipality.
    
    Pattern:
        - React Single Page Application at web.dkm.gov.za/bids
        - Content is rendered client-side with JavaScript
        - httpx only gets the initial HTML shell
        
    Strategy:
        Try the main URL and also a /documents endpoint as fallback.
        Scrape any links containing tender keywords from the HTML we can get.
        
    Note: Full scraping would require Playwright/Selenium for JS rendering.
    
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    base = _get_base_url(city)
    
    # Try both the bids page and a potential documents endpoint
    urls_to_try = [city["url"], urljoin(base, "/documents")]
    
    for url in urls_to_try:
        try:
            r = await client.get(url)
            if r.status_code != 200:
                continue
                
            soup = BeautifulSoup(r.text, "lxml")
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                text = clean_text(link.get_text())
                if not text or len(text) < 8:
                    continue
                    
                # Filter by tender keywords
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
    """
    Scraper for Ga-Segonyana Municipality.
    
    Pattern:
        - Plain HTML table with columns: [Tender Advert, Closing Date]
        - PDF links are relative paths like 'downloads/Bid Document...'
        
    This is one of the more reliable scrapers — the site uses simple,
    static HTML that's easy to parse.
    
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
            
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        # Get base path for resolving relative download links
        base_path = city["url"].rsplit("/", 1)[0] + "/"

        # ---------------------------------------------------------------------
        # Primary strategy: Parse the table structure
        # ---------------------------------------------------------------------
        for row in soup.select("table tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 1:
                continue
                
            title_cell = cells[0]
            closing_cell = cells[1] if len(cells) > 1 else None

            # Find the link inside the title cell
            link_el = title_cell.select_one("a[href]")
            if not link_el:
                continue
                
            title = clean_text(link_el.get_text())
            # Skip header rows
            if not title or len(title) < 5 or title.lower() in ("tender advert", "closing date"):
                continue

            href = link_el.get("href", "")
            full_url = href if href.startswith("http") else urljoin(base_path, href)

            # Extract closing date from second column
            closing_date = clean_text(closing_cell.get_text()) if closing_cell else ""

            result = _build_result(title, full_url, city, city["url"], closing_date)
            if result:
                results.append(result)

        # ---------------------------------------------------------------------
        # Fallback: Direct PDF link scraping (in case table is empty/malformed)
        # ---------------------------------------------------------------------
        if not results:
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                if ".pdf" not in href.lower() and "download" not in href.lower():
                    continue
                    
                title = clean_text(link.get_text())
                if not title or len(title) < 5:
                    # Use filename as title
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
    """
    Scraper for Gamagara Municipality.
    
    Pattern:
        - Tenders are listed with "View" and "Download" links
        - Title text appears between/adjacent to these links
        
    Strategy:
        1. Look for links and check surrounding text
        2. Fallback: Use regex to extract text blocks between "View"/"Download"
        
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
            
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        
        # ---------------------------------------------------------------------
        # Strategy 1: Parse links with tender keywords or document extensions
        # ---------------------------------------------------------------------
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 8:
                continue
                
            # Skip the "View" and "Download" link text itself
            if "view" in text.lower() or "download" in text.lower():
                continue
                
            # Check for tender keywords or document extensions
            if not any(kw in text.lower() for kw in TENDER_KEYWORDS):
                if not any(ext in href.lower() for ext in [".pdf", "download", "view"]):
                    continue
                    
            full_url = href if href.startswith("http") else urljoin(base, href)
            result = _build_result(text, full_url, city, city["url"])
            if result:
                results.append(result)

        # ---------------------------------------------------------------------
        # Strategy 2: Regex fallback — find text blocks between View/Download
        # ---------------------------------------------------------------------
        if not results:
            page_text = soup.get_text()
            # Pattern: Capitalized text (8-80 chars) followed by "View" or "Download"
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
    """
    Scraper for ZF Mgcawu District Municipality.
    
    Pattern:
        - Simple page with PDF document links
        - Each PDF represents a tender document
        
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
            
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        
        # Find all PDF links
        for link in soup.select("a[href*='.pdf']"):
            href = link.get("href", "")
            title = clean_text(link.get_text())
            
            # Fallback to filename if no link text
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
    """
    Scraper for Namakwa District Municipality.
    
    Currently delegates to the generic links scraper, but exists as a separate
    function so it can be customized later if needed.
    
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    return await scrape_links(client, city)


async def scrape_kareeberg(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """
    Scraper for Kareeberg Municipality.
    
    Pattern:
        - Structured list with RFQ numbers
        - Uses standard link scraping with tender keyword filtering
        
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        r = await client.get(city["url"])
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
    """
    Scraper for Siyancuma Municipality.
    
    Pattern:
        - Document library page with PDF links
        - Closing dates may appear in parent element text
        
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        r = await client.get(city["url"])
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
                
            # Try to extract closing date from parent element
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
    """
    Scraper for Hantam Municipality.
    
    Pattern:
        - WordPress site with tender posts under /category/tender-adverts/
        - Also contains direct PDF links
        
    Strategy:
        1. Try the tender category page first
        2. Parse WordPress post structure
        3. Also grab any direct PDF links
        
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        base = _get_base_url(city)
        
        # Try the category page specifically for tender adverts
        cat_url = urljoin(base, "/category/tender-adverts/")
        r = await client.get(cat_url)
        if r.status_code != 200:
            # Fallback to main tenders page
            r = await client.get(city["url"])
            
        if r.status_code != 200:
            return results
            
        soup = BeautifulSoup(r.text, "lxml")
        
        # ---------------------------------------------------------------------
        # Parse WordPress posts
        # ---------------------------------------------------------------------
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
                
        # ---------------------------------------------------------------------
        # Also grab any direct PDF links on the page
        # ---------------------------------------------------------------------
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
# GENERIC SCRAPERS
# =============================================================================
# These functions handle common patterns found across multiple municipal sites.
# They're used as fallbacks or for sites that don't need custom handling.
# =============================================================================

async def scrape_phoca(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """
    Generic scraper for Joomla sites using the Phoca Download component.
    
    Pattern:
        - Links are often inside div.phocadownload or span.phocadownload
        - May have title attributes with the document name
        - Closing dates sometimes appear in parent element text
        
    This is one of the most common patterns for South African municipal sites.
    
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            logger.warning(f"{city['name']} returned {r.status_code}")
            return results
            
        soup = BeautifulSoup(r.text, "lxml")
        base = _get_base_url(city)
        
        # Combine multiple selector strategies for Phoca links
        candidates = (
            soup.select("div.phocadownload a, span.phocadownload a") +
            soup.select("a[href*='.pdf'], a[href*='download'], a[title]")
        )
        
        seen = set()  # Track seen titles to avoid duplicates
        
        for link in candidates:
            href = link.get("href", "")
            # Prefer title attribute, fall back to link text
            title = clean_text(link.get("title") or link.get_text())
            
            if not title or len(title) < 5:
                continue
                
            # Skip navigation links
            if any(n in title.lower() for n in NAV_WORDS):
                continue
                
            # Skip duplicates
            if title in seen:
                continue
            seen.add(title)
            
            full_url = href if href.startswith("http") else urljoin(base, href)
            
            if is_likely_expired(title, full_url):
                continue
                
            # Try to extract closing date from parent element
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
    """
    Generic link scraper — the simplest fallback handler.
    
    Pattern:
        - Finds all <a> tags
        - Filters by tender keywords in link text or URL
        - Builds results from whatever it finds
        
    This is the default scraper for sites without custom handlers.
    
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        r = await client.get(city["url"])
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
                
            # Must contain at least one tender keyword
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
    """
    Enhanced generic scraper — includes parent element text for context.
    
    Similar to scrape_links, but also captures the parent element's text
    to improve province/municipality/industry detection.
    
    Args:
        client: HTTPX async client
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    results = []
    try:
        r = await client.get(city["url"])
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
            
            # Include parent element text for better detection
            parent = link.parent
            extra_text = clean_text(parent.get_text()) if parent else ""
            
            result = _build_result(text, full_url, city, city["url"], extra_text=extra_text)
            if result:
                results.append(result)
                
    except Exception as e:
        logger.exception(f"{city['name']} (standard) failed: {e}")
        
    return results


# =============================================================================
# DISPATCHER
# =============================================================================
# Routes each portal to its appropriate scraper function based on scrape_type.
# =============================================================================

async def scrape_city(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """
    Dispatch function — routes a portal to the correct scraper handler.
    
    Maps the 'scrape_type' field from the portal configuration to the
    appropriate async scraper function.
    
    Args:
        client: HTTPX async client (shared across all requests)
        city: Portal configuration dictionary
        
    Returns:
        List of standardized tender dictionaries from this portal
    """
    dispatch = {
        "wp_posts":       scrape_wp_posts,
        "frances_baard":  scrape_frances_baard,
        "dikgatlong":     scrape_dikgatlong,
        "dawid_kruiper":  scrape_dawid_kruiper,
        "ga_segonyana":   scrape_ga_segonyana,
        "gamagara":       scrape_gamagara,
        "zfm_district":   scrape_zfm_district,
        "namakwa_district": scrape_namakwa_district,
        "kareeberg":      scrape_kareeberg,
        "siyancuma":      scrape_siyancuma,
        "hantam":         scrape_hantam,
        "phoca":          scrape_phoca,
        "standard":       scrape_standard,
        "links":          scrape_links,
    }
    
    # Get the appropriate handler, default to scrape_links if type not found
    handler = dispatch.get(city.get("scrape_type", "links"), scrape_links)
    
    # Execute the handler and return results
    return await handler(client, city)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def scrape() -> List[Dict]:
    """
    Main entry point — scrapes all configured city portals.
    
    Creates a shared HTTPX client, iterates through all portals in CITY_PORTALS,
    dispatches each to the appropriate scraper, and aggregates all results.
    
    Returns:
        Combined list of all tenders from all municipal portals
    """
    results = []
    
    # Create a single shared HTTP client for all requests
    # - timeout=30: Don't hang forever on slow sites
    # - headers=get_headers(): Browser-like headers to avoid blocking
    # - follow_redirects=True: Handle 301/302 automatically
    # - verify=False: Skip SSL verification (some gov sites have bad certs)
    async with httpx.AsyncClient(
        timeout=30, 
        headers=get_headers(), 
        follow_redirects=True, 
        verify=False
    ) as client:
        for city in CITY_PORTALS:
            try:
                city_results = await scrape_city(client, city)
                results.extend(city_results)
                logger.info(f"{city['name']}: {len(city_results)} tenders")
            except Exception as e:
                logger.error(f"{city['name']}: scrape failed — {e}")
                
    return results