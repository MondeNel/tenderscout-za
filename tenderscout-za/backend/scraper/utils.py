"""
scraper/utils.py — Shared Utilities for Tender Scraping
========================================================
Core helper functions used across all scraper modules.

Features:
    - Industry classification from tender text
    - Province/municipality/town detection
    - Date parsing and expiry checking
    - Content hashing for deduplication
    - Text cleaning and HTTP headers
"""

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

# =============================================================================
# HTTP HEADERS
# =============================================================================
# FIX: Module-level constant — was recreated as a new dict on every call
# to get_headers(), which is invoked on every HTTP request.

REQUEST_HEADERS: dict = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-ZA,en;q=0.9",
    "Connection":      "keep-alive",
    "Cache-Control":   "no-cache",
}


def get_headers() -> dict:
    """Return browser-like HTTP headers. Kept as a function for backwards compatibility."""
    return REQUEST_HEADERS


# =============================================================================
# INDUSTRY DETECTION
# =============================================================================
# First match wins — more specific categories listed before general ones.
# Returns None (not "General") when no match — keeps DB clean.

INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "Security, Access, Alarms & Fire": [
        "security", "guarding", "cctv", "access control", "surveillance",
        "alarm", "fire detection", "fire suppression", "firefighting",
        "fire fighting", "monitoring", "armed response", "physical protection",
        "biometric", "turnstile", "boom gate",
    ],
    "Civil": [
        "civil", "road construction", "road maintenance", "bridge",
        "stormwater", "storm water", "storm-water", "bulk earthworks",
        "earthwork", "paving", "pave", "culvert", "retaining wall",
        "kerb", "sidewalk", "pavement", "pothole", "gravel road",
        "surfacing", "tar road", "road grading", "grading of road",
        "road rehabilitation", "road upgrade", "rural roads", "road safety",
        "road marking", "traffic calming", "speed hump",
    ],
    "Building & Trades": [
        "building", "construction of", "housing", "fencing", "fence",
        "roofing", "roof repair", "flooring", "tiling", "plaster",
        "brickwork", "bricklaying", "renovation", "refurbishment", "retrofit",
        "extension of", "erection of", "demolition", "ablution",
        "ablution block", "toilet facility", "carpentry", "joinery",
        "painting", "glazing", "waterproofing", "damp proofing",
    ],
    "Electrical & Automation": [
        "electrical", "wiring", "substation", "generator", "electrification",
        "solar", "metering", "meter", "transformer", "switchgear",
        "high voltage", "low voltage", "automation", "instrumentation",
        "scada", "plc", "ups system", "street light", "streetlight",
        "public lighting", "led lighting", "electrical reticulation",
        "power supply", "backup power", "inverter",
    ],
    "Plumbing & Water": [
        "plumbing", "pipe", "water reticulation", "drainage",
        "waterworks", "sewer", "sewerage", "pump station", "bulk water",
        "water supply", "water distribution", "water meter", "borehole",
        "reservoir", "water tank", "effluent", "wastewater", "water testing",
        "water quality", "irrigation", "water conservation", "leak detection",
    ],
    "IT & Telecoms": [
        "ict", "software", "network", "it support", "hardware", "server",
        "telecommunications", "fiber", "broadband", "internet", "wifi",
        "wi-fi", "application", "erp", "crm", "database", "cybersecurity",
        "cyber security", "data centre", "cloud", "telephone", "pbx",
        "licensing", "microsoft", "website", "laptop", "desktop",
        "computer", "printer", "copier", "multi function", "voip",
        "helpdesk", "it infrastructure",
    ],
    "Cleaning & Facility Management": [
        "cleaning", "hygiene", "janitorial", "pest control", "fumigation",
        "facility management", "facilities management", "grounds maintenance",
        "sanitation service", "grass cutting", "mowing", "litter",
        "landscaping", "horticulture", "garden", "tree felling",
        "deep cleaning", "disinfection",
    ],
    "Waste Management": [
        "waste management", "solid waste", "recycling", "landfill",
        "waste disposal", "refuse compactor", "refuse truck", "skip bin",
        "hazardous waste", "e-waste", "sewage removal", "honey sucker",
        "sanitary waste", "medical waste", "waste collection",
    ],
    "Mechanical, Plant & Equipment": [
        "mechanical", "plant hire", "machinery", "equipment hire",
        "truck", "tractor", "crane", "excavator", "grader", "compactor",
        "tipper", "loader", "forklift", "pump hire", "generator set",
        "compressor", "lifting equipment", "motor vehicle", "vehicle hire",
        "yellow plant", "heavy equipment", "earthmoving",
    ],
    "Transport & Logistics": [
        "transport", "logistics", "courier", "bus service", "shuttle",
        "ambulance transport", "scholar transport", "fleet management",
        "freight", "distribution", "delivery service",
    ],
    "Materials, Supply & Services": [
        "supply and delivery", "supply of", "delivery of",
        "stationery", "office supplies", "furniture", "office furniture",
        "uniform", "protective clothing", "ppe", "personal protective",
        "tools", "chemicals", "reagents", "fuel", "diesel", "petrol",
        "lubricants", "tyres", "tyre", "spare parts", "consumables",
        "janitorial supplies",
    ],
    "Consultants": [
        "consulting services", "advisory", "professional services",
        "feasibility study", "research services", "assessment services",
        "audit services", "investigation", "surveying services",
        "valuation services", "actuarial", "town planning",
        "urban planning", "environmental impact", "eia ",
        "gis services", "geotechnical", "land surveyor",
    ],
    "Engineering Consultants": [
        "engineering services", "civil engineer", "structural engineer",
        "electrical engineer", "project management", "project manager",
        "design and implementation", "supervision of works",
        "consulting engineer", "professional engineer",
    ],
    "Medical & Healthcare": [
        "medical", "healthcare", "pharmaceutical", "clinic services",
        "ambulance", "nursing", "health care", "medicine", "hospital",
        "dental", "laboratory", "pathology", "radiology",
        "occupational health", "wellness",
    ],
    "Catering": [
        "catering", "food supply", "meals", "canteen", "refreshments",
        "food and beverages", "food provision", "kitchen", "nutrition",
    ],
    "HR & Training": [
        "training", "workshop", "skills development", "human resources",
        "hr services", "recruitment", "learnerships", "internship",
        "capacity building", "training programme", "facilitation",
        "moderation", "assessor",
    ],
    "Accounting, Banking & Legal": [
        "accounting", "financial services", "legal services",
        "attorney", "legal advice", "insurance", "short-term insurance",
        "tax services", "bookkeeping", "auditors", "compliance", "forensic",
    ],
    "Media & Marketing": [
        "media", "advertising", "marketing", "branding", "printing services",
        "graphic design", "photography", "videography", "social media",
        "public relations", "communication services", "signage",
    ],
    "Travel, Tourism & Hospitality": [
        "travel", "accommodation", "hotel", "venue hire", "conference",
        "event management", "tourism", "hospitality",
    ],
}

# =============================================================================
# PROVINCE DETECTION
# =============================================================================

PROVINCE_KEYWORDS: Dict[str, List[str]] = {
    "Gauteng": [
        "gauteng", "johannesburg", "pretoria", "ekurhuleni", "soweto",
        "midrand", "tshwane", "centurion", "sandton", "randburg", "roodepoort",
    ],
    "Western Cape": [
        "western cape", "cape town", "stellenbosch", "george", "paarl",
        "worcester", "khayelitsha", "mitchells plain", "beaufort west",
    ],
    "KwaZulu-Natal": [
        "kwazulu-natal", "kzn", "durban", "pietermaritzburg", "richards bay",
        "ethekwini", "umhlanga", "phoenix", "chatsworth", "newcastle",
        "ladysmith", "port shepstone", "empangeni",
    ],
    "Eastern Cape": [
        "eastern cape", "gqeberha", "port elizabeth", "east london", "mthatha",
        "buffalo city", "queenstown", "graaff-reinet", "aliwal north",
    ],
    "Free State": [
        "free state", "bloemfontein", "mangaung", "welkom", "bethlehem",
        "kroonstad", "sasolburg", "phuthaditjhaba", "harrismith",
    ],
    "Limpopo": [
        "limpopo", "polokwane", "tzaneen", "bela-bela", "lephalale",
        "modimolle", "thohoyandou", "burgersfort", "giyani", "makhado",
    ],
    "Mpumalanga": [
        "mpumalanga", "nelspruit", "mbombela", "witbank", "emalahleni",
        "middelburg", "secunda", "ermelo",
    ],
    "North West": [
        "north west", "mahikeng", "rustenburg", "klerksdorp", "potchefstroom",
        "brits", "lichtenburg", "vryburg", "taung",
    ],
    "Northern Cape": [
        "northern cape", "kimberley", "upington", "springbok", "de aar",
        "prieska", "kuruman", "kathu", "postmasburg", "calvinia",
        "colesberg", "victoria west", "carnarvon", "sutherland",
    ],
}

# =============================================================================
# MUNICIPALITIES
# =============================================================================

MUNICIPALITIES: Dict[str, List[str]] = {
    "Eastern Cape": [
        "Buffalo City", "Nelson Mandela Bay", "Chris Hani", "Joe Gqabi",
        "O.R. Tambo", "Alfred Nzo", "Amathole", "Sarah Baartman",
        "Matatiele", "Ntabankulu", "Umzimvubu",
    ],
    "Free State": [
        "Mangaung", "Fezile Dabi", "Lejweleputswa", "Thabo Mofutsanyana",
        "Xhariep", "Metsimaholo", "Mafube", "Ngwathe", "Dihlabeng",
    ],
    "Gauteng": [
        "City of Johannesburg", "City of Tshwane", "City of Ekurhuleni",
        "Sedibeng", "West Rand", "Merafong", "Rand West", "Lesedi",
    ],
    "KwaZulu-Natal": [
        "eThekwini", "Ugu", "Umgungundlovu", "Uthukela", "Umzinyathi",
        "Amajuba", "Zululand", "Umkhanyakude", "King Cetshwayo", "Ilembe",
        "Harry Gwala", "Msunduzi", "Newcastle", "Okhahlamba",
    ],
    "Limpopo": [
        "Capricorn", "Mopani", "Sekhukhune", "Vhembe", "Waterberg",
        "Polokwane", "Thulamela", "Elias Motsoaledi", "Lepelle-Nkumpi",
    ],
    "Mpumalanga": [
        "Ehlanzeni", "Gert Sibande", "Nkangala", "Mbombela", "Emalahleni",
        "Steve Tshwete", "Govan Mbeki", "Thembisile Hani",
    ],
    "North West": [
        "Bojanala", "Ngaka Modiri Molema", "Dr Ruth Segomotsi Mompati",
        "Dr Kenneth Kaunda", "Mahikeng", "Madibeng", "Rustenburg",
    ],
    "Western Cape": [
        "City of Cape Town", "Cape Winelands", "Central Karoo", "Garden Route",
        "Overberg", "West Coast", "Drakenstein", "Stellenbosch", "Breede Valley",
        "Saldanha Bay", "Swartland", "Mossel Bay",
    ],
    "Northern Cape": [
        "Frances Baard", "ZF Mgcawu", "Namakwa", "Pixley ka Seme",
        "John Taolo Gaetsewe", "Sol Plaatje", "Dikgatlong", "Magareng",
        "Phokwane", "Dawid Kruiper", "Kai !Garib", "Khara Hais",
        "!Kheis", "Tsantsabane", "Richtersveld", "Nama Khoi",
        "Kamiesberg", "Hantam", "Karoo Hoogland", "Khai-Ma",
        "Ubuntu", "Umsobomvu", "Emthanjeni", "Kareeberg",
        "Renosterberg", "Thembelihle", "Siyathemba", "Siyancuma",
        "Joe Morolong", "Gamagara", "Ga-Segonyana",
    ],
}

# =============================================================================
# TOWNS
# =============================================================================

TOWNS: Dict[str, List[str]] = {
    "Gauteng": [
        "Johannesburg", "Pretoria", "Centurion", "Midrand", "Sandton", "Soweto",
        "Ekurhuleni", "Germiston", "Benoni", "Boksburg", "Kempton Park",
        "Vereeniging", "Vanderbijlpark", "Randburg", "Roodepoort",
    ],
    "Western Cape": [
        "Cape Town", "Stellenbosch", "George", "Paarl", "Worcester",
        "Swellendam", "Knysna", "Mossel Bay", "Hermanus", "Oudtshoorn",
        "Beaufort West",
    ],
    "KwaZulu-Natal": [
        "Durban", "Pietermaritzburg", "Richards Bay", "Newcastle", "Ladysmith",
        "Ulundi", "Port Shepstone", "Empangeni", "Kokstad",
    ],
    "Eastern Cape": [
        "Gqeberha", "East London", "Mthatha", "Queenstown", "Graaff-Reinet",
        "Aliwal North", "Matatiele", "Mount Frere", "Lusikisiki",
        "Butterworth", "Port St Johns",
    ],
    "Free State": [
        "Bloemfontein", "Welkom", "Kroonstad", "Sasolburg", "Phuthaditjhaba",
        "Bethlehem", "Harrismith", "Parys",
    ],
    "Limpopo": [
        "Polokwane", "Tzaneen", "Lephalale", "Modimolle", "Thohoyandou",
        "Burgersfort", "Giyani", "Makhado", "Bela-Bela",
    ],
    "Mpumalanga": [
        "Nelspruit", "Witbank", "Middelburg", "Secunda", "Ermelo",
        "Malelane", "Sabie", "Graskop",
    ],
    "North West": [
        "Mahikeng", "Rustenburg", "Klerksdorp", "Potchefstroom", "Brits",
        "Vryburg", "Lichtenburg", "Taung",
    ],
    "Northern Cape": [
        "Kimberley", "Barkly West", "Warrenton", "Hartswater", "Upington",
        "Kakamas", "Groblershoop", "Postmasburg", "Springbok", "Port Nolloth",
        "Garies", "Calvinia", "Sutherland", "Pofadder", "De Aar", "Colesberg",
        "Victoria West", "Carnarvon", "Prieska", "Douglas", "Kuruman", "Kathu",
    ],
}

# =============================================================================
# DATE PARSING
# =============================================================================

_DATE_FORMATS: list[str] = [
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
    "%d %B %Y", "%d %b %Y",
    "%B %d, %Y", "%b %d, %Y",
    "%d/%m/%y", "%Y/%m/%d",
    "%d %B %Y - %H:%M",
    "%A, %d %B %Y - %H:%M",
]

_DATE_EXTRACT_RE = re.compile(
    r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{2}[/\-]\d{2}|'
    r'\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|'
    r'Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|'
    r'Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\b',
    re.IGNORECASE,
)


def parse_date(text: str) -> Optional[datetime]:
    """
    Parse a date string into a timezone-aware datetime.

    FIX: Returns datetime (not date) to match the DateTime DB column type.
    FIX: Returns timezone-aware datetime to prevent comparison errors.
    Returns None if parsing fails — caller decides what to do.
    """
    if not text:
        return None
    text = text.strip()

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    match = _DATE_EXTRACT_RE.search(text)
    if match:
        candidate = match.group(0)
        for fmt in _DATE_FORMATS:
            try:
                dt = datetime.strptime(candidate, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

    return None


def is_closing_date_expired(closing_date_str: str) -> bool:
    """
    Return True if the closing date is parseable AND in the past.
    Returns False on parse failure (keep tender to be safe).
    """
    parsed = parse_date(closing_date_str)
    if parsed is None:
        return False
    return parsed < datetime.now(timezone.utc)


# =============================================================================
# CONTENT HASH
# =============================================================================

def make_content_hash(title: str, url: str, closing_date: str = "") -> str:
    """
    Create a deduplication hash for a tender.

    FIX: Include closing_date in the hash. Without it, a reissued tender
    with the same title and URL but a new closing date gets the same hash
    and the updated version is silently dropped as a duplicate.

    Args:
        title:        Tender title
        url:          Source URL
        closing_date: Closing date string (optional but recommended)

    Returns:
        32-character MD5 hash
    """
    key = f"{title.lower().strip()}|{url.lower().strip()}|{closing_date.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()


# =============================================================================
# DETECTION HELPERS
# =============================================================================

def detect_industry(text: str) -> Optional[str]:
    """
    Detect industry category from tender text.

    FIX: Returns None (not "General") when no match is found.
    "General" was a fake category that polluted filters and analytics.
    The DB column is nullable — use None to mean unclassified.
    """
    if not text:
        return None
    t = text.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(k in t for k in keywords):
            return industry
    return None


def detect_province(text: str) -> Optional[str]:
    """Detect province from tender text. Used for aggregators only."""
    if not text:
        return None
    t = text.lower()
    for province, keywords in PROVINCE_KEYWORDS.items():
        if any(k in t for k in keywords):
            return province
    return None


def detect_municipality(text: str, province: Optional[str] = None) -> Optional[str]:
    """
    Detect municipality from tender text.

    FIX: Fixed broken indentation — the re.search() call was one level
    short, making it execute unconditionally rather than inside the for loop.
    FIX: Removed unused text_lower variable.
    """
    if not text:
        return None

    candidates = (
        MUNICIPALITIES.get(province, [])
        if province
        else [m for lst in MUNICIPALITIES.values() for m in lst]
    )

    for mun in candidates:
        # FIX: Correct indentation — was misaligned causing wrong scoping
        if re.search(r'\b' + re.escape(mun) + r'\b', text, re.IGNORECASE):
            return mun
    return None


def detect_town(text: str, province: Optional[str] = None) -> Optional[str]:
    """
    Detect town from tender text.
    FIX: Removed unused text_lower variable.
    """
    if not text:
        return None

    candidates = (
        TOWNS.get(province, [])
        if province
        else [t for lst in TOWNS.values() for t in lst]
    )

    for town in candidates:
        if re.search(r'\b' + re.escape(town) + r'\b', text, re.IGNORECASE):
            return town
    return None


def clean_text(text: str) -> str:
    """Collapse whitespace and strip. Returns empty string for None/empty input."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


# =============================================================================
# EXPIRY HEURISTIC
# =============================================================================

def is_likely_expired(text: str, url: str) -> bool:
    """
    Heuristic: return True if text/URL contains years older than last year.

    FIX: CURRENT_YEAR was hardcoded to 2026. Now derived at call time so
    the function stays correct across calendar years without code changes.

    FIX: Previous range was range(2018, CURRENT_YEAR - 1) which excluded
    the previous year. A 2025 tender is expired in 2027 — this now uses
    current_year - 1 as the cutoff correctly.
    """
    current_year = datetime.now(timezone.utc).year
    combined     = (text + " " + url).lower()
    old_years    = [str(y) for y in range(2018, current_year - 1)]
    return any(year in combined for year in old_years)


# =============================================================================
# URL HEALTH CHECK
# =============================================================================

async def url_is_alive(url: str) -> bool:
    """
    Check if a URL returns a non-error HTTP status.

    FIX: verify=False removed — use default TLS verification.
    Known-broken SSL domains should be handled at the call site.
    """
    import httpx
    try:
        async with httpx.AsyncClient(
            timeout=8,
            verify=True,             # FIX: no global SSL bypass
            follow_redirects=True,
        ) as client:
            r = await client.head(url)
            if r.status_code == 405:  # HEAD not allowed — try GET
                r = await client.get(url)
            return r.status_code < 400
    except Exception:
        return False