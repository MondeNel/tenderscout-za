import hashlib
import re
from typing import Optional
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Industry detection
# ---------------------------------------------------------------------------

INDUSTRY_KEYWORDS = {
    "Security Services":      ["security", "guarding", "cctv", "access control", "surveillance"],
    "Construction":           ["construction", "building", "civil works", "infrastructure", "roads", "housing", "paving", "fencing"],
    "Waste Management":       ["waste", "refuse", "sanitation", "recycling", "sewage", "solid waste"],
    "Electrical Services":    ["electrical", "wiring", "substation", "generator", "electrification", "solar", "metering"],
    "Plumbing":               ["plumbing", "pipes", "water reticulation", "drainage", "waterworks"],
    "ICT / Technology":       ["ict", "software", "network", "it support", "hardware", "telecommunications", "fiber", "broadband", "system"],
    "Maintenance":            ["maintenance", "repairs", "facilities management", "renovations", "refurbishment"],
    "Mining Services":        ["mining", "drilling", "blasting", "shaft", "mineral", "geological"],
    "Cleaning Services":      ["cleaning", "hygiene", "janitorial", "pest control", "fumigation"],
    "Catering":               ["catering", "food supply", "meals", "canteen", "refreshments"],
    "Consulting":             ["consulting", "advisory", "professional services", "research", "feasibility"],
    "Transport & Logistics":  ["transport", "logistics", "fleet", "courier", "vehicles", "buses"],
    "Healthcare":             ["medical", "healthcare", "pharmaceutical", "clinic", "ambulance", "nursing"],
    "Landscaping":            ["landscaping", "gardening", "horticulture", "parks", "grass cutting"],
}

# ---------------------------------------------------------------------------
# Province detection — used ONLY for aggregator scrapers
# ---------------------------------------------------------------------------
# Direct portal scrapers always use config province (allow_province_detection=False).
# WARNING: Do NOT add bare "cape" — matches both "Western Cape" and "Northern Cape".

PROVINCE_KEYWORDS = {
    "Gauteng":       ["gauteng", "johannesburg", "pretoria", "ekurhuleni", "soweto", "midrand", "tshwane", "centurion", "sandton"],
    "Western Cape":  ["western cape", "cape town", "stellenbosch", "george", "paarl", "worcester"],
    "KwaZulu-Natal": ["kwazulu-natal", "kzn", "durban", "pietermaritzburg", "richards bay", "ethekwini"],
    "Eastern Cape":  ["eastern cape", "gqeberha", "port elizabeth", "east london", "mthatha", "buffalo city"],
    "Free State":    ["free state", "bloemfontein", "mangaung", "welkom"],
    "Limpopo":       ["limpopo", "polokwane", "tzaneen", "bela-bela"],
    "Mpumalanga":    ["mpumalanga", "nelspruit", "mbombela", "witbank", "emalahleni"],
    "North West":    ["north west", "mahikeng", "rustenburg", "klerksdorp"],
    # Only unambiguous NC-specific terms — NOT bare "cape" or "northern"
    "Northern Cape": [
        "northern cape", "kimberley", "upington", "springbok", "de aar",
        "prieska", "kuruman", "kathu", "postmasburg", "calvinia", "colesberg",
        "victoria west", "carnarvon", "sutherland", "pofadder", "kakamas",
        "groblershoop", "barkly west", "warrenton", "hartswater", "douglas",
        "hopetown", "petrusville", "port nolloth", "garies",
    ],
}

# ---------------------------------------------------------------------------
# Municipalities — scoped per province
# ---------------------------------------------------------------------------

MUNICIPALITIES = {
    "Eastern Cape":  ["Buffalo City", "Nelson Mandela Bay", "Chris Hani", "Joe Gqabi", "O.R. Tambo", "Alfred Nzo", "Amathole", "Sarah Baartman"],
    "Free State":    ["Mangaung", "Fezile Dabi", "Lejweleputswa", "Thabo Mofutsanyana", "Xhariep"],
    "Gauteng":       ["City of Johannesburg", "City of Tshwane", "City of Ekurhuleni", "Sedibeng", "West Rand"],
    "KwaZulu-Natal": ["eThekwini", "Ugu", "Umgungundlovu", "Uthukela", "Umzinyathi", "Amajuba", "Zululand", "Umkhanyakude", "King Cetshwayo", "Ilembe", "Harry Gwala"],
    "Limpopo":       ["Capricorn", "Mopani", "Sekhukhune", "Vhembe", "Waterberg"],
    "Mpumalanga":    ["Ehlanzeni", "Gert Sibande", "Nkangala"],
    "North West":    ["Bojanala", "Ngaka Modiri Molema", "Dr Ruth Segomotsi Mompati", "Dr Kenneth Kaunda"],
    "Western Cape":  ["City of Cape Town", "Cape Winelands", "Central Karoo", "Garden Route", "Overberg", "West Coast"],
    "Northern Cape": [
        "Frances Baard", "ZF Mgcawu", "Namakwa", "Pixley ka Seme", "John Taolo Gaetsewe",
        "Sol Plaatje", "Dikgatlong", "Magareng", "Phokwane",
        "Dawid Kruiper", "Kai Garib", "Khara Hais", "Kheis", "Tsantsabane",
        "Richtersveld", "Nama Khoi", "Kamiesberg", "Hantam", "Karoo Hoogland", "Khai-Ma",
        "Ubuntu", "Umsobomvu", "Emthanjeni", "Kareeberg", "Renosterberg",
        "Thembelihle", "Siyathemba", "Siyancuma",
        "Joe Morolong", "Gamagara", "Ga-Segonyana",
    ],
}

# ---------------------------------------------------------------------------
# Towns — scoped per province
# ---------------------------------------------------------------------------

TOWNS = {
    "Gauteng":       ["Johannesburg", "Pretoria", "Centurion", "Midrand", "Sandton", "Soweto", "Ekurhuleni", "Germiston", "Benoni", "Boksburg", "Kempton Park"],
    "Western Cape":  ["Cape Town", "Stellenbosch", "George", "Paarl", "Worcester", "Swellendam", "Knysna", "Mossel Bay"],
    "KwaZulu-Natal": ["Durban", "Pietermaritzburg", "Richards Bay", "Newcastle", "Ladysmith", "Ulundi"],
    "Eastern Cape":  ["Gqeberha", "East London", "Mthatha", "Queenstown", "Graaff-Reinet"],
    "Free State":    ["Bloemfontein", "Welkom", "Kroonstad", "Sasolburg"],
    "Limpopo":       ["Polokwane", "Tzaneen", "Lephalale", "Modimolle"],
    "Mpumalanga":    ["Nelspruit", "Witbank", "Middelburg", "Secunda"],
    "North West":    ["Mahikeng", "Rustenburg", "Klerksdorp", "Potchefstroom"],
    "Northern Cape": [
        "Kimberley", "Barkly West", "Warrenton", "Hartswater",
        "Upington", "Kakamas", "Groblershoop", "Postmasburg",
        "Springbok", "Port Nolloth", "Garies", "Calvinia", "Sutherland", "Pofadder",
        "De Aar", "Colesberg", "Victoria West", "Carnarvon", "Petrusville",
        "Hopetown", "Prieska", "Douglas",
        "Kuruman", "Kathu",
    ],
}

# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
    "%d %B %Y", "%d %b %Y",
    "%B %d, %Y", "%b %d, %Y",
    "%d/%m/%y",
]

_DATE_EXTRACT_RE = re.compile(
    r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{2}[/\-]\d{2}|'
    r'\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|'
    r'Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|'
    r'Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\b',
    re.IGNORECASE,
)


def _parse_date(text: str) -> Optional[date]:
    """Extract and parse a date from a raw string. Returns None if parsing fails."""
    if not text:
        return None
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = _DATE_EXTRACT_RE.search(text)
    if match:
        candidate = match.group(0)
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def is_closing_date_expired(closing_date_str: str) -> bool:
    """
    Returns True if the closing date is parseable AND is before today.
    Returns False (benefit of the doubt) if the date cannot be parsed.
    """
    parsed = _parse_date(closing_date_str)
    if parsed is None:
        return False
    return parsed < date.today()


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def make_content_hash(title: str, url: str) -> str:
    return hashlib.md5(f"{title.lower().strip()}{url.lower().strip()}".encode()).hexdigest()


def detect_industry(text: str) -> str:
    t = text.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(k in t for k in keywords):
            return industry
    return "General"


def detect_province(text: str) -> Optional[str]:
    """
    Detect province from free text.
    Used ONLY for aggregators — direct portal scrapers use config province.
    Returns None if province cannot be confidently identified.
    """
    t = text.lower()
    for province, keywords in PROVINCE_KEYWORDS.items():
        if any(k in t for k in keywords):
            return province
    return None


def detect_municipality(text: str, province: Optional[str] = None) -> Optional[str]:
    if not text:
        return None
    text_lower = text.lower()
    candidates = (
        MUNICIPALITIES.get(province, [])
        if province
        else [m for lst in MUNICIPALITIES.values() for m in lst]
    )
    for mun in candidates:
        if re.search(r'\b' + re.escape(mun.lower()) + r'\b', text_lower):
            return mun
    return None


def detect_town(text: str, province: Optional[str] = None) -> Optional[str]:
    if not text:
        return None
    text_lower = text.lower()
    candidates = (
        TOWNS.get(province, [])
        if province
        else [t for lst in TOWNS.values() for t in lst]
    )
    for town in candidates:
        if re.search(r'\b' + re.escape(town.lower()) + r'\b', text_lower):
            return town
    return None


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def get_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
        "Connection": "keep-alive",
    }


CURRENT_YEAR = 2026


def is_likely_expired(text: str, url: str) -> bool:
    """Heuristic: text/URL contains a year older than current-1."""
    combined = (text + " " + url).lower()
    old_years = [str(y) for y in range(2018, CURRENT_YEAR - 1)]
    return any(year in combined for year in old_years)


async def url_is_alive(url: str) -> bool:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8, verify=False, follow_redirects=True) as client:
            r = await client.head(url)
            if r.status_code == 405:
                r = await client.get(url)
            return r.status_code < 400
    except Exception:
        return False