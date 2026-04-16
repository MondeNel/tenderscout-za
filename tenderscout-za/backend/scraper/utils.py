import hashlib
import re
from typing import Optional
from datetime import datetime
import dateparser  # new dependency: add to requirements.txt

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

# Province keywords – used as fallback after city detection
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

# City/Town to Province mapping (for cases where the province name is not explicitly mentioned)
CITY_TO_PROVINCE = {
    # Gauteng
    "pretoria": "Gauteng", "johannesburg": "Gauteng", "centurion": "Gauteng", "midrand": "Gauteng",
    "sandton": "Gauteng", "soweto": "Gauteng", "ekurhuleni": "Gauteng", "germiston": "Gauteng",
    "benoni": "Gauteng", "boksburg": "Gauteng", "kempton park": "Gauteng",
    # Western Cape
    "cape town": "Western Cape", "stellenbosch": "Western Cape", "george": "Western Cape",
    "paarl": "Western Cape", "worcester": "Western Cape", "knysna": "Western Cape",
    # KwaZulu-Natal
    "durban": "KwaZulu-Natal", "pietermaritzburg": "KwaZulu-Natal", "richards bay": "KwaZulu-Natal",
    "newcastle": "KwaZulu-Natal", "ladysmith": "KwaZulu-Natal", "ulundi": "KwaZulu-Natal",
    # Eastern Cape
    "gqeberha": "Eastern Cape", "port elizabeth": "Eastern Cape", "east london": "Eastern Cape",
    "mthatha": "Eastern Cape", "queenstown": "Eastern Cape", "graaff-reinet": "Eastern Cape",
    # Free State
    "bloemfontein": "Free State", "welkom": "Free State", "kroonstad": "Free State", "sasolburg": "Free State",
    # Limpopo
    "polokwane": "Limpopo", "tzaneen": "Limpopo", "lephalale": "Limpopo", "modimolle": "Limpopo",
    # Mpumalanga
    "nelspruit": "Mpumalanga", "mbombela": "Mpumalanga", "witbank": "Mpumalanga", "middelburg": "Mpumalanga",
    "secunda": "Mpumalanga", "emalahleni": "Mpumalanga",
    # North West
    "mahikeng": "North West", "mafikeng": "North West", "rustenburg": "North West", "klerksdorp": "North West",
    "potchefstroom": "North West",
    # Northern Cape
    "kimberley": "Northern Cape", "upington": "Northern Cape", "springbok": "Northern Cape", "de aar": "Northern Cape",
    "prieska": "Northern Cape", "kuruman": "Northern Cape", "kathu": "Northern Cape", "postmasburg": "Northern Cape",
    "calvinia": "Northern Cape", "colesberg": "Northern Cape", "victoria west": "Northern Cape", "carnarvon": "Northern Cape",
    "sutherland": "Northern Cape", "pofadder": "Northern Cape", "kakamas": "Northern Cape", "groblershoop": "Northern Cape",
    "barkly west": "Northern Cape", "warrenton": "Northern Cape", "hartswater": "Northern Cape", "douglas": "Northern Cape",
    "hopetown": "Northern Cape", "petrusville": "Northern Cape", "port nolloth": "Northern Cape", "garies": "Northern Cape",
}

# ---------------------------------------------------------------------------
# Municipalities and Towns
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
    Detect province from free text. First tries to find a known city/town,
    then falls back to province name keywords. Returns None if no match.
    """
    if not text:
        return None
    t = text.lower()
    
    # First, try to find a known city/town in the text
    for city, province in CITY_TO_PROVINCE.items():
        if re.search(r'\b' + re.escape(city) + r'\b', t):
            return province
    
    # Then, try province name keywords (original method)
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

def is_likely_expired(text: str, url: str) -> bool:
    combined = (text + " " + url).lower()
    current_year = datetime.now().year
    # Find all 4-digit years
    years = re.findall(r'\b(20\d{2})\b', combined)
    for y in years:
        if int(y) < current_year - 1:  # allow previous year (some tenders still open)
            return True
    return False

def is_closing_date_expired(date_str: str) -> bool:
    """Returns True if the closing date is in the past."""
    if not date_str:
        return False
    date_str = date_str.strip()
    # Use dateparser for robust parsing
    parsed = dateparser.parse(date_str, languages=['en'], settings={'PREFER_DATES_FROM': 'future'})
    if parsed:
        return parsed.date() < datetime.today().date()
    # Fallback to known patterns if dateparser fails (should be rare)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%d %B %Y - %H:%M", "%d-%m-%Y"):
        try:
            d = datetime.strptime(date_str, fmt)
            return d.date() < datetime.today().date()
        except:
            continue
    return False

async def url_is_alive(url: str) -> bool:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8, verify=True, follow_redirects=True) as client:
            r = await client.head(url)
            if r.status_code == 405:
                r = await client.get(url)
            return r.status_code < 400
    except Exception:
        return False

def is_tender_url(url: str, anchor_text: str = "") -> bool:
    url_lower = url.lower()
    anchor_lower = anchor_text.lower()
    tender_keywords = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "supply", "contract"]
    if any(kw in url_lower for kw in tender_keywords):
        return True
    if any(kw in anchor_lower for kw in tender_keywords):
        return True
    return False