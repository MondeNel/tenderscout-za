import hashlib
import re
from typing import Optional

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

# ---------------------------------------------------------------------------
# Province detection
# ---------------------------------------------------------------------------
# NOTE: Province detection from text is only used as a *last resort* for
# aggregator scrapers that have no source-level province context.
# Direct portal scrapers always use the config province — see city_portals.py.
# ---------------------------------------------------------------------------

PROVINCE_KEYWORDS = {
    "Gauteng":        ["gauteng", "johannesburg", "pretoria", "ekurhuleni", "soweto", "midrand", "tshwane", "centurion", "sandton"],
    "Western Cape":   ["western cape", "cape town", "stellenbosch", "george", "paarl", "worcester"],
    "KwaZulu-Natal":  ["kwazulu-natal", "kzn", "durban", "pietermaritzburg", "richards bay", "ethekwini"],
    "Eastern Cape":   ["eastern cape", "gqeberha", "port elizabeth", "east london", "mthatha", "buffalo city"],
    "Free State":     ["free state", "bloemfontein", "mangaung", "welkom"],
    "Limpopo":        ["limpopo", "polokwane", "tzaneen", "bela-bela"],
    "Mpumalanga":     ["mpumalanga", "nelspruit", "mbombela", "witbank", "emalahleni"],
    "North West":     ["north west", "mahikeng", "rustenburg", "klerksdorp"],
    # Northern Cape: match specific NC towns ONLY — do NOT include bare "cape"
    # to avoid false matches with "Cape Town" / "Western Cape"
    "Northern Cape":  [
        "northern cape", "kimberley", "upington", "springbok", "de aar",
        "prieska", "kuruman", "kathu", "postmasburg", "calvinia", "colesberg",
        "victoria west", "carnarvon", "sutherland", "pofadder", "kakamas",
        "groblershoop", "barkly west", "warrenton", "hartswater", "douglas",
        "hopetown", "petrusville", "port nolloth", "garies",
    ],
}

# ---------------------------------------------------------------------------
# Municipalities
# ---------------------------------------------------------------------------

MUNICIPALITIES = {
    "Eastern Cape":   ["Buffalo City", "Nelson Mandela Bay", "Chris Hani", "Joe Gqabi", "O.R. Tambo", "Alfred Nzo", "Amathole", "Sarah Baartman"],
    "Free State":     ["Mangaung", "Fezile Dabi", "Lejweleputswa", "Thabo Mofutsanyana", "Xhariep"],
    "Gauteng":        ["City of Johannesburg", "City of Tshwane", "City of Ekurhuleni", "Sedibeng", "West Rand"],
    "KwaZulu-Natal":  ["eThekwini", "Ugu", "Umgungundlovu", "Uthukela", "Umzinyathi", "Amajuba", "Zululand", "Umkhanyakude", "King Cetshwayo", "Ilembe", "Harry Gwala"],
    "Limpopo":        ["Capricorn", "Mopani", "Sekhukhune", "Vhembe", "Waterberg"],
    "Mpumalanga":     ["Ehlanzeni", "Gert Sibande", "Nkangala"],
    "North West":     ["Bojanala", "Ngaka Modiri Molema", "Dr Ruth Segomotsi Mompati", "Dr Kenneth Kaunda"],
    "Western Cape":   ["City of Cape Town", "Cape Winelands", "Central Karoo", "Garden Route", "Overberg", "West Coast"],

    # Northern Cape — all 5 district municipalities + 22 local municipalities
    "Northern Cape": [
        # District municipalities
        "Frances Baard",
        "ZF Mgcawu",
        "Namakwa",
        "Pixley ka Seme",
        "John Taolo Gaetsewe",
        # Frances Baard locals
        "Sol Plaatje",
        "Dikgatlong",
        "Magareng",
        "Phokwane",
        # ZF Mgcawu locals
        "Dawid Kruiper",
        "Kai Garib",
        "Khara Hais",
        "Kheis",
        "Tsantsabane",
        # Namakwa locals
        "Richtersveld",
        "Nama Khoi",
        "Kamiesberg",
        "Hantam",
        "Karoo Hoogland",
        "Khai-Ma",
        # Pixley ka Seme locals
        "Ubuntu",
        "Umsobomvu",
        "Emthanjeni",
        "Kareeberg",
        "Renosterberg",
        "Thembelihle",
        "Siyathemba",
        "Siyancuma",
        # John Taolo Gaetsewe locals
        "Joe Morolong",
        "Gamagara",
        "Ga-Segonyana",
    ],
}

# ---------------------------------------------------------------------------
# Towns / cities
# ---------------------------------------------------------------------------

TOWNS = {
    "Gauteng":        ["Johannesburg", "Pretoria", "Centurion", "Midrand", "Sandton", "Soweto", "Ekurhuleni", "Germiston", "Benoni", "Boksburg", "Kempton Park"],
    "Western Cape":   ["Cape Town", "Stellenbosch", "George", "Paarl", "Worcester", "Swellendam", "Knysna", "Mossel Bay"],
    "KwaZulu-Natal":  ["Durban", "Pietermaritzburg", "Richards Bay", "Newcastle", "Ladysmith", "Ulundi"],
    "Eastern Cape":   ["Gqeberha", "East London", "Mthatha", "Queenstown", "Graaff-Reinet"],
    "Free State":     ["Bloemfontein", "Welkom", "Kroonstad", "Sasolburg"],
    "Limpopo":        ["Polokwane", "Tzaneen", "Lephalale", "Modimolle"],
    "Mpumalanga":     ["Nelspruit", "Witbank", "Middelburg", "Secunda"],
    "North West":     ["Mahikeng", "Rustenburg", "Klerksdorp", "Potchefstroom"],

    # Northern Cape — complete list of all district/local towns
    "Northern Cape": [
        # Frances Baard
        "Kimberley", "Barkly West", "Warrenton", "Hartswater",
        # ZF Mgcawu
        "Upington", "Kakamas", "Groblershoop", "Postmasburg",
        # Namakwa
        "Springbok", "Port Nolloth", "Garies", "Calvinia", "Sutherland", "Pofadder",
        # Pixley ka Seme
        "De Aar", "Colesberg", "Victoria West", "Carnarvon", "Petrusville",
        "Hopetown", "Prieska", "Douglas",
        # John Taolo Gaetsewe
        "Kuruman", "Kathu",
    ],
}

# ---------------------------------------------------------------------------
# Helper functions
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
    Detect province from free text. Used only for aggregator scrapers.
    Returns None if no province can be confidently identified.
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
    combined = (text + " " + url).lower()
    old_years = [str(y) for y in range(2018, CURRENT_YEAR - 1)]
    for year in old_years:
        if year in combined:
            return True
    return False


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