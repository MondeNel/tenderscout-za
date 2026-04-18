"""
scraper/sites/sa_tenders.py
----------------------------
Scraper for https://sa-tenders.co.za/tenders/

The site is a WordPress/custom PHP site that renders tender listings as HTML
cards. We use Playwright to handle any JS lazy-loading, then parse with
BeautifulSoup.

Selector strategy (tried in order, first match wins):
  - article.tender-item
  - div.tender-item
  - div.tender-list-item
  - tr (table rows with tender content)
  - Any <a> whose text/href contains tender keywords (last-resort fallback)
"""

import asyncio
import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.utils import (
    make_content_hash,
    detect_industry,
    detect_province,
    detect_municipality,
    detect_town,
    clean_text,
    is_closing_date_expired,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source config
# ---------------------------------------------------------------------------

AGGREGATORS: List[Dict] = []   # kept for engine.py import compatibility

SA_TENDERS_SOURCE = {
    "name": "sa-tenders.co.za",
    "url": "https://sa-tenders.co.za/tenders/",
    "province_hint": None,        # multi-province — detect per tender
}

# Tender card selectors tried in priority order
_CARD_SELECTORS = [
    "article.tender-item",
    "div.tender-item",
    "div.tender-list-item",
    "div.listing-item",
    "div.views-row",
    "li.tender",
]

# Field selectors tried in priority order inside each card
_TITLE_SELECTORS   = ["h2 a", "h3 a", "h4 a", ".tender-title a", ".entry-title a", "a"]
_DATE_SELECTORS    = [".closing-date", ".tender-closing", ".date", "time", "[class*='clos']", "[class*='date']"]
_BODY_SELECTORS    = [".department", ".issuer", ".authority", ".tender-org", ".organization", "small"]
_DESC_SELECTORS    = [".description", ".tender-desc", ".entry-summary", "p"]

TENDER_KEYWORDS = {"tender", "bid", "rfq", "rfp", "quotation", "procurement", "contract", "supply"}


# ---------------------------------------------------------------------------
# HTML extraction helpers
# ---------------------------------------------------------------------------

def _first_text(element, selectors: List[str]) -> str:
    for sel in selectors:
        found = element.select_one(sel)
        if found:
            return clean_text(found.get_text())
    return ""


def _first_href(element, selectors: List[str], base_url: str) -> str:
    for sel in selectors:
        found = element.select_one(sel)
        if found and found.get("href"):
            href = found["href"]
            return href if href.startswith("http") else urljoin(base_url, href)
    return base_url


def _extract_cards(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """Try each card selector in order. Returns list of raw tender dicts."""
    results = []

    for selector in _CARD_SELECTORS:
        cards = soup.select(selector)
        if cards:
            logger.info(f"[SA-TENDERS] Matched card selector: '{selector}' ({len(cards)} cards)")
            for card in cards:
                item = _parse_card(card, base_url)
                if item:
                    results.append(item)
            return results

    # Last-resort: any link whose text or href looks like a tender
    logger.warning("[SA-TENDERS] No card selector matched — falling back to link scan")
    seen = set()
    for a in soup.select("a[href]"):
        text = clean_text(a.get_text())
        href = a.get("href", "")
        if len(text) < 10:
            continue
        if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
            continue
        url = href if href.startswith("http") else urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        results.append({
            "title": text,
            "description": "",
            "issuing_body": "",
            "closing_date": "",
            "url": url,
            "raw_text": text,
        })
    return results


def _parse_card(card, base_url: str) -> Optional[Dict]:
    title = _first_text(card, _TITLE_SELECTORS)
    if not title or len(title) < 8:
        return None

    url = _first_href(card, _TITLE_SELECTORS, base_url)
    closing_date = _first_text(card, _DATE_SELECTORS)
    issuing_body = _first_text(card, _BODY_SELECTORS)
    description  = _first_text(card, _DESC_SELECTORS)

    # Strip label noise from closing date ("Closing date:", "Closes:", etc.)
    closing_date = re.sub(r"(?i)(closing\s*date|closes?)\s*[:\-]?\s*", "", closing_date).strip()

    return {
        "title": title,
        "description": description,
        "issuing_body": issuing_body,
        "closing_date": closing_date,
        "url": url,
        "raw_text": f"{title} {description} {issuing_body}",
    }


def _build_tender(raw: Dict, source: Dict) -> Optional[Dict]:
    title        = raw.get("title", "")
    closing_date = raw.get("closing_date", "")
    url          = raw.get("url", source["url"])
    raw_text     = raw.get("raw_text", title)

    if not title:
        return None
    if closing_date and is_closing_date_expired(closing_date):
        return None

    province     = detect_province(raw_text) or source.get("province_hint")
    municipality = detect_municipality(raw_text, province)
    town         = detect_town(raw_text, province)

    return {
        "title":             title,
        "description":       raw.get("description", ""),
        "issuing_body":      raw.get("issuing_body", ""),
        "province":          province,
        "municipality":      municipality,
        "town":              town,
        "industry_category": detect_industry(raw_text),
        "closing_date":      closing_date,
        "posted_date":       "",
        "source_url":        url,
        "document_url":      None,
        "source_site":       urlparse(source["url"]).netloc.replace("www.", ""),
        "reference_number":  "",
        "contact_info":      "",
        "content_hash":      make_content_hash(title, url),
    }


# ---------------------------------------------------------------------------
# Playwright scraper
# ---------------------------------------------------------------------------

def _sync_scrape_sa_tenders(source: Dict) -> List[Dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("[SA-TENDERS] Playwright not installed. Run: pip install playwright && python -m playwright install chromium")
        return []

    results = []
    url = source["url"]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors", "--disable-web-security", "--no-sandbox"],
            )
            context = browser.new_context(
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            logger.info(f"[SA-TENDERS] Navigating to {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)

            # Scroll to trigger any lazy-loaded content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # Paginate — follow "Next" links up to 5 pages
            all_html_pages = []
            for page_num in range(1, 6):
                all_html_pages.append(page.content())
                logger.info(f"[SA-TENDERS] Captured page {page_num}")

                # Try common "next page" patterns
                next_btn = (
                    page.query_selector("a.next")
                    or page.query_selector("a[rel='next']")
                    or page.query_selector(".pagination a.next")
                    or page.query_selector("a:has-text('Next')")
                    or page.query_selector("a:has-text('›')")
                )
                if not next_btn:
                    break
                try:
                    next_btn.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
                    page.wait_for_timeout(1500)
                except Exception:
                    break

            browser.close()

        # Parse all captured pages
        base_url = url
        for html in all_html_pages:
            soup = BeautifulSoup(html, "lxml")
            raw_items = _extract_cards(soup, base_url)
            for raw in raw_items:
                tender = _build_tender(raw, source)
                if tender:
                    results.append(tender)

        # Deduplicate by content_hash
        seen_hashes = set()
        unique = []
        for t in results:
            h = t["content_hash"]
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique.append(t)

        logger.info(f"[SA-TENDERS] {len(unique)} unique tenders extracted")
        return unique

    except Exception as e:
        logger.exception(f"[SA-TENDERS] Scrape failed: {e}")
        return []


async def scrape_sa_tenders() -> List[Dict]:
    return await asyncio.to_thread(_sync_scrape_sa_tenders, SA_TENDERS_SOURCE)


# ---------------------------------------------------------------------------
# Engine compatibility shims
# ---------------------------------------------------------------------------

async def scrape_aggregator(client, source: Dict) -> List[Dict]:
    """Called by engine.py for AGGREGATORS entries. No HTML aggregators active."""
    return []


async def scrape_detail(client, url: str, source: Dict) -> List[Dict]:
    """Called by engine.py when crawler finds a verified URL for this source."""
    return []


async def scrape() -> List[Dict]:
    return await scrape_sa_tenders()