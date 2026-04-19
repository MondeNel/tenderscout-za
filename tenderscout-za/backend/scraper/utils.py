import hashlib
import re
from typing import Optional
from datetime import datetime

# ---------------------------------------------------------------------------
# Industry detection
# ---------------------------------------------------------------------------

INDUSTRY_KEYWORDS = {
    "Security Services":      ["security", "guarding", "cctv", "access control", "surveillance"],
    "Construction":           ["construction", "building", "civil works", "infrastructure", "roads", "housing"],
    "Waste Management":       ["waste", "refuse", "sanitation", "recycling", "sewage"],
    "Electrical Services":    ["electrical", "wiring", "substation", "generator", "electrification"],
    "Plumbing":               ["plumbing", "pipes", "water reticulation", "drainage"],
    "ICT / Technology":       ["ict", "software", "network", "it support", "hardware", "telecommunications", "fiber"],
    "Maintenance":            ["maintenance", "repairs", "facilities management", "renovations"],
    "Mining Services":        ["mining", "drilling", "blasting", "shaft", "mineral"],
    "Cleaning Services":      ["cleaning", "hygiene", "janitorial", "pest control"],
    "Catering":               ["catering", "food supply", "meals", "canteen"],
    "Consulting":             ["consulting", "advisory", "professional services", "research"],
    "Transport & Logistics":  ["transport", "logistics", "fleet", "courier", "vehicles"],
    "Healthcare":             ["medical", "healthcare", "pharmaceutical", "clinic", "ambulance"],
    "Landscaping":            ["landscaping", "gardening", "horticulture", "parks"],
}

PROVINCE_KEYWORDS = {
    "Gauteng":        ["gauteng", "johannesburg", "pretoria", "ekurhuleni", "soweto", "midrand", "tshwane", "centurion", "sandton"],
    "Western Cape":   ["western cape", "cape town", "stellenbosch", "george", "paarl", "worcester"],
    "KwaZulu-Natal":  ["kwazulu-natal", "kzn", "durban", "pietermaritzburg", "richards bay", "ethekwini"],
    "Eastern Cape":   ["eastern cape", "gqeberha", "port elizabeth", "east london", "mthatha", "buffalo city"],
    "Free State":     ["free state", "bloemfontein", "mangaung", "welkom"],
    "Limpopo":        ["limpopo", "polokwane", "tzaneen", "bela-bela"],
    "Mpumalanga":     ["mpumalanga", "nelspruit", "mbombela", "witbank", "emalahleni"],
    "North West":     ["north west", "mahikeng", "rustenburg", "klerksdorp"],
    "Northern Cape":  [
        "northern cape", "kimberley", "upington", "springbok", "de aar",
        "prieska", "kuruman", "kathu", "postmasburg", "calvinia", "colesberg",
        "victoria west", "carnarvon", "sutherland", "pofadder", "kakamas",
        "groblershoop", "barkly west", "warrenton", "hartswater", "douglas",
        "hopetown", "petrusville", "port nolloth", "garies",
    ],
}

CITY_TO_PROVINCE = {
    "pretoria": "Gauteng", "johannesburg": "Gauteng", "centurion": "Gauteng", "midrand": "Gauteng",
    "sandton": "Gauteng", "soweto": "Gauteng", "ekurhuleni": "Gauteng", "germiston": "Gauteng",
    "benoni": "Gauteng", "boksburg": "Gauteng", "kempton park": "Gauteng",
    "cape town": "Western Cape", "stellenbosch": "Western Cape", "george": "Western Cape",
    "paarl": "Western Cape", "worcester": "Western Cape", "knysna": "Western Cape",
    "durban": "KwaZulu-Natal", "pietermaritzburg": "KwaZulu-Natal", "richards bay": "KwaZulu-Natal",
    "newcastle": "KwaZulu-Natal", "ladysmith": "KwaZulu-Natal", "ulundi": "KwaZulu-Natal",
    "gqeberha": "Eastern Cape", "port elizabeth": "Eastern Cape", "east london": "Eastern Cape",
    "mthatha": "Eastern Cape", "queenstown": "Eastern Cape", "graaff-reinet": "Eastern Cape",
    "bloemfontein": "Free State", "welkom": "Free State", "kroonstad": "Free State", "sasolburg": "Free State",
    "polokwane": "Limpopo", "tzaneen": "Limpopo", "lephalale": "Limpopo", "modimolle": "Limpopo",
    "nelspruit": "Mpumalanga", "mbombela": "Mpumalanga", "witbank": "Mpumalanga", "middelburg": "Mpumalanga",
    "secunda": "Mpumalanga", "emalahleni": "Mpumalanga",
    "mahikeng": "North West", "mafikeng": "North West", "rustenburg": "North West", "klerksdorp": "North West",
    "potchefstroom": "North West",
    "kimberley": "Northern Cape", "upington": "Northern Cape", "springbok": "Northern Cape", "de aar": "Northern Cape",
    "prieska": "Northern Cape", "kuruman": "Northern Cape", "kathu": "Northern Cape", "postmasburg": "Northern Cape",
    "calvinia": "Northern Cape", "colesberg": "Northern Cape", "victoria west": "Northern Cape", "carnarvon": "Northern Cape",
    "sutherland": "Northern Cape", "pofadder": "Northern Cape", "kakamas": "Northern Cape", "groblershoop": "Northern Cape",
    "barkly west": "Northern Cape", "warrenton": "Northern Cape", "hartswater": "Northern Cape", "douglas": "Northern Cape",
    "hopetown": "Northern Cape", "petrusville": "Northern Cape", "port nolloth": "Northern Cape", "garies": "Northern Cape",
}

MUNICIPALITIES = {
    "Eastern Cape":   ["Buffalo City", "Nelson Mandela Bay", "Chris Hani", "Joe Gqabi", "O.R. Tambo", "Alfred Nzo", "Amathole", "Sarah Baartman"],
    "Free State":     ["Mangaung", "Fezile Dabi", "Lejweleputswa", "Thabo Mofutsanyana", "Xhariep"],
    "Gauteng":        ["City of Johannesburg", "City of Tshwane", "City of Ekurhuleni", "Sedibeng", "West Rand"],
    "KwaZulu-Natal":  ["eThekwini", "Ugu", "Umgungundlovu", "Uthukela", "Umzinyathi", "Amajuba", "Zululand", "Umkhanyakude", "King Cetshwayo", "Ilembe", "Harry Gwala"],
    "Limpopo":        ["Capricorn", "Mopani", "Sekhukhune", "Vhembe", "Waterberg"],
    "Mpumalanga":     ["Ehlanzeni", "Gert Sibande", "Nkangala"],
    "North West":     ["Bojanala", "Ngaka Modiri Molema", "Dr Ruth Segomotsi Mompati", "Dr Kenneth Kaunda"],
    "Western Cape":   ["City of Cape Town", "Cape Winelands", "Central Karoo", "Garden Route", "Overberg", "West Coast"],
    "Northern Cape": [
        "Frances Baard", "ZF Mgcawu", "Namakwa", "Pixley ka Seme", "John Taolo Gaetsewe",
        "Sol Plaatje", "Dikgatlong", "Magareng", "Phokwane",
        "Dawid Kruiper", "Kai Garib", "Khara Hais", "Kheis", "Tsantsabane",
        "Richtersveld", "Nama Khoi", "Kamiesberg", "Hantam", "Karoo Hoogland", "Khai-Ma",
        "Ubuntu", "Umsobomvu", "Emthanjeni", "Kareeberg", "Renosterberg", "Thembelihle", "Siyathemba", "Siyancuma",
        "Joe Morolong", "Gamagara", "Ga-Segonyana",
    ],
}

TOWNS = {
    "Gauteng":        ["Johannesburg", "Pretoria", "Centurion", "Midrand", "Sandton", "Soweto", "Ekurhuleni", "Germiston", "Benoni", "Boksburg", "Kempton Park"],
    "Western Cape":   ["Cape Town", "Stellenbosch", "George", "Paarl", "Worcester", "Swellendam", "Knysna", "Mossel Bay"],
    "KwaZulu-Natal":  ["Durban", "Pietermaritzburg", "Richards Bay", "Newcastle", "Ladysmith", "Ulundi"],
    "Eastern Cape":   ["Gqeberha", "East London", "Mthatha", "Queenstown", "Graaff-Reinet"],
    "Free State":     ["Bloemfontein", "Welkom", "Kroonstad", "Sasolburg"],
    "Limpopo":        ["Polokwane", "Tzaneen", "Lephalale", "Modimolle"],
    "Mpumalanga":     ["Nelspruit", "Witbank", "Middelburg", "Secunda"],
    "North West":     ["Mahikeng", "Rustenburg", "Klerksdorp", "Potchefstroom"],
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
# Helpers
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
    if not text:
        return None
    t = text.lower()
    for city, province in CITY_TO_PROVINCE.items():
        if re.search(r'\b' + re.escape(city) + r'\b', t):
            return province
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


# FIX: was `CURRENT_YEAR - 1` which marked all of 2025 as expired when running in 2026.
# Now dynamically computed so it always points to 2+ years ago.
def _stale_year_threshold() -> int:
    return datetime.utcnow().year - 1


def is_likely_expired(text: str, url: str) -> bool:
    """Return True only if the text/URL explicitly references a year older than last year."""
    combined = (text + " " + url).lower()
    threshold = _stale_year_threshold()
    old_years = [str(y) for y in range(2018, threshold)]
    for year in old_years:
        if year in combined:
            return True
    return False


# ---------------------------------------------------------------------------
# Closing date parsing — SA government sites use many formats
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%d/%m/%Y",           # 31/12/2026
    "%d-%m-%Y",           # 31-12-2026
    "%Y-%m-%d",           # 2026-12-31
    "%d %B %Y",           # 31 December 2026
    "%d %b %Y",           # 31 Dec 2026
    "%d %B %Y - %H:%M",   # 31 December 2026 - 14:00
    "%d %b %Y - %H:%M",   # 31 Dec 2026 - 14:00
    "%B %d, %Y",          # December 31, 2026
    "%b %d, %Y",          # Dec 31, 2026
    "%d/%m/%Y %H:%M",     # 31/12/2026 14:00
    "%Y/%m/%d",           # 2026/12/31
    "%d.%m.%Y",           # 31.12.2026
]

# Matches e.g. "31 December 2026", "31 Dec 2026", "31/12/2026", "2026-12-31"
_DATE_RE = re.compile(
    r'\b(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})'          # 31/12/2026
    r'|\b(\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2})'          # 2026-12-31
    r'|\b(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\s+\d{4})',                                      # 31 December 2026
    re.IGNORECASE
)


def parse_closing_date(date_str: str) -> Optional[datetime]:
    """Try to parse a date string into a datetime. Returns None if unparseable."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # Extract just the date part if there's surrounding noise
    m = _DATE_RE.search(date_str)
    if m:
        date_str = (m.group(1) or m.group(2) or m.group(3)).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def is_closing_date_expired(date_str: str) -> bool:
    """Returns True if the closing date is in the past. Unparseable dates return False (keep tender)."""
    d = parse_closing_date(date_str)
    if d is None:
        return False
    return d.date() < datetime.today().date()


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