"""
scraper/sites/sa_tenders.py
----------------------------
SA-Tenders.co.za scraper — Windows-compatible via playwright_runner
"""

import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from scraper.utils import (
    make_content_hash, detect_industry, detect_province,
    detect_municipality, detect_town, clean_text, is_closing_date_expired,
)
from scraper.playwright_runner import run_sync

logger     = logging.getLogger(__name__)
AGGREGATORS: List[Dict] = []

SA_TENDERS_URL = "https://sa-tenders.co.za/tenders/"
SOURCE_SITE    = "sa-tenders.co.za"

_CARD_SELECTORS = [
    "article.tender-item", "div.tender-item", "div.tender-list-item",
    "div.listing-item", "div.views-row", "li.tender",
    "table tbody tr",
]
_TITLE_SELECTORS   = ["h2 a", "h3 a", "h4 a", ".tender-title a", ".entry-title a", "a"]
_DATE_SELECTORS    = [".closing-date", ".tender-closing", ".date", "time", "[class*='clos']"]
_BODY_SELECTORS    = [".department", ".issuer", ".authority", ".tender-org", "small"]
_DESC_SELECTORS    = [".description", ".tender-desc", ".entry-summary", "p"]
TENDER_KW          = {"tender", "bid", "rfq", "rfp", "quotation", "procurement", "contract", "supply"}


def _first_text(el, selectors):
    for s in selectors:
        found = el.select_one(s)
        if found:
            return clean_text(found.get_text())
    return ""


def _first_href(el, selectors, base):
    for s in selectors:
        found = el.select_one(s)
        if found and found.get("href"):
            href = found["href"]
            return href if href.startswith("http") else urljoin(base, href)
    return base


def _extract(soup: BeautifulSoup, base: str) -> List[Dict]:
    results = []
    for sel in _CARD_SELECTORS:
        cards = soup.select(sel)
        if cards:
            for card in cards:
                title = _first_text(card, _TITLE_SELECTORS)
                if not title or len(title) < 8:
                    continue
                url          = _first_href(card, _TITLE_SELECTORS, base)
                closing_date = re.sub(r"(?i)(closing\s*date|closes?)\s*[:\-]?\s*", "",
                                      _first_text(card, _DATE_SELECTORS)).strip()
                issuing_body = _first_text(card, _BODY_SELECTORS)
                description  = _first_text(card, _DESC_SELECTORS)
                if closing_date and is_closing_date_expired(closing_date):
                    continue
                raw_text = f"{title} {description} {issuing_body}"
                province = detect_province(raw_text)
                results.append({
                    "title": title, "description": description,
                    "issuing_body": issuing_body, "province": province,
                    "municipality": detect_municipality(raw_text, province),
                    "town": detect_town(raw_text, province),
                    "industry_category": detect_industry(raw_text),
                    "closing_date": closing_date, "posted_date": "",
                    "source_url": url, "document_url": None,
                    "source_site": SOURCE_SITE,
                    "reference_number": "", "contact_info": "",
                    "content_hash": make_content_hash(title, url),
                })
            if results:
                return results

    # Fallback: any tender-keyword link
    seen = set()
    for a in soup.select("a[href]"):
        text = clean_text(a.get_text())
        href = a.get("href", "")
        if len(text) < 15:
            continue
        if not any(kw in text.lower() for kw in TENDER_KW):
            continue
        url = href if href.startswith("http") else urljoin(base, href)
        if url in seen:
            continue
        seen.add(url)
        raw = text
        province = detect_province(raw)
        results.append({
            "title": text, "description": "", "issuing_body": "",
            "province": province,
            "municipality": detect_municipality(raw, province),
            "town": detect_town(raw, province),
            "industry_category": detect_industry(raw),
            "closing_date": "", "posted_date": "",
            "source_url": url, "document_url": None,
            "source_site": SOURCE_SITE,
            "reference_number": "", "contact_info": "",
            "content_hash": make_content_hash(text, url),
        })
    return results


def _sync_scrape(_playwright) -> List[Dict]:
    results: List[Dict] = []
    seen_hashes: set    = set()

    browser = _playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage",
              "--ignore-certificate-errors", "--disable-web-security"],
    )
    context = browser.new_context(
        ignore_https_errors=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1440, "height": 900},
    )
    page = context.new_page()

    logger.info(f"[SA-TENDERS] Loading {SA_TENDERS_URL}")
    page.goto(SA_TENDERS_URL, wait_until="networkidle", timeout=60000)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)

    for page_num in range(1, 6):
        soup  = BeautifulSoup(page.content(), "lxml")
        items = _extract(soup, SA_TENDERS_URL)
        new   = 0
        for t in items:
            if t["content_hash"] not in seen_hashes:
                seen_hashes.add(t["content_hash"])
                results.append(t)
                new += 1
        logger.info(f"[SA-TENDERS] Page {page_num}: {new} new items (total {len(results)})")
        if new == 0:
            break
        next_btn = (
            page.query_selector("a.next")
            or page.query_selector("a[rel='next']")
            or page.query_selector(".pagination a.next")
            or page.query_selector("a:has-text('Next')")
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
    logger.info(f"[SA-TENDERS] Final: {len(results)} tenders")
    return results


async def scrape_sa_tenders() -> List[Dict]:
    try:
        return await run_sync(_sync_scrape)
    except Exception as e:
        logger.error(f"[SA-TENDERS] Failed: {e}")
        return []


async def scrape_aggregator(client, source: Dict) -> List[Dict]:
    return []


async def scrape_detail(client, url: str, source: Dict) -> List[Dict]:
    return []


async def scrape() -> List[Dict]:
    return await scrape_sa_tenders()