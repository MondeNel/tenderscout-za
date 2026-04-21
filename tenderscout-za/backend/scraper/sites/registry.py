"""
scraper/sites/registry.py
==========================
SINGLE SOURCE OF TRUTH for all tender sources.
Last verified: 2026-04-21 via test_all_scrapers.py

This file centralizes ALL website configurations. The orchestrator reads from
this registry to know what to scrape. Individual scraper files (city_portals.py,
js_scraper.py, etc.) may contain their own configs for backward compatibility,
but this registry should be considered authoritative.

CATEGORIES:
    ACTIVE_SOURCES  — Confirmed working, scraped daily
    BROKEN_SOURCES  — Need fixing (moved from ACTIVE when they break)
    DEAD_SOURCES    — DNS failure, site removed, or no working URL (never delete)

SCRAPE TYPES (mapped to handler functions in dispatcher):
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
    js_playwright       JS-rendered site — Playwright required (js_scraper.py)
    etenders_playwright eTenders-specific Playwright scraper (etenders.py)

To add a site:    add to ACTIVE_SOURCES
To fix a site:    move from BROKEN_SOURCES → ACTIVE_SOURCES, update url/scrape_type
To retire a site: move to DEAD_SOURCES (keeps history, never delete)
"""

from typing import List, Dict

# =============================================================================
# ✅ ACTIVE SOURCES — Confirmed returning tenders
# =============================================================================
# These are scraped daily. Last verification: 2026-04-21 via test_all_scrapers.py
# =============================================================================

ACTIVE_SOURCES: List[Dict] = [

    # =========================================================================
    # GAUTENG — Major Metropolitan Municipalities
    # =========================================================================
    {
        "name":                     "City of Tshwane",
        "url":                      "https://www.tshwane.gov.za/?page_id=2194",
        "province":                 "Gauteng",
        "town":                     "Pretoria",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~11 tenders — confirmed active",
    },
    {
        "name":                     "City of Ekurhuleni",
        "url":                      "https://www.ekurhuleni.gov.za/tenders",
        "province":                 "Gauteng",
        "town":                     "Ekurhuleni",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~46 tenders — confirmed active",
    },
    {
        "name":                     "City of Johannesburg",
        "url":                      "https://joburg.org.za/work_/TendersQuotations/Pages/Tenders.aspx",
        "province":                 "Gauteng",
        "town":                     "Johannesburg",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "SharePoint-based tender list — may need Playwright",
    },

    # =========================================================================
    # KWAZULU-NATAL
    # =========================================================================
    {
        "name":                     "eThekwini Municipality",
        "url":                      "https://www.durban.gov.za/pages/government/procurement",
        "province":                 "KwaZulu-Natal",
        "town":                     "Durban",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "Procurement page — confirmed live",
    },

    # =========================================================================
    # WESTERN CAPE
    # =========================================================================
    {
        "name":                     "City of Cape Town",
        "url":                      "https://web1.capetown.gov.za/web1/procurementportal/",
        "province":                 "Western Cape",
        "town":                     "Cape Town",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~4 tenders — confirmed active",
    },

    # =========================================================================
    # EASTERN CAPE — Metropolitan & District
    # =========================================================================
    {
        "name":                     "Buffalo City Metro",
        "url":                      "https://www.buffalocity.gov.za/tenders",
        "province":                 "Eastern Cape",
        "town":                     "East London",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~5 tenders — confirmed active",
    },
    {
        "name":                     "Nelson Mandela Bay",
        "url":                      "https://www.nelsonmandelabay.gov.za/tenders",
        "province":                 "Eastern Cape",
        "town":                     "Gqeberha",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~6 tenders — confirmed active",
    },

    # =========================================================================
    # EASTERN CAPE — Additional Local Municipalities
    # =========================================================================
    # (Keeping all your Eastern Cape sources — they're working and provide good coverage)
    {
        "name":                     "Matatiele Local Municipality",
        "url":                      "https://www.matatiele.gov.za/tenders/",
        "province":                 "Eastern Cape", "town": "Matatiele",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Ntabankulu Local Municipality",
        "url":                      "https://www.ntabankulu.gov.za/category/tenders/open-tenders/",
        "province":                 "Eastern Cape", "town": "Ntabankulu",
        "scrape_type":              "phokwane", "allow_province_detection": False,
        "notes":                    "WordPress category page",
    },
    {
        "name":                     "Umzimvubu Local Municipality",
        "url":                      "https://www.umzimvubu.gov.za/rfq-adverts/",
        "province":                 "Eastern Cape", "town": "Mount Frere",
        "scrape_type":              "phokwane", "allow_province_detection": False,
        "notes":                    "WordPress RFQ adverts page",
    },
    {
        "name":                     "Winnie Madikizela-Mandela Municipality",
        "url":                      "https://www.winniemmlm.gov.za/tenders/",
        "province":                 "Eastern Cape", "town": "Bizana",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Amahlathi Local Municipality",
        "url":                      "https://amahlathi.gov.za/tenders-rfqs/",
        "province":                 "Eastern Cape", "town": "Stutterheim",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Great Kei Local Municipality",
        "url":                      "https://greatkeilm.gov.za/web/category/tenders/open-tenders/",
        "province":                 "Eastern Cape", "town": "Komani",
        "scrape_type":              "phokwane", "allow_province_detection": False,
        "notes":                    "WordPress category page",
    },
    {
        "name":                     "Mbhashe Local Municipality",
        "url":                      "https://www.mbhashemun.gov.za/procurement/tenders/",
        "province":                 "Eastern Cape", "town": "Dutywa",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Mnquma Local Municipality",
        "url":                      "https://www.mnquma.gov.za/notices/",
        "province":                 "Eastern Cape", "town": "Butterworth",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Notices page includes tenders",
    },
    {
        "name":                     "Ngqushwa Local Municipality",
        "url":                      "https://ngqushwamun.gov.za/procurements/tenders/",
        "province":                 "Eastern Cape", "town": "Peddie",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Raymond Mhlaba Local Municipality",
        "url":                      "https://www.raymondmhlaba.gov.za/documents/tenders/current",
        "province":                 "Eastern Cape", "town": "Fort Beaufort",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Current tenders documents page",
    },
    {
        "name":                     "Dr AB Xuma Local Municipality",
        "url":                      "https://drabxumalm.gov.za/tenders/",
        "province":                 "Eastern Cape", "town": "Dordrecht",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Emalahleni Local Municipality",
        "url":                      "https://www.emalahlenilm.gov.za/current-tenders/",
        "province":                 "Eastern Cape", "town": "Lady Frere",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Enoch Mgijima Local Municipality",
        "url":                      "https://www.enochmgijima.gov.za/supply-chain/",
        "province":                 "Eastern Cape", "town": "Queenstown",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Supply chain page",
    },
    {
        "name":                     "Inxuba Yethemba Municipality",
        "url":                      "https://iym.gov.za/index.php/notices/tender-advertisements/",
        "province":                 "Eastern Cape", "town": "Cradock",
        "scrape_type":              "phokwane", "allow_province_detection": False,
        "notes":                    "WordPress tender advertisements",
    },
    {
        "name":                     "Sakhisizwe Local Municipality",
        "url":                      "https://www.slm.gov.za/supply-chain-management/tenders/",
        "province":                 "Eastern Cape", "town": "Elliot",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Elundini Local Municipality (RFQs)",
        "url":                      "https://www.elundini.gov.za/category/supplychain/rfqs/",
        "province":                 "Eastern Cape", "town": "Maclear",
        "scrape_type":              "phokwane", "allow_province_detection": False,
        "notes":                    "WordPress RFQ category",
    },
    {
        "name":                     "Elundini Local Municipality (Tenders)",
        "url":                      "https://www.elundini.gov.za/category/supplychain/tenders/",
        "province":                 "Eastern Cape", "town": "Maclear",
        "scrape_type":              "phokwane", "allow_province_detection": False,
        "notes":                    "WordPress tender category",
    },
    {
        "name":                     "Senqu Local Municipality",
        "url":                      "https://senqu.gov.za/formal-tenders-2025-2026/",
        "province":                 "Eastern Cape", "town": "Sterkspruit",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "2025/2026 formal tenders page",
    },
    {
        "name":                     "Joe Gqabi District Municipality",
        "url":                      "https://jgdm.gov.za/tenders/tender-quotation-advertisements/",
        "province":                 "Eastern Cape", "town": "Aliwal North",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Inkwanca Local Municipality",
        "url":                      "https://www.ihlm.gov.za/tenders/",
        "province":                 "Eastern Cape", "town": "Molteno",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "King Sabata Dalindyebo Municipality",
        "url":                      "https://ksd.gov.za/procurements/tenders/",
        "province":                 "Eastern Cape", "town": "Mthatha",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Mhlontlo Local Municipality",
        "url":                      "https://mhlontlolm.gov.za/current-tenders/",
        "province":                 "Eastern Cape", "town": "Tsolo",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Nyandeni Local Municipality",
        "url":                      "https://www.nyandenilm.gov.za/tenders-index",
        "province":                 "Eastern Cape", "town": "Ngqeleni",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Port St Johns Municipality",
        "url":                      "https://psjmunicipality.gov.za/za/procurement/tender-adverts/",
        "province":                 "Eastern Cape", "town": "Port St Johns",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Blue Crane Route Municipality",
        "url":                      "https://www.bcrm.gov.za/index.php/Documents/11",
        "province":                 "Eastern Cape", "town": "Somerset East",
        "scrape_type":              "phoca", "allow_province_detection": False,
        "notes":                    "Joomla documents page",
    },
    {
        "name":                     "Kouga Local Municipality",
        "url":                      "https://www.kouga.gov.za/tenders/status/open",
        "province":                 "Eastern Cape", "town": "Jeffreys Bay",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Open tenders filtered page",
    },
    {
        "name":                     "Koukamma Local Municipality",
        "url":                      "https://www.koukammamunicipality.gov.za/tenders-and-rfq/",
        "province":                 "Eastern Cape", "town": "Kareedouw",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Makana Local Municipality",
        "url":                      "https://www.makana.gov.za/category/tenders/",
        "province":                 "Eastern Cape", "town": "Makhanda",
        "scrape_type":              "phokwane", "allow_province_detection": False,
        "notes":                    "WordPress category page",
    },
    {
        "name":                     "Ndlambe Local Municipality",
        "url":                      "https://www.ndlambe.gov.za/quotations-and-tenders/",
        "province":                 "Eastern Cape", "town": "Port Alfred",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },
    {
        "name":                     "Sunday's River Valley Municipality",
        "url":                      "https://www.srvm.gov.za/tenders/",
        "province":                 "Eastern Cape", "town": "Kirkwood",
        "scrape_type":              "links", "allow_province_detection": False,
        "notes":                    "Added 2026-04-19",
    },

    # =========================================================================
    # FREE STATE
    # =========================================================================
    {
        "name":                     "Mangaung Municipality",
        "url":                      "https://www.mangaung.co.za/category/tenders-bids/",
        "province":                 "Free State",
        "town":                     "Bloemfontein",
        "scrape_type":              "phokwane",
        "allow_province_detection": False,
        "notes":                    "WordPress category page — URL fixed 2026-04-18",
    },

    # =========================================================================
    # NORTHERN CAPE — Provincial Government
    # =========================================================================
    {
        "name":                     "Northern Cape Provincial Government",
        "url":                      "https://www.ncgov.co.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Kimberley",
        "scrape_type":              "standard",
        "allow_province_detection": False,
        "notes":                    "~334 tenders — largest single HTML source",
    },
    {
        "name":                     "Northern Cape DEDAT",
        "url":                      "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824",
        "province":                 "Northern Cape",
        "town":                     "Kimberley",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "Joomla Phoca Download",
    },

    # =========================================================================
    # NORTHERN CAPE — Frances Baard District
    # =========================================================================
    {
        "name":                     "Sol Plaatje Municipality",
        "url":                      "https://www.solplaatje.org.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Kimberley",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "Site is slow (15s+) — increase timeout",
    },
    {
        "name":                     "Dikgatlong Municipality",
        "url":                      "https://dikgatlong.gov.za/tenders-quotations/tenders",
        "province":                 "Northern Cape",
        "town":                     "Barkly West",
        "scrape_type":              "dikgatlong",
        "allow_province_detection": False,
        "notes":                    "~244 tenders — largest municipal source",
    },
    {
        "name":                     "Magareng Municipality",
        "url":                      "https://www.magareng.gov.za/index.php/tenders-quotations/tenders",
        "province":                 "Northern Cape",
        "town":                     "Warrenton",
        "scrape_type":              "dikgatlong",
        "allow_province_detection": False,
        "notes":                    "Same structure as Dikgatlong",
    },
    {
        "name":                     "Phokwane Municipality",
        "url":                      "https://phokwane.gov.za/category/tenders-quotations/",
        "province":                 "Northern Cape",
        "town":                     "Hartswater",
        "scrape_type":              "phokwane",
        "allow_province_detection": False,
        "notes":                    "WordPress category page",
    },
    {
        "name":                     "Frances Baard District",
        "url":                      "https://francesbaard.gov.za/tenders/",
        "province":                 "Northern Cape",
        "town":                     "Kimberley",
        "scrape_type":              "frances_baard",
        "allow_province_detection": False,
        "notes":                    "Card layout: title + closing date + download button",
    },

    # =========================================================================
    # NORTHERN CAPE — ZF Mgcawu District
    # =========================================================================
    {
        "name":                     "Dawid Kruiper Municipality",
        "url":                      "https://web.dkm.gov.za/bids",
        "province":                 "Northern Cape",
        "town":                     "Upington",
        "scrape_type":              "js_playwright",
        "allow_province_detection": False,
        "notes":                    "JS-rendered tabbed table — Playwright required",
    },
    {
        "name":                     "ZF Mgcawu District",
        "url":                      "https://www.zfm-dm.gov.za/documents/?dir=4302",
        "province":                 "Northern Cape",
        "town":                     "Upington",
        "scrape_type":              "zfm_district",
        "allow_province_detection": False,
        "notes":                    "Document directory — PDF filenames are tender titles",
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

    # =========================================================================
    # NORTHERN CAPE — Namakwa District
    # =========================================================================
    {
        "name":                     "Richtersveld Municipality",
        "url":                      "https://www.richtersveld.gov.za/tenders/",
        "province":                 "Northern Cape",
        "town":                     "Port Nolloth",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "~7 tenders — confirmed active",
    },
    {
        "name":                     "Hantam Municipality",
        "url":                      "https://www.hantam.gov.za/category/tender-adverts/",
        "province":                 "Northern Cape",
        "town":                     "Calvinia",
        "scrape_type":              "phokwane",
        "allow_province_detection": False,
        "notes":                    "Confirmed active",
    },
    {
        "name":                     "Karoo Hoogland Municipality",
        "url":                      "https://www.karoohoogland.gov.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Sutherland",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~4 tenders — confirmed active",
    },
    {
        "name":                     "Namakwa District",
        "url":                      "https://www.namakwa-dm.gov.za/request-for-tenders/",
        "province":                 "Northern Cape",
        "town":                     "Springbok",
        "scrape_type":              "namakwa_district",
        "allow_province_detection": False,
        "notes":                    "Grouped by month, plain link list",
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
        "notes":                    "Static .htm page — RFQ links list",
    },

    # =========================================================================
    # NORTHERN CAPE — Pixley ka Seme District
    # =========================================================================
    {
        "name":                     "Siyathemba Municipality",
        "url":                      "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders",
        "province":                 "Northern Cape",
        "town":                     "Prieska",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~14 tenders — confirmed active",
    },
    {
        "name":                     "Siyathemba Municipality (Quotes)",
        "url":                      "https://www.siyathemba.gov.za/index.php/tenders-quotations/quotations",
        "province":                 "Northern Cape",
        "town":                     "Prieska",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "Quotations page",
    },
    {
        "name":                     "Siyancuma Municipality",
        "url":                      "https://www.siyancuma.gov.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Douglas",
        "scrape_type":              "siyancuma",
        "allow_province_detection": False,
        "notes":                    "~36 tenders — PDF link scraper",
    },
    {
        "name":                     "Ubuntu Municipality",
        "url":                      "https://www.ubuntu.gov.za/index.php/temders-quotations/temders",
        "province":                 "Northern Cape",
        "town":                     "Victoria West",
        "scrape_type":              "links",
        "allow_province_detection": False,
        "notes":                    "Note: typo in URL ('temders') is intentional",
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

    # =========================================================================
    # NORTHERN CAPE — John Taolo Gaetsewe District
    # =========================================================================
    {
        "name":                     "Gamagara Municipality",
        "url":                      "https://www.gamagara.gov.za/tenders",
        "province":                 "Northern Cape",
        "town":                     "Kathu",
        "scrape_type":              "gamagara",
        "allow_province_detection": False,
        "notes":                    "~1 tender — structured text parser",
    },
    {
        "name":                     "Ga-Segonyana Municipality",
        "url":                      "https://ga-segonyana.gov.za/Tenders.html",
        "province":                 "Northern Cape",
        "town":                     "Kuruman",
        "scrape_type":              "ga_segonyana",
        "allow_province_detection": False,
        "notes":                    "Simple HTML table: Tender Advert | Closing Date",
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
        "notes":                    "~7 tenders — confirmed active",
    },
    {
        "name":                     "Emthanjeni Municipality",
        "url":                      "https://www.emthanjeni.co.za/index.php?option=com_docman&Itemid=160",
        "province":                 "Northern Cape",
        "town":                     "De Aar",
        "scrape_type":              "phoca",
        "allow_province_detection": False,
        "notes":                    "~4 tenders — confirmed active",
    },

    # =========================================================================
    # AGGREGATORS — Nationwide Coverage
    # =========================================================================
    # These are your MOST IMPORTANT sources for nationwide tender coverage.
    # They aggregate tenders from multiple government sources.
    # =========================================================================
    {
        "name":                     "Municipalities.co.za (Northern Cape)",
        "url":                      "https://municipalities.co.za/tenders/index/7/northern-cape",
        "province":                 "Northern Cape",
        "town":                     None,
        "scrape_type":              "standard",
        "allow_province_detection": True,
        "notes":                    "~55 tenders — multi-municipality aggregator",
    },
    {
        "name":                     "EasyTenders",
        "url":                      "https://easytenders.co.za/tenders",
        "province":                 None,
        "town":                     None,
        "scrape_type":              "js_playwright",
        "allow_province_detection": True,
        "notes":                    "⭐ ALL 9 provinces — scrapes each province page. ~52+ tenders per province.",
    },
    {
        "name":                     "eTenders Portal (National)",
        "url":                      "https://www.etenders.gov.za/Home/opportunities?id=1",
        "province":                 None,
        "town":                     None,
        "scrape_type":              "etenders_playwright",
        "allow_province_detection": True,
        "notes":                    "⭐ Official government portal — nationwide tenders. Province from detail panel.",
    },
    {
        "name":                     "sa-tenders.co.za",
        "url":                      "https://sa-tenders.co.za/tenders",
        "province":                 None,
        "town":                     None,
        "scrape_type":              "js_playwright",
        "allow_province_detection": True,
        "notes":                    "Multi-province aggregator — Playwright required. Currently returns 0 results — needs debugging.",
    },
    # Add these entries to ACTIVE_SOURCES in registry.py

    # =========================================================================
    # ADDITIONAL AGGREGATORS (from sa_tenders.py)
    # =========================================================================
    {
        "name":                     "OnlineTenders (Northern Cape)",
        "url":                      "https://www.onlinetenders.co.za/tenders/northern-cape",
        "province":                 "Northern Cape",
        "town":                     None,
        "scrape_type":              "js_playwright",  # Try Playwright first
        "allow_province_detection": True,
        "notes":                    "Currently returns 0 — needs selector debugging",
    },
    {
        "name":                     "TenderAlerts",
        "url":                      "https://tenderalerts.co.za",
        "province":                 None,
        "town":                     None,
        "scrape_type":              "standard",
        "allow_province_detection": True,
        "notes":                    "Currently returns 0 — needs selector debugging",
    },
    
    # =========================================================================
    # TENDER BULLETINS (from tender_bulletins.py)
    # =========================================================================
    {
        "name":                     "tenderbulletins.co.za",
        "url":                      "https://tenderbulletins.co.za",
        "province":                 None,
        "town":                     None,
        "scrape_type":              "js_playwright",  # 403 with httpx — use Playwright
        "allow_province_detection": True,
        "notes":                    "Returns 403 with httpx — needs Playwright",
    },
    
    # -------------------------------------------------------------------------
    # TODO: Add these sources once debugged
    # -------------------------------------------------------------------------
    # {
    #     "name":                     "OnlineTenders (Northern Cape)",
    #     "url":                      "https://www.onlinetenders.co.za/tenders/northern-cape",
    #     "province":                 "Northern Cape",
    #     "town":                     None,
    #     "scrape_type":              "js_playwright",
    #     "allow_province_detection": True,
    #     "notes":                    "Currently returns 0 results — needs selector updates",
    # },
    # {
    #     "name":                     "TenderAlerts",
    #     "url":                      "https://tenderalerts.co.za",
    #     "province":                 None,
    #     "town":                     None,
    #     "scrape_type":              "standard",
    #     "allow_province_detection": True,
    #     "notes":                    "Currently returns 0 results — needs selector updates",
    # },
    # {
    #     "name":                     "tenderbulletins.co.za",
    #     "url":                      "https://tenderbulletins.co.za",
    #     "province":                 None,
    #     "town":                     None,
    #     "scrape_type":              "js_playwright",  # 403 Forbidden with httpx
    #     "allow_province_detection": True,
    #     "notes":                    "Returns 403 — needs Playwright or better headers",
    # },
]


# =============================================================================
# ⚠️ BROKEN SOURCES — Need fixing
# =============================================================================
# These were in ACTIVE but are currently not returning data.
# Fix and move back to ACTIVE_SOURCES.
# =============================================================================

BROKEN_SOURCES: List[Dict] = [
    {
        "name": "Tsantsabane Municipality",
        "url":  "https://www.tsantsabane.gov.za/index.php/tenders",
        "province": "Northern Cape", "town": "Postmasburg",
        "scrape_type": "phoca", "allow_province_detection": False,
        "notes": "HTTP 404 — correct URL not yet found",
    },
]


# =============================================================================
# ❌ DEAD SOURCES — DNS failure, site removed, or no working URL
# =============================================================================
# Never delete — keep for historical reference to avoid re-adding broken URLs.
# =============================================================================

DEAD_SOURCES: List[Dict] = [
    {"name": "//Khara Hais Municipality",    "url": "https://www.kharahais.gov.za/tenders",              "province": "Northern Cape", "town": "Upington",     "notes": "Timeout — no alternative found"},
    {"name": "!Kheis Municipality",          "url": "https://www.tenderflow.co.za/institutions/kheis-local-municipality-nc084", "province": "Northern Cape", "town": "Groblershoop", "notes": "DNS failure on own domain — tenderflow link only"},
    {"name": "Khai-Ma Municipality",         "url": "https://www.khai-ma.gov.za/tenders",               "province": "Northern Cape", "town": "Pofadder",     "notes": "DNS failure — no alternative found"},
    {"name": "Nama Khoi Municipality",       "url": "https://www.namakhoi.gov.za/tenders",              "province": "Northern Cape", "town": "Springbok",    "notes": "HTTP 404 — no working URL found"},
    {"name": "Renosterberg Municipality",    "url": "https://www.renosterberg.gov.za/tenders",          "province": "Northern Cape", "town": "Petrusville",  "notes": "DNS failure — no alternative found"},
    {"name": "Thembelihle Municipality",     "url": "https://www.thembelihle.gov.za/tenders",           "province": "Northern Cape", "town": "Hopetown",     "notes": "DNS failure — no alternative found"},
    {"name": "tendersbulletins.co.za (Northern Cape)", "url": "https://tendersbulletins.co.za/location/northern-cape", "province": "Northern Cape", "town": None, "notes": "DNS failure — domain may be defunct"},
]


# =============================================================================
# COMBINED VIEWS
# =============================================================================

ALL_ACTIVE_SOURCES: List[Dict] = ACTIVE_SOURCES
ALL_SOURCES:        List[Dict] = ACTIVE_SOURCES + BROKEN_SOURCES + DEAD_SOURCES


# =============================================================================
# FILTER FUNCTIONS
# =============================================================================

def get_by_scrape_type(scrape_type: str) -> List[Dict]:
    """
    Get all active sources with a specific scrape_type.
    
    Args:
        scrape_type: e.g., "links", "js_playwright", "etenders_playwright"
        
    Returns:
        List of source configurations
    """
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") == scrape_type]


def get_playwright_sources() -> List[Dict]:
    """
    Get all sources that require Playwright (JavaScript rendering).
    
    Returns:
        List of sources with scrape_type "js_playwright" or "etenders_playwright"
    """
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") in ("js_playwright", "etenders_playwright")]


def get_html_sources() -> List[Dict]:
    """
    Get all sources that can be scraped with httpx + BeautifulSoup.
    
    Returns:
        List of sources NOT requiring Playwright
    """
    return [s for s in ACTIVE_SOURCES if s.get("scrape_type") not in ("js_playwright", "etenders_playwright")]


def get_sources_by_province(province: str) -> List[Dict]:
    """
    Get all active sources for a specific province.
    
    Args:
        province: e.g., "Gauteng", "Western Cape", "Northern Cape"
        
    Returns:
        List of source configurations for that province
    """
    return [s for s in ACTIVE_SOURCES if s.get("province") == province]


def get_aggregator_sources() -> List[Dict]:
    """
    Get all aggregator sources (nationwide coverage).
    
    Returns:
        List of sources where province is None (meaning multi-province)
    """
    return [s for s in ACTIVE_SOURCES if s.get("province") is None]


def summary() -> Dict:
    """
    Get summary statistics about the source registry.
    
    Returns:
        Dictionary with counts: active, broken, dead, total
    """
    return {
        "active":  len(ACTIVE_SOURCES),
        "broken":  len(BROKEN_SOURCES),
        "dead":    len(DEAD_SOURCES),
        "total":   len(ALL_SOURCES),
        "playwright": len(get_playwright_sources()),
        "html": len(get_html_sources()),
    }