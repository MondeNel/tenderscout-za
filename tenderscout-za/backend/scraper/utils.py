import hashlib, re
from typing import Optional

INDUSTRY_KEYWORDS = {
    "Security Services": ["security", "guarding", "cctv", "access control", "surveillance"],
    "Construction": ["construction", "building", "civil works", "infrastructure", "roads", "housing"],
    "Waste Management": ["waste", "refuse", "sanitation", "recycling", "sewage"],
    "Electrical Services": ["electrical", "wiring", "substation", "generator", "electrification"],
    "Plumbing": ["plumbing", "pipes", "water reticulation", "drainage"],
    "ICT / Technology": ["ict", "software", "network", "it support", "hardware", "telecommunications", "fiber"],
    "Maintenance": ["maintenance", "repairs", "facilities management", "renovations"],
    "Mining Services": ["mining", "drilling", "blasting", "shaft", "mineral"],
    "Cleaning Services": ["cleaning", "hygiene", "janitorial", "pest control"],
    "Catering": ["catering", "food supply", "meals", "canteen"],
    "Consulting": ["consulting", "advisory", "professional services", "research"],
    "Transport & Logistics": ["transport", "logistics", "fleet", "courier", "vehicles"],
    "Healthcare": ["medical", "healthcare", "pharmaceutical", "clinic", "ambulance"],
    "Landscaping": ["landscaping", "gardening", "horticulture", "parks"],
}

PROVINCE_KEYWORDS = {
    "Gauteng": ["gauteng", "johannesburg", "pretoria", "ekurhuleni", "soweto", "midrand", "tshwane", "centurion", "sandton"],
    "Western Cape": ["western cape", "cape town", "stellenbosch", "george", "paarl", "worcester"],
    "KwaZulu-Natal": ["kwazulu-natal", "kzn", "durban", "pietermaritzburg", "richards bay", "ethekwini"],
    "Eastern Cape": ["eastern cape", "gqeberha", "port elizabeth", "east london", "mthatha", "buffalo city"],
    "Free State": ["free state", "bloemfontein", "mangaung", "welkom"],
    "Limpopo": ["limpopo", "polokwane", "tzaneen", "bela-bela"],
    "Mpumalanga": ["mpumalanga", "nelspruit", "mbombela", "witbank", "emalahleni"],
    "North West": ["north west", "mahikeng", "rustenburg", "klerksdorp"],
    "Northern Cape": ["northern cape", "kimberley", "upington", "springbok"],
}


def make_content_hash(title: str, url: str) -> str:
    return hashlib.md5(f"{title.lower().strip()}{url.lower().strip()}".encode()).hexdigest()


def detect_industry(text: str) -> str:
    t = text.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(k in t for k in keywords):
            return industry
    return "General"


def detect_province(text: str) -> Optional[str]:
    t = text.lower()
    for province, keywords in PROVINCE_KEYWORDS.items():
        if any(k in t for k in keywords):
            return province
    return None


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def get_headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
        "Connection": "keep-alive",
    }
