"""
scripts/discover_tenders.py
----------------------------
Given a list of municipality website URLs, automatically finds the correct
tender/bid/RFQ page URL and suggests the right scrape_type.

Usage:
    cd backend
    python scripts/discover_tenders.py --urls https://www.somemunicipality.gov.za
    python scripts/discover_tenders.py --file urls.txt
    python scripts/discover_tenders.py --province "Limpopo"   # uses built-in list

Output: ready-to-paste registry.py entries for every URL discovered.
"""

import asyncio
import sys
import os
import argparse
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import httpx
from bs4 import BeautifulSoup
from scraper.utils import get_headers

# Common tender page path patterns — tried in order on each site
TENDER_PATH_CANDIDATES = [
    "/tenders", "/tenders/", "/tenders/open", "/tenders/status/open",
    "/tender", "/tender/",
    "/bids", "/bids/",
    "/rfq", "/rfqs", "/rfq-adverts", "/rfq-adverts/",
    "/quotations", "/quotations-and-tenders", "/quotations-and-tenders/",
    "/procurement", "/procurement/", "/procurement/tenders", "/procurement/tenders/",
    "/supply-chain", "/supply-chain/", "/supply-chain-management",
    "/supply-chain-management/tenders", "/supply-chain-management/tenders/",
    "/scm", "/scm/tenders",
    "/notices/tender-advertisements", "/notices/tender-advertisements/",
    "/category/tenders", "/category/tenders/", "/category/tenders/open-tenders/",
    "/category/tenders-rfqs", "/category/tenders-rfqs/",
    "/category/supplychain/tenders", "/category/supplychain/tenders/",
    "/documents/tenders/current", "/documents/tenders",
    "/current-tenders", "/current-tenders/",
    "/open-tenders", "/open-tenders/",
    "/formal-tenders-2025-2026", "/formal-tenders",
    "/tender-quotation-advertisements",
    "/index.php/notices/tender-advertisements",
    "/index.php/tenders",
    "/procurements/tenders", "/procurements/tenders/",
]

# Keywords that indicate a tender page
TENDER_PAGE_KEYWORDS = [
    "tender", "bid", "rfq", "quotation", "procurement", "supply chain",
    "scm", "bidding", "request for proposal",
]

# Nav link text that typically leads to tender pages
TENDER_NAV_KEYWORDS = [
    "tender", "tenders", "bid", "bids", "rfq", "rfqs", "quotation",
    "procurement", "supply chain", "scm", "notices",
]


def detect_scrape_type(url: str, html: str) -> str:
    """Guess the best scrape_type from the page content."""
    soup = BeautifulSoup(html, "lxml")

    # Check for Joomla Phoca Download
    if soup.select("div.phocadownload, span.phocadownload"):
        return "phoca"
    if "com_phocadownload" in url:
        return "phoca"
    if "option=com_docman" in url:
        return "phoca"

    # Check for WordPress category/post pages
    if soup.select("article.post, article.category, .jeg_post, div.type-post"):
        return "phokwane"
    if "/category/" in url:
        return "phokwane"

    # Table with Tender Advert | Closing Date columns
    for tbl in soup.select("table"):
        header = tbl.select_one("thead tr, tr:first-child")
        if header:
            txt = header.get_text().lower()
            if "closing" in txt and ("tender" in txt or "advert" in txt or "description" in txt):
                return "ga_segonyana"

    # Document directory listing
    if soup.select("a[href*='.pdf']") and len(soup.select("table")) == 0:
        pdfs = soup.select("a[href*='.pdf']")
        if len(pdfs) > 3:
            return "zfm_district"

    # Default
    return "links"


async def check_url(client: httpx.AsyncClient, url: str) -> tuple[bool, int, str]:
    """Check if URL returns a valid tender page."""
    try:
        r = await client.get(url, timeout=10)
        if r.status_code != 200:
            return False, r.status_code, ""
        html = r.text.lower()
        has_tender = any(kw in html for kw in TENDER_PAGE_KEYWORDS)
        return has_tender, r.status_code, r.text
    except Exception:
        return False, 0, ""


async def find_tender_links_on_homepage(
    client: httpx.AsyncClient, base_url: str
) -> list[str]:
    """Scrape the homepage and find links that likely lead to tender pages."""
    candidates = []
    try:
        r = await client.get(base_url, timeout=10)
        if r.status_code != 200:
            return candidates
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a[href]"):
            text = a.get_text().strip().lower()
            href = a.get("href", "")
            if any(kw in text for kw in TENDER_NAV_KEYWORDS):
                full = href if href.startswith("http") else urljoin(base_url, href)
                if urlparse(full).netloc == urlparse(base_url).netloc:
                    candidates.append(full)
    except Exception:
        pass
    return list(dict.fromkeys(candidates))  # deduplicate preserving order


async def discover_site(
    client: httpx.AsyncClient, base_url: str
) -> Optional[dict]:
    """
    For a given municipality base URL, find the tender page URL and scrape type.
    Returns a dict with url, scrape_type, tender_count estimate, or None if not found.
    """
    # Normalise base URL
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    base_url = base_url.rstrip("/")
    domain   = urlparse(base_url).netloc

    print(f"  🔍 {domain}")

    # 1. Try common path candidates
    for path in TENDER_PATH_CANDIDATES:
        url = base_url + path
        found, status, html = await check_url(client, url)
        if found:
            scrape_type  = detect_scrape_type(url, html)
            soup         = BeautifulSoup(html, "lxml")
            tender_links = [
                a for a in soup.select("a[href]")
                if any(kw in a.get_text().lower() for kw in TENDER_PAGE_KEYWORDS)
            ]
            print(f"    ✅ Found: {url}  [{scrape_type}]  (~{len(tender_links)} links)")
            return {"base": base_url, "url": url, "scrape_type": scrape_type,
                    "link_count": len(tender_links)}

    # 2. Try homepage nav links
    print(f"    Trying nav links...")
    nav_links = await find_tender_links_on_homepage(client, base_url)
    for url in nav_links[:8]:
        found, status, html = await check_url(client, url)
        if found:
            scrape_type  = detect_scrape_type(url, html)
            soup         = BeautifulSoup(html, "lxml")
            tender_links = [
                a for a in soup.select("a[href]")
                if any(kw in a.get_text().lower() for kw in TENDER_PAGE_KEYWORDS)
            ]
            print(f"    ✅ Found via nav: {url}  [{scrape_type}]  (~{len(tender_links)} links)")
            return {"base": base_url, "url": url, "scrape_type": scrape_type,
                    "link_count": len(tender_links)}

    print(f"    ❌ No tender page found")
    return None


def format_registry_entry(result: dict, name: str, province: str, town: str = "") -> str:
    """Format a result as a ready-to-paste registry.py entry."""
    return f'''    {{
        "name":                     "{name}",
        "url":                      "{result['url']}",
        "province":                 "{province}",
        "town":                     "{town}",
        "scrape_type":              "{result['scrape_type']}",
        "allow_province_detection": False,
        "notes":                    "Auto-discovered {result['link_count']} links",
    }},'''


# ---------------------------------------------------------------------------
# Built-in municipality lists for each province
# ---------------------------------------------------------------------------

PROVINCE_MUNICIPALITIES = {
    "Limpopo": [
        "https://www.polokwane.gov.za",
        "https://www.capricorndm.gov.za",
        "https://www.mogalakwena.gov.za",
        "https://www.blouberg.gov.za",
        "https://www.lepelle-nkumpi.gov.za",
        "https://www.molemole.gov.za",
        "https://www.thabazimbi.gov.za",
        "https://www.waterberg.gov.za",
        "https://www.mopanidm.gov.za",
        "https://www.tzaneen.gov.za",
        "https://www.maruleng.gov.za",
        "https://www.ba-phalaborwa.gov.za",
        "https://www.giyani.gov.za",
        "https://www.vhembe.gov.za",
        "https://www.thulamela.gov.za",
        "https://www.musina.gov.za",
        "https://www.mutale.gov.za",
        "https://www.collins-chabane.gov.za",
        "https://www.sdr.gov.za",
        "https://www.ephraimmogale.gov.za",
        "https://www.fetakgomo.gov.za",
        "https://www.makhuduthamaga.gov.za",
        "https://www.elias-motsoaledi.gov.za",
        "https://www.gpdlm.gov.za",
    ],
    "KwaZulu-Natal": [
        "https://www.ugu.gov.za",
        "https://www.hibiscuscoast.gov.za",
        "https://www.vulamehlo.gov.za",
        "https://www.ezinqoleni.gov.za",
        "https://www.umzimkhulu.gov.za",
        "https://www.umdoni.gov.za",
        "https://www.umngeni.gov.za",
        "https://www.ilembedc.gov.za",
        "https://www.ndwendwe.gov.za",
        "https://www.kwadukuza.gov.za",
        "https://www.endumeni.gov.za",
        "https://www.uthukela.gov.za",
        "https://www.inkosi-langalibalele.gov.za",
        "https://www.emnambithi.gov.za",
        "https://www.zululand.gov.za",
        "https://www.abaqulusi.gov.za",
        "https://www.nongoma.gov.za",
        "https://www.ulundi.gov.za",
        "https://www.uphongolo.gov.za",
        "https://www.umkhanyakudedc.gov.za",
        "https://www.hlabisa.gov.za",
        "https://www.jozini.gov.za",
        "https://www.mtubatuba.gov.za",
        "https://www.bigfive.gov.za",
        "https://www.kcdm.gov.za",
    ],
    "Mpumalanga": [
        "https://www.ehlanzeni.gov.za",
        "https://www.mbombela.gov.za",
        "https://www.nkomazi.gov.za",
        "https://www.bushbuckridge.gov.za",
        "https://www.nkangala.gov.za",
        "https://www.emalahleni.gov.za",
        "https://www.steve-tshwete.gov.za",
        "https://www.victor-khanye.gov.za",
        "https://www.thembisile.gov.za",
        "https://www.drjsmoroka.gov.za",
        "https://www.gert-sibande.gov.za",
        "https://www.dipaleseng.gov.za",
        "https://www.govanmbeki.gov.za",
        "https://www.pixley.gov.za",
        "https://www.lekwa.gov.za",
        "https://www.msukaligwa.gov.za",
        "https://www.mkhondo.gov.za",
    ],
    "North West": [
        "https://www.bojanala.gov.za",
        "https://www.rustenburg.gov.za",
        "https://www.kgetleng.gov.za",
        "https://www.moses-kotane.gov.za",
        "https://www.madibeng.gov.za",
        "https://www.moretele.gov.za",
        "https://www.ngakamodirimolema.gov.za",
        "https://www.mahikeng.gov.za",
        "https://www.ditsobotla.gov.za",
        "https://www.ramotshere.gov.za",
        "https://www.drkenneth-kaunda.gov.za",
        "https://www.tlokwe.gov.za",
        "https://www.ventersdorp.gov.za",
        "https://www.maquassi.gov.za",
        "https://www.drruthsegomotsi.gov.za",
        "https://www.kagisano-molopo.gov.za",
        "https://www.naledi.gov.za",
    ],
    "Free State": [
        "https://www.mangaung.co.za",
        "https://www.lejweleputswa.gov.za",
        "https://www.masilonyana.gov.za",
        "https://www.matjhabeng.gov.za",
        "https://www.nala.gov.za",
        "https://www.tokologo.gov.za",
        "https://www.tswelopele.gov.za",
        "https://www.thabo-mofutsanyana.gov.za",
        "https://www.dihlabeng.gov.za",
        "https://www.maluti-a-phofung.gov.za",
        "https://www.mantsopa.gov.za",
        "https://www.nketoana.gov.za",
        "https://www.phumelela.gov.za",
        "https://www.setsoto.gov.za",
        "https://www.xhariep.gov.za",
        "https://www.kopanong.gov.za",
        "https://www.letsemeng.gov.za",
        "https://www.mohokare.gov.za",
    ],
    "Western Cape": [
        "https://www.drakenstein.gov.za",
        "https://www.stellenbosch.gov.za",
        "https://www.witzenberg.gov.za",
        "https://www.langeberg.gov.za",
        "https://www.breede-gariep.gov.za",
        "https://www.capeagulhas.gov.za",
        "https://www.overstrand.gov.za",
        "https://www.swellendam.gov.za",
        "https://www.theewaterskloof.gov.za",
        "https://www.george.gov.za",
        "https://www.hessequa.gov.za",
        "https://www.kannaland.gov.za",
        "https://www.knysna.gov.za",
        "https://www.mosselbay.gov.za",
        "https://www.oudtshoorn.gov.za",
        "https://www.beaufortwest.gov.za",
        "https://www.bergrivier.gov.za",
        "https://www.cederberg.gov.za",
        "https://www.matzikama.gov.za",
        "https://www.saldanhabay.gov.za",
        "https://www.swartland.gov.za",
    ],
    "Gauteng": [
        "https://www.ekurhuleni.gov.za",
        "https://www.tshwane.gov.za",
        "https://www.joburg.gov.za",
        "https://www.lesedi.gov.za",
        "https://www.merafong.gov.za",
        "https://www.mogalecity.gov.za",
        "https://www.randfontein.gov.za",
        "https://www.westonaria.gov.za",
        "https://www.emfuleni.gov.za",
        "https://www.midvaal.gov.za",
    ],
}


async def main():
    parser = argparse.ArgumentParser(description="Auto-discover tender URLs for municipality websites")
    parser.add_argument("--urls",     nargs="+", help="One or more base URLs to check")
    parser.add_argument("--file",     help="Text file with one URL per line")
    parser.add_argument("--province", help="Use built-in list for a province")
    parser.add_argument("--name",     help="Municipality name (single URL mode)")
    parser.add_argument("--town",     help="Town name (single URL mode)")
    args = parser.parse_args()

    urls      = []
    province  = args.province or "Unknown"

    if args.urls:
        urls = args.urls
    elif args.file:
        with open(args.file) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    elif args.province and args.province in PROVINCE_MUNICIPALITIES:
        urls     = PROVINCE_MUNICIPALITIES[args.province]
        province = args.province
        print(f"Using built-in list for {province}: {len(urls)} municipalities")
    else:
        parser.print_help()
        return

    print(f"\n{'='*65}")
    print(f"  Discovering tender URLs for {len(urls)} sites...")
    print(f"{'='*65}\n")

    found_entries  = []
    not_found      = []

    async with httpx.AsyncClient(
        headers=get_headers(), follow_redirects=True, verify=False, timeout=15
    ) as client:
        for url in urls:
            result = await discover_site(client, url)
            if result:
                name = args.name or urlparse(url).netloc.replace("www.", "").replace(".gov.za", "").replace("-", " ").title()
                town = args.town or ""
                found_entries.append((result, name, province, town))
            else:
                not_found.append(url)

    print(f"\n{'='*65}")
    print(f"  Results: {len(found_entries)} found, {len(not_found)} not found")
    print(f"{'='*65}\n")

    if found_entries:
        print("# ── Ready to paste into registry.py ACTIVE_SOURCES ──────────────")
        for result, name, prov, town in found_entries:
            print(format_registry_entry(result, name, prov, town))
        print("# ─────────────────────────────────────────────────────────────────\n")

    if not_found:
        print(f"# These {len(not_found)} sites had no discoverable tender pages:")
        for u in not_found:
            print(f"#   {u}")


if __name__ == "__main__":
    asyncio.run(main())