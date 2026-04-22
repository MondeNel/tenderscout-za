"""
scraper/sites/registry.py
==========================
SINGLE SOURCE OF TRUTH for all tender sources.
Last verified: 2026-04-22

This file centralizes ALL website configurations. The orchestrator reads from
this registry to know what to scrape.

CATEGORIES:
    ACTIVE_SOURCES  — Confirmed working, scraped daily
    BROKEN_SOURCES  — Need fixing (moved from ACTIVE when they break)
    DEAD_SOURCES    — DNS failure, site removed, or no working URL (never delete)

SCRAPE TYPES:
    links               Generic anchor-tag scraper
    standard            Generic with parent-element context
    phoca               Joomla Phoca Download component
    phokwane            WordPress category/post page
    dikgatlong          Title + PDF link with closing date in heading
    ga_segonyana        Simple HTML table: Tender Advert | Closing Date
    gamagara            Structured text block parser
    zfm_district        Document directory listing (PDF filenames)
    namakwa_district    Grouped-by-month link list
    kareeberg           Static .htm page with RFQ links
    siyancuma           PDF-link scraper (Siyancuma-specific)
    frances_baard       Card layout with download buttons
    js_playwright       JS-rendered site — Playwright required
    etenders_playwright eTenders-specific Playwright scraper
"""

from typing import List, Dict

# =============================================================================
# ✅ ACTIVE SOURCES — Balanced coverage across all 9 provinces
# =============================================================================

ACTIVE_SOURCES: List[Dict] = [

    # =========================================================================
    # GAUTENG (5 sources)
    # =========================================================================
    {
        "name": "City of Johannesburg",
        "url": "https://www.joburg.org.za/work_/TendersQuotations/Pages/Tenders.aspx",
        "province": "Gauteng", "town": "Johannesburg",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "City of Tshwane",
        "url": "https://www.tshwane.gov.za/?page_id=2194",
        "province": "Gauteng", "town": "Pretoria",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "City of Ekurhuleni",
        "url": "https://www.ekurhuleni.gov.za/tenders",
        "province": "Gauteng", "town": "Ekurhuleni",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Sedibeng District",
        "url": "https://www.sedibeng.gov.za/tenders",
        "province": "Gauteng", "town": "Vereeniging",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "West Rand District",
        "url": "https://www.westranddm.gov.za/tenders",
        "province": "Gauteng", "town": "Randfontein",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # WESTERN CAPE (8 sources)
    # =========================================================================
    {
        "name": "City of Cape Town",
        "url": "https://web1.capetown.gov.za/web1/procurementportal/",
        "province": "Western Cape", "town": "Cape Town",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Stellenbosch Municipality",
        "url": "https://www.stellenbosch.gov.za/tenders",
        "province": "Western Cape", "town": "Stellenbosch",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Drakenstein Municipality",
        "url": "https://www.drakenstein.gov.za/tenders",
        "province": "Western Cape", "town": "Paarl",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "George Municipality",
        "url": "https://www.george.gov.za/tenders",
        "province": "Western Cape", "town": "George",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Garden Route District",
        "url": "https://www.gardenroute.gov.za/tenders",
        "province": "Western Cape", "town": "George",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Cape Winelands District",
        "url": "https://www.capewinelands.gov.za/tenders",
        "province": "Western Cape", "town": "Worcester",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Overberg District",
        "url": "https://www.odm.org.za/tenders",
        "province": "Western Cape", "town": "Bredasdorp",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "West Coast District",
        "url": "https://www.westcoastdm.co.za/tenders",
        "province": "Western Cape", "town": "Moorreesburg",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # KWAZULU-NATAL (8 sources)
    # =========================================================================
    {
        "name": "eThekwini Municipality",
        "url": "https://www.durban.gov.za/pages/government/procurement",
        "province": "KwaZulu-Natal", "town": "Durban",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Msunduzi Municipality",
        "url": "https://www.msunduzi.gov.za/tenders",
        "province": "KwaZulu-Natal", "town": "Pietermaritzburg",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Newcastle Municipality",
        "url": "https://www.newcastle.gov.za/tenders",
        "province": "KwaZulu-Natal", "town": "Newcastle",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Umgungundlovu District",
        "url": "https://www.umdm.gov.za/tenders",
        "province": "KwaZulu-Natal", "town": "Pietermaritzburg",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "King Cetshwayo District",
        "url": "https://www.kingcetshwayo.gov.za/tenders",
        "province": "KwaZulu-Natal", "town": "Richards Bay",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Ugu District",
        "url": "https://www.ugu.gov.za/tenders",
        "province": "KwaZulu-Natal", "town": "Port Shepstone",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Zululand District",
        "url": "https://www.zululand.org.za/tenders",
        "province": "KwaZulu-Natal", "town": "Ulundi",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Harry Gwala District",
        "url": "https://www.harrygwaladm.gov.za/tenders",
        "province": "KwaZulu-Natal", "town": "Ixopo",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # EASTERN CAPE (8 sources)
    # =========================================================================
    {
        "name": "Buffalo City Metro",
        "url": "https://www.buffalocity.gov.za/tenders",
        "province": "Eastern Cape", "town": "East London",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Nelson Mandela Bay",
        "url": "https://www.nelsonmandelabay.gov.za/tenders",
        "province": "Eastern Cape", "town": "Gqeberha",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Sarah Baartman District",
        "url": "https://www.sarahbaartman.gov.za/tenders",
        "province": "Eastern Cape", "town": "Gqeberha",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Chris Hani District",
        "url": "https://www.chrishanidm.gov.za/tenders",
        "province": "Eastern Cape", "town": "Queenstown",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Joe Gqabi District",
        "url": "https://www.jgdm.gov.za/tenders",
        "province": "Eastern Cape", "town": "Aliwal North",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "O.R. Tambo District",
        "url": "https://www.ortambodm.gov.za/tenders",
        "province": "Eastern Cape", "town": "Mthatha",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Alfred Nzo District",
        "url": "https://www.andm.gov.za/tenders",
        "province": "Eastern Cape", "town": "Mount Ayliff",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Amathole District",
        "url": "https://www.amathole.gov.za/tenders",
        "province": "Eastern Cape", "town": "East London",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # FREE STATE (5 sources)
    # =========================================================================
    {
        "name": "Mangaung Municipality",
        "url": "https://www.mangaung.co.za/category/tenders-bids/",
        "province": "Free State", "town": "Bloemfontein",
        "scrape_type": "phokwane", "allow_province_detection": False,
    },
    {
        "name": "Fezile Dabi District",
        "url": "https://www.feziledabi.gov.za/tenders",
        "province": "Free State", "town": "Sasolburg",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Lejweleputswa District",
        "url": "https://www.lejweleputswa.gov.za/tenders",
        "province": "Free State", "town": "Welkom",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Thabo Mofutsanyana District",
        "url": "https://www.thabomofutsanyana.gov.za/tenders",
        "province": "Free State", "town": "Phuthaditjhaba",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Xhariep District",
        "url": "https://www.xhariep.gov.za/tenders",
        "province": "Free State", "town": "Trompsburg",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # LIMPOPO (6 sources)
    # =========================================================================
    {
        "name": "Polokwane Municipality",
        "url": "https://www.polokwane.gov.za/index.php/tenders",
        "province": "Limpopo", "town": "Polokwane",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Capricorn District",
        "url": "https://www.cdm.org.za/tenders",
        "province": "Limpopo", "town": "Polokwane",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Vhembe District",
        "url": "https://www.vhembe.gov.za/tenders",
        "province": "Limpopo", "town": "Thohoyandou",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Mopani District",
        "url": "https://www.mopani.gov.za/tenders",
        "province": "Limpopo", "town": "Giyani",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Waterberg District",
        "url": "https://www.waterberg.gov.za/tenders",
        "province": "Limpopo", "town": "Modimolle",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Sekhukhune District",
        "url": "https://www.sekhukhunedistrict.gov.za/tenders",
        "province": "Limpopo", "town": "Groblersdal",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # MPUMALANGA (6 sources)
    # =========================================================================
    {
        "name": "Mbombela Municipality",
        "url": "https://www.mbombela.gov.za/tenders",
        "province": "Mpumalanga", "town": "Nelspruit",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Ehlanzeni District",
        "url": "https://www.ehlanzeni.gov.za/tenders",
        "province": "Mpumalanga", "town": "Nelspruit",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Gert Sibande District",
        "url": "https://www.gertsibande.gov.za/tenders",
        "province": "Mpumalanga", "town": "Ermelo",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Nkangala District",
        "url": "https://www.nkangaladm.gov.za/tenders",
        "province": "Mpumalanga", "town": "Middelburg",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Steve Tshwete Municipality",
        "url": "https://www.stevetshwetelm.gov.za/tenders",
        "province": "Mpumalanga", "town": "Middelburg",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Govan Mbeki Municipality",
        "url": "https://www.govanmbeki.gov.za/tenders",
        "province": "Mpumalanga", "town": "Secunda",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # NORTH WEST (6 sources)
    # =========================================================================
    {
        "name": "Mahikeng Municipality",
        "url": "https://www.mahikeng.gov.za/tenders",
        "province": "North West", "town": "Mahikeng",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Rustenburg Municipality",
        "url": "https://www.rustenburg.gov.za/tenders",
        "province": "North West", "town": "Rustenburg",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Bojanala District",
        "url": "https://www.bojanala.gov.za/tenders",
        "province": "North West", "town": "Rustenburg",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Dr Kenneth Kaunda District",
        "url": "https://www.kaundadistrict.gov.za/tenders",
        "province": "North West", "town": "Klerksdorp",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Ngaka Modiri Molema District",
        "url": "https://www.nmmdm.gov.za/tenders",
        "province": "North West", "town": "Mahikeng",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Dr Ruth Segomotsi Mompati District",
        "url": "https://www.ruthsegomotsimompati.gov.za/tenders",
        "province": "North West", "town": "Vryburg",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # NORTHERN CAPE (8 sources — reduced from 20+ to balance)
    # =========================================================================
    {
        "name": "Northern Cape Provincial Government",
        "url": "https://www.ncgov.co.za/tenders",
        "province": "Northern Cape", "town": "Kimberley",
        "scrape_type": "standard", "allow_province_detection": False,
    },
    {
        "name": "Northern Cape DEDAT",
        "url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824",
        "province": "Northern Cape", "town": "Kimberley",
        "scrape_type": "phoca", "allow_province_detection": False,
    },
    {
        "name": "Sol Plaatje Municipality",
        "url": "https://www.solplaatje.org.za/tenders",
        "province": "Northern Cape", "town": "Kimberley",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "Frances Baard District",
        "url": "https://francesbaard.gov.za/tenders/",
        "province": "Northern Cape", "town": "Kimberley",
        "scrape_type": "frances_baard", "allow_province_detection": False,
    },
    {
        "name": "ZF Mgcawu District",
        "url": "https://www.zfm-dm.gov.za/documents/?dir=4302",
        "province": "Northern Cape", "town": "Upington",
        "scrape_type": "zfm_district", "allow_province_detection": False,
    },
    {
        "name": "Namakwa District",
        "url": "https://www.namakwa-dm.gov.za/request-for-tenders/",
        "province": "Northern Cape", "town": "Springbok",
        "scrape_type": "namakwa_district", "allow_province_detection": False,
    },
    {
        "name": "Pixley ka Seme District",
        "url": "https://www.pksdm.gov.za/tenders.html",
        "province": "Northern Cape", "town": "De Aar",
        "scrape_type": "links", "allow_province_detection": False,
    },
    {
        "name": "John Taolo Gaetsewe District",
        "url": "https://taologaetsewe.gov.za/request-for-quotations/",
        "province": "Northern Cape", "town": "Kuruman",
        "scrape_type": "links", "allow_province_detection": False,
    },

    # =========================================================================
    # AGGREGATORS — Nationwide Coverage
    # =========================================================================
    {
        "name": "EasyTenders",
        "url": "https://easytenders.co.za/tenders",
        "province": None, "town": None,
        "scrape_type": "js_playwright", "allow_province_detection": True,
        "notes": "⭐ ALL 9 provinces — scrapes each province page",
    },
    {
        "name": "eTenders Portal (National)",
        "url": "https://www.etenders.gov.za/Home/opportunities?id=1",
        "province": None, "town": None,
        "scrape_type": "etenders_playwright", "allow_province_detection": True,
        "notes": "⭐ Official government portal — nationwide tenders",
    },
    {
        "name": "Municipalities.co.za",
        "url": "https://municipalities.co.za/tenders",
        "province": None, "town": None,
        "scrape_type": "standard", "allow_province_detection": True,
        "notes": "Multi-province aggregator",
    },
]

# =============================================================================
# ⚠️ BROKEN SOURCES — Need fixing
# =============================================================================

BROKEN_SOURCES: List[Dict] = [
    {
        "name": "OnlineTenders (Northern Cape)",
        "url": "https://www.onlinetenders.co.za/tenders/northern-cape",
        "province": "Northern Cape", "town": None,
        "scrape_type": "js_playwright", "allow_province_detection": True,
        "notes": "Returns 0 results — needs selector debugging",
    },
    {
        "name": "sa-tenders.co.za",
        "url": "https://sa-tenders.co.za/tenders",
        "province": None, "town": None,
        "scrape_type": "js_playwright", "allow_province_detection": True,
        "notes": "Timeout issues — needs investigation",
    },
]

# =============================================================================
# ❌ DEAD SOURCES — DNS failure or site removed
# =============================================================================

DEAD_SOURCES: List[Dict] = [
    {"name": "//Khara Hais Municipality", "url": "https://www.kharahais.gov.za/tenders", "province": "Northern Cape"},
    {"name": "!Kheis Municipality", "url": "https://www.kheis.gov.za/tenders", "province": "Northern Cape"},
    {"name": "Khai-Ma Municipality", "url": "https://www.khai-ma.gov.za/tenders", "province": "Northern Cape"},
    {"name": "Nama Khoi Municipality", "url": "https://www.namakhoi.gov.za/tenders", "province": "Northern Cape"},
    {"name": "Renosterberg Municipality", "url": "https://www.renosterberg.gov.za/tenders", "province": "Northern Cape"},
    {"name": "Thembelihle Municipality", "url": "https://www.thembelihle.gov.za/tenders", "province": "Northern Cape"},
    {"name": "Tsantsabane Municipality", "url": "https://www.tsantsabane.gov.za/index.php/tenders", "province": "Northern Cape"},
    {"name": "tenderbulletins.co.za", "url": "https://tenderbulletins.co.za", "province": None},
    {"name": "tendersbulletins.co.za", "url": "https://tendersbulletins.co.za/location/northern-cape", "province": "Northern Cape"},
    {"name": "TenderAlerts", "url": "https://tenderalerts.co.za", "province": None},
]

# =============================================================================
# COMBINED VIEWS & HELPER FUNCTIONS
# =============================================================================

ALL_ACTIVE_SOURCES: List[Dict] = ACTIVE_SOURCES
ALL_SOURCES: List[Dict] = ACTIVE_SOURCES + BROKEN_SOURCES + DEAD_SOURCES


def get_by_scrape_type(scrape_type: str) -> List[Dict]:
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") == scrape_type]


def get_playwright_sources() -> List[Dict]:
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") in ("js_playwright", "etenders_playwright")]


def get_html_sources() -> List[Dict]:
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") not in ("js_playwright", "etenders_playwright")]


def get_sources_by_province(province: str) -> List[Dict]:
    return [s for s in ACTIVE_SOURCES if s.get("province") == province]


def get_aggregator_sources() -> List[Dict]:
    return [s for s in ACTIVE_SOURCES if s.get("province") is None]


def summary() -> Dict:
    return {
        "active": len(ACTIVE_SOURCES),
        "broken": len(BROKEN_SOURCES),
        "dead": len(DEAD_SOURCES),
        "total": len(ALL_SOURCES),
        "playwright": len(get_playwright_sources()),
        "html": len(get_html_sources()),
    }