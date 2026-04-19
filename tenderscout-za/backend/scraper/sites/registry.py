"""
scraper/sites/registry.py
--------------------------
SINGLE SOURCE OF TRUTH for all tender sources.
Last verified: 2026-04-18 via test_sites.py + manual URL checks

To add a site:    add to ACTIVE_SOURCES
To fix a site:    move from BROKEN_SOURCES → ACTIVE_SOURCES, update url/scrape_type
To retire a site: move to DEAD_SOURCES (keeps history, never delete)

scrape_type values:
  links                  Generic anchor-tag scraper
  phoca                  Joomla Phoca Download component
  standard               Generic with parent-element context
  siyancuma              PDF-link scraper (Siyancuma-specific)
  hantam                 Follows "View All" sub-page link
  gamagara               Structured text block parser
  dikgatlong             Title + PDF link with closing date in heading
  phokwane               WordPress category/post page
  ga_segonyana           Simple HTML table: Tender Advert | Closing Date
  dawid_kruiper          Tab-based table (Open Bids / Closed Bids)
  zfm_district           Document directory listing (PDF filenames)
  namakwa_district       Grouped-by-month link list
  kareeberg              Static .htm page with RFQ links
  js_playwright          JS-rendered site — Playwright required
  etenders_playwright    eTenders-specific Playwright scraper
"""

from typing import List, Dict

# ---------------------------------------------------------------------------
# ✅ ACTIVE — confirmed returning tenders (verified 2026-04-18)
# ---------------------------------------------------------------------------

ACTIVE_SOURCES: List[Dict] = [

    # ── Gauteng ───────────────────────────────────────────────────────────────
    {
        "name":                     "City of Tshwane",
        "url":                      "https://www.tshwane.gov.za/?page_id=2194",
        "province":                 "Gauteng",
        "town":                     "Pretoria",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~11 tenders",
    },
    {
        "name":                     "City of Ekurhuleni",
        "url":                      "https://www.ekurhuleni.gov.za/tenders",
        "province":                 "Gauteng",
        "town":                     "Ekurhuleni",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~65 tenders",
    },
    {
        "name":                     "City of Johannesburg",
        "url":                      "https://joburg.org.za/work_/TendersQuotations/Pages/Tenders.aspx",
        "province":                 "Gauteng",
        "town":                     "Johannesburg",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "SharePoint-based tender list",
    },

    # ── KwaZulu-Natal ─────────────────────────────────────────────────────────
    {
        "name":                     "eThekwini Municipality",
        "url":                      "https://www.durban.gov.za/pages/government/procurement",
        "province":                 "KwaZulu-Natal",
        "town":                     "Durban",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "Procurement page — confirmed live",
    },

    # ── Western Cape ──────────────────────────────────────────────────────────
    {
        "name":                     "City of Cape Town",
        "url":                      "https://web1.capetown.gov.za/web1/procurementportal/",
        "province":                 "Western Cape",
        "town":                     "Cape Town",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~9 tenders",
    },

    # ── Eastern Cape ──────────────────────────────────────────────────────────
    {
        "name":                     "Buffalo City Metro",
        "url":                      "https://www.buffalocity.gov.za/tenders",
        "province":                 "Eastern Cape",
        "town":                     "East London",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~7 tenders",
    },
    {
        "name":                     "Nelson Mandela Bay",
        "url":                      "https://www.nelsonmandelabay.gov.za/tenders",
        "province":                 "Eastern Cape",
        "town":                     "Gqeberha",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~6 tenders",
    },

    # ── Free State ────────────────────────────────────────────────────────────
    {
        "name":                     "Mangaung Municipality",
        "url":                      "https://www.mangaung.co.za/category/tenders-bids/",
        "province":                 "Free State",
        "town":                     "Bloemfontein",
        "scrape_type":              "phokwane",
        "allow_province_detection": False,
        "notes":                    "WordPress category page — URL fixed 2026-04-18",
    },

    # ── Northern Cape — Provincial ────────────────────────────────────────────
    {
        "name":                     "Northern Cape Provincial Government",
        "url":                      "https://www.ncgov.co.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Kimberley",
        "scrape_type":              "standard",
        "allow_province_detection": False,
        "notes":                    "~336 tenders — largest single HTML source",
    },
    {
        "name":                     "Northern Cape DEDAT",
        "url":                      "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824",
        "province":                 "Northern Cape",
        "town":                     "Kimberley",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~51 tenders — Joomla Phoca Download",
    },

    # ── Northern Cape — Frances Baard ─────────────────────────────────────────
    {
        "name":                     "Sol Plaatje Municipality",
        "url":                      "https://www.solplaatje.org.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Kimberley",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~6 tenders — site is slow (15s+), increase timeout if timing out",
    },
    {
        "name":                     "Dikgatlong Municipality",
        "url":                      "https://dikgatlong.gov.za/tenders-quotations/tenders",
        "province":                 "Northern Cape",
        "town":                     "Barkly West",
        "scrape_type":              "dikgatlong",
        "allow_province_detection": False,
        "notes":                    "Title in heading + PDF link + closing date in heading. URL fixed.",
    },
    {
        "name":                     "Magareng Municipality",
        "url":                      "https://www.magareng.gov.za/index.php/tenders-quotations/tenders",
        "province":                 "Northern Cape",
        "town":                     "Warrenton",
        "scrape_type":              "dikgatlong",
        "allow_province_detection": False,
        "notes":                    "Same structure as Dikgatlong. URL fixed.",
    },
    {
        "name":                     "Phokwane Municipality",
        "url":                      "https://phokwane.gov.za/category/tenders-quotations/",
        "province":                 "Northern Cape",
        "town":                     "Hartswater",
        "scrape_type":              "phokwane",
        "allow_province_detection": False,
        "notes":                    "WordPress category page. URL fixed.",
    },
    {
        "name":                     "Frances Baard District",
        "url":                      "https://francesbaard.gov.za/tenders/",
        "province":                 "Northern Cape",
        "town":                     "Kimberley",
        "scrape_type":              "frances_baard",
        "allow_province_detection": False,
        "notes":                    "Card layout: title + closing date + download button. URL fixed.",
    },

    # ── Northern Cape — ZF Mgcawu ─────────────────────────────────────────────
    {
        "name":                     "Dawid Kruiper Municipality",
        "url":                      "https://web.dkm.gov.za/bids",
        "province":                 "Northern Cape",
        "town":                     "Upington",
        "scrape_type":              "js_playwright",
        "allow_province_detection": False,
        "notes":                    "JS-rendered tabbed table — Playwright required. URL fixed.",
    },
    {
        "name":                     "ZF Mgcawu District",
        "url":                      "https://www.zfm-dm.gov.za/documents/?dir=4302",
        "province":                 "Northern Cape",
        "town":                     "Upington",
        "scrape_type":              "zfm_district",
        "allow_province_detection": False,
        "notes":                    "Document directory — PDF filenames are tender titles. URL fixed.",
    },
    {
        "name":                     "Kai !Garib Municipality",
        "url":                      "https://www.kaigarib.gov.za/supply-chain-management/new-tenders/",
        "province":                 "Northern Cape",
        "town":                     "Kakamas",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "URL fixed 2026-04-18",
    },

    # ── Northern Cape — Namakwa ───────────────────────────────────────────────
    {
        "name":                     "Richtersveld Municipality",
        "url":                      "https://www.richtersveld.gov.za/tenders/",
        "province":                 "Northern Cape",
        "town":                     "Port Nolloth",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~9 tenders — confirmed active",
    },
    {
        "name":                     "Hantam Municipality",
        "url":                      "https://www.hantam.gov.za/category/tender-adverts/",
        "province":                 "Northern Cape",
        "town":                     "Calvinia",
        "scrape_type":              "phokwane",
        "allow_province_detection": False,
        "notes":                    "~12 tenders — confirmed active",
    },
    {
        "name":                     "Karoo Hoogland Municipality",
        "url":                      "https://www.karoohoogland.gov.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Sutherland",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~38 tenders",
    },
    {
        "name":                     "Namakwa District",
        "url":                      "https://www.namakwa-dm.gov.za/request-for-tenders/",
        "province":                 "Northern Cape",
        "town":                     "Springbok",
        "scrape_type":              "namakwa_district",
        "allow_province_detection": False,
        "notes":                    "Grouped by month, plain link list. URL fixed.",
    },
    {
        "name":                     "Kamiesberg Municipality",
        "url":                      "https://www.kamiesberg.gov.za/?page_id=68",
        "province":                 "Northern Cape",
        "town":                     "Garies",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "URL fixed 2026-04-18",
    },
    {
        "name":                     "Kareeberg Municipality",
        "url":                      "https://kareeberg.gov.za/written_quotations_2026.htm",
        "province":                 "Northern Cape",
        "town":                     "Carnarvon",
        "scrape_type":              "kareeberg",
        "allow_province_detection": False,
        "notes":                    "Static .htm page — RFQ links list. URL fixed.",
    },

    # ── Northern Cape — Pixley ka Seme ────────────────────────────────────────
    {
        "name":                     "Siyathemba Municipality",
        "url":                      "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders",
        "province":                 "Northern Cape",
        "town":                     "Prieska",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~13 tenders",
    },
    {
        "name":                     "Siyathemba Municipality (Quotes)",
        "url":                      "https://www.siyathemba.gov.za/index.php/tenders-quotations/quotations",
        "province":                 "Northern Cape",
        "town":                     "Prieska",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~13 quotations",
    },
    {
        "name":                     "Siyancuma Municipality",
        "url":                      "https://www.siyancuma.gov.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Douglas",
        "scrape_type":              "siyancuma",
        "allow_province_detection": False,
        "notes":                    "~46 tenders — PDF link scraper",
    },
    {
        "name":                     "Ubuntu Municipality",
        "url":                      "https://www.ubuntu.gov.za/index.php/temders-quotations/temders",
        "province":                 "Northern Cape",
        "town":                     "Victoria West",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "Note: typo in URL ('temders') is intentional — that's their actual URL",
    },
    {
        "name":                     "Pixley ka Seme District",
        "url":                      "https://www.pksdm.gov.za/tenders.html",
        "province":                 "Northern Cape",
        "town":                     "De Aar",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "URL fixed 2026-04-18",
    },

    # ── Northern Cape — John Taolo Gaetsewe ───────────────────────────────────
    {
        "name":                     "Gamagara Municipality",
        "url":                      "https://www.gamagara.gov.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Kathu",
        "scrape_type":              "gamagara",
        "allow_province_detection": False,
        "notes":                    "~6 tenders — structured text parser",
    },
    {
        "name":                     "Ga-Segonyana Municipality",
        "url":                      "https://ga-segonyana.gov.za/Tenders.html",
        "province":                 "Northern Cape",
        "town":                     "Kuruman",
        "scrape_type":              "ga_segonyana",
        "allow_province_detection": False,
        "notes":                    "Simple HTML table: Tender Advert | Closing Date. URL fixed.",
    },
    {
        "name":                     "Joe Morolong Municipality",
        "url":                      "http://www.joemorolong.gov.za/Tenders.htm",
        "province":                 "Northern Cape",
        "town":                     "Kuruman",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "URL fixed 2026-04-18",
    },
    {
        "name":                     "John Taolo Gaetsewe District",
        "url":                      "https://taologaetsewe.gov.za/request-for-quotations/",
        "province":                 "Northern Cape",
        "town":                     "Kuruman",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "URL fixed 2026-04-18",
    },

    {
        "name":                     "Umsobomvu Municipality",
        "url":                      "https://www.umsobomvumun.co.za/index.php?option=com_docman&task=cat_view&gid=98&Itemid=53",
        "province":                 "Northern Cape",
        "town":                     "Colesberg",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~7 tenders — confirmed active 2026-04-18",
    },
    {
        "name":                     "Emthanjeni Municipality",
        "url":                      "https://www.emthanjeni.co.za/index.php?option=com_docman&Itemid=160",
        "province":                 "Northern Cape",
        "town":                     "De Aar",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~3 tenders — confirmed active 2026-04-18",
    },

        # ── Aggregators ───────────────────────────────────────────────────────────
    {
        "name":                     "Municipalities.co.za (Northern Cape)",
        "url":                      "https://municipalities.co.za/tenders/index/7/northern-cape",
        "province":                 "Northern Cape",
        "town":                     None,
        "scrape_type":              "standard",
        "allow_province_detection": True,
        "notes":                    "~69 tenders — multi-municipality aggregator",
    },
    {
        "name":                     "EasyTenders (Northern Cape)",
        "url":                      "https://easytenders.co.za/tenders",
        "province":                 "Northern Cape",
        "town":                     None,
        "scrape_type":              "js_playwright",
        "allow_province_detection": True,
        "notes":                    "~50 tenders — JS-rendered, Playwright required",
        "query_params":             {"province": "northern-cape"},
    },
    {
        "name":                     "eTenders Portal (National)",
        "url":                      "https://www.etenders.gov.za/Home/opportunities?id=1",
        "province":                 None,
        "town":                     None,
        "scrape_type":              "etenders_playwright",
        "allow_province_detection": True,
        "notes":                    "National portal — province from detail panel. Playwright required.",
    },
    {
        "name":                     "sa-tenders.co.za",
        "url":                      "https://sa-tenders.co.za/tenders/",
        "province":                 None,
        "town":                     None,
        "scrape_type":              "js_playwright",
        "allow_province_detection": True,
        "notes":                    "Multi-province aggregator — Playwright required",
    },
]


# ---------------------------------------------------------------------------
# ⚠️  BROKEN — still need fixing
# ---------------------------------------------------------------------------

BROKEN_SOURCES: List[Dict] = [
    {
        "name": "Tsantsabane Municipality",
        "url":  "https://www.tsantsabane.gov.za/index.php/tenders",
        "province": "Northern Cape", "town": "Postmasburg",
        "scrape_type": "phoca", "allow_province_detection": False,
        "notes": "HTTP 404 — correct URL not yet found",
    },

]


# ---------------------------------------------------------------------------
# ❌ DEAD — DNS failure, no working URL found (verified 2026-04-18)
# ---------------------------------------------------------------------------

DEAD_SOURCES: List[Dict] = [
    {"name": "//Khara Hais Municipality",    "url": "https://www.kharahais.gov.za/tenders",              "province": "Northern Cape", "town": "Upington",     "notes": "Timeout — no alternative found"},
    {"name": "!Kheis Municipality",          "url": "https://www.tenderflow.co.za/institutions/kheis-local-municipality-nc084", "province": "Northern Cape", "town": "Groblershoop", "notes": "DNS failure on own domain — tenderflow link only"},
    {"name": "Khai-Ma Municipality",         "url": "https://www.khai-ma.gov.za/tenders",               "province": "Northern Cape", "town": "Pofadder",     "notes": "DNS failure — no alternative found"},
    {"name": "Nama Khoi Municipality",       "url": "https://www.namakhoi.gov.za/tenders",              "province": "Northern Cape", "town": "Springbok",    "notes": "HTTP 404 — no working URL found"},
    {"name": "Renosterberg Municipality",    "url": "https://www.renosterberg.gov.za/tenders",          "province": "Northern Cape", "town": "Petrusville",  "notes": "DNS failure — no alternative found"},
    {"name": "Thembelihle Municipality",     "url": "https://www.thembelihle.gov.za/tenders",           "province": "Northern Cape", "town": "Hopetown",     "notes": "DNS failure — no alternative found"},
]


# ---------------------------------------------------------------------------
# Combined views
# ---------------------------------------------------------------------------

ALL_ACTIVE_SOURCES: List[Dict] = ACTIVE_SOURCES
ALL_SOURCES:        List[Dict] = ACTIVE_SOURCES + BROKEN_SOURCES + DEAD_SOURCES


def get_by_scrape_type(scrape_type: str) -> List[Dict]:
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") == scrape_type]


def get_playwright_sources() -> List[Dict]:
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") in ("js_playwright", "etenders_playwright")]


def get_html_sources() -> List[Dict]:
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") not in ("js_playwright", "etenders_playwright")]


def summary() -> Dict:
    return {
        "active":  len(ACTIVE_SOURCES),
        "broken":  len(BROKEN_SOURCES),
        "dead":    len(DEAD_SOURCES),
        "total":   len(ALL_SOURCES),
    }