"""
scraper/sites/city_portals.py
------------------------------
HTML scrapers for all non-Playwright tender sources.
Site list is driven entirely by registry.py — do not hardcode sites here.
"""

import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional

from scraper.utils import (
    make_content_hash, detect_industry, detect_municipality, detect_town,
    detect_province, clean_text, get_headers, is_likely_expired, is_closing_date_expired,
)
from scraper.sites.registry import get_html_sources

import logging
logger = logging.getLogger(__name__)

# Driven by registry — no hardcoded list here
CITY_PORTALS = get_html_sources()

TENDER_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "supply", "contract"]

NAV_WORDS = frozenset([
    "home", "about", "contact", "login", "forgot", "gallery", "council",
    "notice", "vacancy", "vacancies", "budget", "annual report",
    "financial statement", "organogram", "sitemap", "privacy", "terms",
])


def _base(city: Dict) -> str:
    p = urlparse(city["url"])
    return f"{p.scheme}://{p.netloc}"


def _build_result(title, href, city, listing_url, closing_date="", extra_text="") -> Optional[Dict]:
    if not title or len(title.strip()) < 5:
        return None

    doc_url = None
    if href and any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".zip"]):
        doc_url = href if href.startswith("http") else None

    detection_text = f"{title} {extra_text}"
    if city.get("allow_province_detection"):
        province = detect_province(detection_text) or city["province"]
    else:
        province = city["province"]

    municipality = detect_municipality(detection_text, province)
    town         = detect_town(detection_text, province) or city.get("town")

    if closing_date and is_closing_date_expired(closing_date):
        return None

    return {
        "title":             title.strip(),
        "description":       f"Tender from {city['name']}.",
        "issuing_body":      city["name"],
        "province":          province,
        "municipality":      municipality,
        "town":              town,
        "industry_category": detect_industry(detection_text),
        "closing_date":      closing_date,
        "posted_date":       "",
        "source_url":        listing_url,
        "document_url":      doc_url,
        "source_site":       urlparse(city["url"]).netloc.replace("www.", ""),
        "reference_number":  "",
        "contact_info":      "",
        "content_hash":      make_content_hash(title, listing_url),
    }


# ---------------------------------------------------------------------------
# Scraper implementations
# ---------------------------------------------------------------------------

async def scrape_phoca(client, city):
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)
        candidates = (
            soup.select("div.phocadownload a, span.phocadownload a")
            + soup.select("a[href*='.pdf'], a[href*='download'], a[title]")
        )
        seen = set()
        for link in candidates:
            href  = link.get("href", "")
            title = clean_text(link.get("title") or link.get_text())
            if not title or len(title) < 5 or title in seen:
                continue
            if any(n in title.lower() for n in NAV_WORDS):
                continue
            seen.add(title)
            full_url = href if href.startswith("http") else urljoin(base, href)
            if is_likely_expired(title, full_url):
                continue
            parent_text = link.parent.get_text() if link.parent else ""
            dm = re.search(r'(?:Closing|Closes)[:\s]*([\d/\w\s]+?)(?:\n|$)', parent_text, re.IGNORECASE)
            closing = clean_text(dm.group(1)) if dm else ""
            res = _build_result(title, full_url, city, city["url"], closing)
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} phoca: {e}")
    return results


async def scrape_links(client, city):
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 10:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue
            full_url = href if href.startswith("http") else urljoin(base, href)
            res = _build_result(text, full_url, city, city["url"])
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} links: {e}")
    return results


async def scrape_standard(client, city):
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())
            if not text or len(text) < 8:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue
            full_url    = href if href.startswith("http") else urljoin(base, href)
            extra_text  = clean_text(link.parent.get_text()) if link.parent else ""
            res = _build_result(text, full_url, city, city["url"], extra_text=extra_text)
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} standard: {e}")
    return results


async def scrape_siyancuma(client, city):
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)
        for link in soup.select('a[href*=".pdf"]'):
            href  = link.get("href", "")
            title = clean_text(link.get_text())
            if not title or len(title) < 5:
                continue
            if not any(kw in title.lower() for kw in TENDER_KEYWORDS):
                continue
            full_url    = href if href.startswith("http") else urljoin(base, href)
            parent_text = link.parent.get_text() if link.parent else ""
            dm = re.search(r'Closing\s*Date[:\s]*([\d/]+)', parent_text, re.IGNORECASE)
            closing = dm.group(1) if dm else ""
            res = _build_result(title, full_url, city, city["url"], closing)
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} siyancuma: {e}")
    return results


async def scrape_hantam(client, city):
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)
        view_all = (
            soup.select_one('a[href*="tender-documents"]')
            or soup.select_one('a[href*="tenders"]')
        )
        if not view_all:
            return results
        href      = view_all.get("href", "")
        page_url  = href if href.startswith("http") else urljoin(base, href)
        r2        = await client.get(page_url)
        if r2.status_code != 200:
            return results
        soup2 = BeautifulSoup(r2.text, "lxml")
        for link in soup2.select('a[href*=".pdf"]'):
            href  = link.get("href", "")
            title = clean_text(link.get_text())
            if not title or len(title) < 5:
                continue
            doc_url = href if href.startswith("http") else urljoin(base, href)
            res = _build_result(title, doc_url, city, page_url)
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} hantam: {e}")
    return results


async def scrape_gamagara(client, city):
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup  = BeautifulSoup(r.text, "lxml")
        text  = soup.get_text()
        for match in re.finditer(
            r'(GM\d{4}-\d+)\s+(.*?)(?=Closing:.*?)(Closing:\s*[^G]+)',
            text, re.DOTALL | re.IGNORECASE
        ):
            ref_no  = match.group(1).strip()
            title   = clean_text(match.group(2))
            closing = match.group(3).replace("Closing:", "").strip()
            pdfs    = re.findall(r'https://[^"\s]+\.pdf', text[match.start():match.end() + 500])
            doc_url = pdfs[0] if pdfs else None
            if not title or len(title) < 5:
                continue
            res = _build_result(title, doc_url, city, city["url"], closing)
            if res:
                res["reference_number"] = ref_no
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} gamagara: {e}")
    return results





# ---------------------------------------------------------------------------
# New scraper implementations for URL-fixed sites
# ---------------------------------------------------------------------------

async def scrape_dikgatlong(client, city):
    """
    Dikgatlong / Magareng style:
    Each tender is a <div> or <article> with:
      - Heading containing "RefNo - Title - Closing Date: DD Month YYYY"
      - A PDF link below it
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)

        # Each tender block: find headings that contain ref numbers like FIN05/2025/26
        for heading in soup.select("h1, h2, h3, h4, h5, .entry-title, .tender-title"):
            title_text = clean_text(heading.get_text())
            if not title_text or len(title_text) < 10:
                continue
            if not any(kw in title_text.lower() for kw in TENDER_KEYWORDS):
                continue

            # Extract closing date from title text
            closing = ""
            dm = re.search(r'Closing\s*Date[:\s]*([\d\s\w]+(?:\d{4}))', title_text, re.IGNORECASE)
            if dm:
                closing = dm.group(1).strip()

            # Find nearest PDF link
            doc_url = None
            parent = heading.parent
            if parent:
                pdf_link = parent.select_one('a[href*=".pdf"]')
                if pdf_link:
                    href = pdf_link.get("href", "")
                    doc_url = href if href.startswith("http") else urljoin(base, href)

            res = _build_result(title_text, doc_url or city["url"], city, city["url"], closing)
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} dikgatlong: {e}")
    return results


async def scrape_phokwane(client, city):
    """
    WordPress category page style (Phokwane, Mangaung):
    Posts shown as cards with h2 title + excerpt containing closing date.
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)

        # WordPress post cards
        for article in soup.select("article, .post, .entry, div.type-post"):
            title_el = article.select_one("h1 a, h2 a, h3 a, .entry-title a")
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 10:
                continue
            href = title_el.get("href", "")
            url  = href if href.startswith("http") else urljoin(base, href)

            # Get closing date from excerpt
            excerpt = article.select_one(".entry-summary, .excerpt, p")
            excerpt_text = clean_text(excerpt.get_text()) if excerpt else ""
            dm = re.search(r'Closing\s*Date[:\s]*([\d\s\w/]+(?:\d{4}))', excerpt_text, re.IGNORECASE)
            closing = dm.group(1).strip() if dm else ""

            res = _build_result(title, url, city, city["url"], closing)
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} phokwane: {e}")
    return results


async def scrape_frances_baard(client, city):
    """
    Frances Baard style:
    Cards with bold title heading + "Closing date: DD Month YYYY at HH:mm"
    + "Click to Download" button linking to PDF.
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)

        # Each card is a div/section containing a title, closing date, and download link
        for card in soup.select("div, section, article"):
            # Must have a bold or heading title + closing date text
            card_text = card.get_text()
            if len(card_text) < 20:
                continue
            if "closing date" not in card_text.lower() and "download" not in card_text.lower():
                continue

            title_el = card.select_one("h1, h2, h3, h4, h5, strong, b")
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 10:
                continue
            if not any(kw in title.lower() for kw in TENDER_KEYWORDS):
                continue

            # Closing date
            dm = re.search(r'Closing\s*date[:\s]*([\d\s\w]+(?:\d{4})(?:\s+at\s+[\d:]+)?)', card_text, re.IGNORECASE)
            closing = clean_text(dm.group(1)) if dm else ""

            # Download link
            dl_link = card.select_one("a")
            doc_url = None
            if dl_link:
                href = dl_link.get("href", "")
                doc_url = href if href.startswith("http") else urljoin(base, href)

            res = _build_result(title, doc_url or city["url"], city, city["url"], closing)
            if res:
                results.append(res)

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r["content_hash"] not in seen:
                seen.add(r["content_hash"])
                unique.append(r)
        results = unique
    except Exception as e:
        logger.exception(f"{city['name']} frances_baard: {e}")
    return results


async def scrape_dawid_kruiper(client, city):
    """
    Dawid Kruiper Municipality — modern tabbed table:
    Tabs: Open Bids | Closed Bids | Cancelled Bids | Adjudicated Bids
    Table columns: Title | Site Meeting | Closing Date | Download
    We only want "Open Bids" tab (default active tab).
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)

        # The open bids table — first visible table or tab panel
        for table in soup.select("table"):
            rows = table.select("tbody tr")
            if not rows:
                continue
            header_text = table.get_text().lower()
            if "title" not in header_text and "closing" not in header_text:
                continue

            for row in rows:
                cells = row.select("td")
                if len(cells) < 2:
                    continue
                title       = clean_text(cells[0].get_text()) if cells else ""
                closing_raw = clean_text(cells[2].get_text()) if len(cells) > 2 else ""
                if not title or len(title) < 8:
                    continue

                # Download link
                dl = row.select_one("a[href], button")
                doc_url = None
                if dl and dl.get("href"):
                    href = dl["href"]
                    doc_url = href if href.startswith("http") else urljoin(base, href)

                res = _build_result(title, doc_url or city["url"], city, city["url"], closing_raw)
                if res:
                    results.append(res)
            if results:
                break
    except Exception as e:
        logger.exception(f"{city['name']} dawid_kruiper: {e}")
    return results


async def scrape_zfm_district(client, city):
    """
    ZF Mgcawu District — document directory listing:
    PDF filenames are the tender titles, each is a direct link.
    URL: https://www.zfm-dm.gov.za/documents/?dir=4302
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)

        for link in soup.select("a[href*='.pdf'], a[href*='.doc']"):
            href  = link.get("href", "")
            # Use filename as title, clean it up
            filename = href.split("/")[-1].replace("-", " ").replace("_", " ")
            title    = clean_text(link.get_text()) or clean_text(filename)
            if not title or len(title) < 5:
                continue
            doc_url = href if href.startswith("http") else urljoin(base, href)
            res = _build_result(title, doc_url, city, city["url"])
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} zfm_district: {e}")
    return results


async def scrape_namakwa_district(client, city):
    """
    Namakwa District — grouped-by-month link list:
    Headings like "April 2026", "March 2026" with bullet-point links below each.
    Links use descriptive text like "Tender 202026 Document – 13 laptops final"
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)

        current_month = ""
        for el in soup.select("h1, h2, h3, h4, li, p"):
            text = clean_text(el.get_text())

            # Detect month headings
            if re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$', text, re.IGNORECASE):
                current_month = text
                continue

            # Tender links
            link = el.select_one("a[href]") if el.name in ("li", "p") else None
            if not link:
                link = el if el.name == "a" and el.get("href") else None
            if not link:
                continue

            title = clean_text(link.get_text())
            if not title or len(title) < 8:
                continue
            # Skip orange/old links (they're typically past tenders)
            # Include if title looks like a tender
            href    = link.get("href", "")
            doc_url = href if href.startswith("http") else urljoin(base, href)

            # Annotate with month for context
            full_title = f"{title} ({current_month})" if current_month else title
            res = _build_result(full_title, doc_url, city, city["url"])
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} namakwa_district: {e}")
    return results


async def scrape_kareeberg(client, city):
    """
    Kareeberg Municipality — static .htm page:
    Simple list of RFQ links, e.g. "RFQ 21-2026 : Supply and Delivery of Airdac"
    URL pattern changes each year: written_quotations_2026.htm
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            # Try current year dynamically
            import datetime
            year = datetime.datetime.now().year
            alt_url = re.sub(r'\d{4}\.htm', f'{year}.htm', city["url"])
            r = await client.get(alt_url)
            if r.status_code != 200:
                return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)

        for link in soup.select("a[href]"):
            title = clean_text(link.get_text())
            if not title or len(title) < 8:
                continue
            href    = link.get("href", "")
            doc_url = href if href.startswith("http") else urljoin(base, href)
            res = _build_result(title, doc_url, city, city["url"])
            if res:
                results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} kareeberg: {e}")
    return results


async def scrape_ga_segonyana(client, city):
    """
    Ga-Segonyana Municipality — simple HTML table:
    Columns: Tender Advert (link) | Closing Date
    """
    results = []
    try:
        r = await client.get(city["url"])
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")
        base = _base(city)

        for table in soup.select("table"):
            for row in table.select("tr"):
                cells = row.select("td")
                if len(cells) < 2:
                    continue
                link_el  = cells[0].select_one("a[href]")
                if not link_el:
                    continue
                title    = clean_text(link_el.get_text())
                href     = link_el.get("href", "")
                closing  = clean_text(cells[1].get_text()) if len(cells) > 1 else ""
                doc_url  = href if href.startswith("http") else urljoin(base, href)
                if not title or len(title) < 8:
                    continue
                res = _build_result(title, doc_url, city, city["url"], closing)
                if res:
                    results.append(res)
    except Exception as e:
        logger.exception(f"{city['name']} ga_segonyana: {e}")
    return results

# ---------------------------------------------------------------------------
# Dispatcher — defined AFTER all scraper functions
# ---------------------------------------------------------------------------

_DISPATCH = {
    "phoca":            scrape_phoca,
    "links":            scrape_links,
    "standard":         scrape_standard,
    "siyancuma":        scrape_siyancuma,
    "hantam":           scrape_hantam,
    "gamagara":         scrape_gamagara,
    "dikgatlong":       scrape_dikgatlong,
    "phokwane":         scrape_phokwane,
    "frances_baard":    scrape_frances_baard,
    "dawid_kruiper":    scrape_dawid_kruiper,
    "zfm_district":     scrape_zfm_district,
    "namakwa_district": scrape_namakwa_district,
    "kareeberg":        scrape_kareeberg,
    "ga_segonyana":     scrape_ga_segonyana,
}


async def scrape_city(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    handler = _DISPATCH.get(city.get("scrape_type", "links"), scrape_links)
    return await handler(client, city)


async def scrape() -> List[Dict]:
    results = []
    async with httpx.AsyncClient(
        timeout=30, headers=get_headers(), follow_redirects=True, verify=False
    ) as client:
        for city in CITY_PORTALS:
            try:
                city_results = await scrape_city(client, city)
                results.extend(city_results)
                logger.info(f"{city['name']}: {len(city_results)} tenders")
            except Exception as e:
                logger.error(f"{city['name']}: {e}")
    return results