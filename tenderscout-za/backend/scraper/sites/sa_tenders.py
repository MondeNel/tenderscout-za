"""
scraper/sites/sa_tenders.py
----------------------------
Scraper for https://sa-tenders.co.za/tenders/
Uses async_playwright — works inside FastAPI's asyncio event loop on Windows.

SA-Tenders is a table-based aggregator:
Columns: Category | Description | Published | Closing | Pin
The "+" expander reveals more detail per row.
"""

import asyncio
import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from scraper.utils import (
    make_content_hash, detect_industry, detect_province,
    detect_municipality, detect_town, clean_text, is_closing_date_expired,
)

logger = logging.getLogger(__name__)

AGGREGATORS: List[Dict] = []  # kept for engine.py import compatibility

SA_TENDERS_URL  = "https://sa-tenders.co.za/tenders/"
SA_TENDERS_SITE = "sa-tenders.co.za"

TENDER_KEYWORDS = {"tender", "bid", "rfq", "rfp", "quotation", "procurement", "contract", "supply"}

_CARD_SELECTORS = [
    "article.tender-item", "div.tender-item", "div.tender-list-item",
    "div.listing-item", "div.views-row", "li.tender",
    "table tbody tr",
]
_TITLE_SELECTORS = ["h2 a", "h3 a", "h4 a", ".tender-title a", ".entry-title a", "a"]
_DATE_SELECTORS  = [".closing-date", ".tender-closing", ".date", "time", "[class*='clos']", "[class*='date']"]
_BODY_SELECTORS  = [".department", ".issuer", ".authority", ".tender-org", "small"]


def _first_text(el, selectors):
    for s in selectors:
        f = el.select_one(s)
        if f:
            return clean_text(f.get_text())
    return ""


def _first_href(el, selectors, base):
    for s in selectors:
        f = el.select_one(s)
        if f and f.get("href"):
            href = f["href"]
            return href if href.startswith("http") else urljoin(base, href)
    return base


def _parse_cards(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    for selector in _CARD_SELECTORS:
        cards = soup.select(selector)
        if not cards:
            continue
        logger.info(f"[SA-TENDERS] Matched '{selector}' ({len(cards)} cards)")
        results = []
        for card in cards:
            title = _first_text(card, _TITLE_SELECTORS)
            if not title or len(title) < 8:
                continue
            url          = _first_href(card, _TITLE_SELECTORS, base_url)
            closing_date = _first_text(card, _DATE_SELECTORS)
            closing_date = re.sub(r"(?i)(closing\s*date|closes?)\s*[:\-]?\s*", "", closing_date).strip()
            issuing_body = _first_text(card, _BODY_SELECTORS)
            description  = _first_text(card, [".description", ".tender-desc", "p"])

            if closing_date and is_closing_date_expired(closing_date):
                continue

            raw_text = f"{title} {description} {issuing_body}"
            province = detect_province(raw_text)
            results.append({
                "title":             title,
                "description":       description,
                "issuing_body":      issuing_body,
                "province":          province,
                "municipality":      detect_municipality(raw_text, province),
                "town":              detect_town(raw_text, province),
                "industry_category": detect_industry(raw_text),
                "closing_date":      closing_date,
                "posted_date":       "",
                "source_url":        url,
                "document_url":      None,
                "source_site":       SA_TENDERS_SITE,
                "reference_number":  "",
                "contact_info":      "",
                "content_hash":      make_content_hash(title, url),
            })
        if results:
            return results

    # Last resort: link scan
    logger.warning("[SA-TENDERS] No card selector matched — link scan fallback")
    results = []
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
        province = detect_province(text)
        results.append({
            "title": text, "description": "", "issuing_body": "",
            "province": province, "municipality": detect_municipality(text, province),
            "town": detect_town(text, province), "industry_category": detect_industry(text),
            "closing_date": "", "posted_date": "", "source_url": url,
            "document_url": None, "source_site": SA_TENDERS_SITE,
            "reference_number": "", "contact_info": "",
            "content_hash": make_content_hash(text, url),
        })
    return results


async def scrape_sa_tenders() -> List[Dict]:
    """Async Playwright scraper — works inside FastAPI's event loop."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[SA-TENDERS] Playwright not installed")
        return []

    results: List[Dict] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors", "--disable-web-security",
                      "--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            logger.info(f"[SA-TENDERS] Loading {SA_TENDERS_URL}")
            await page.goto(SA_TENDERS_URL, wait_until="networkidle", timeout=60000)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            all_html = []
            for page_num in range(1, 6):
                all_html.append(await page.content())
                logger.info(f"[SA-TENDERS] Captured page {page_num}")

                next_btn = (
                    await page.query_selector("a.next")
                    or await page.query_selector("a[rel='next']")
                    or await page.query_selector(".pagination a.next")
                    or await page.query_selector("a:has-text('Next')")
                    or await page.query_selector("a:has-text('›')")
                )
                if not next_btn:
                    break
                try:
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await page.wait_for_timeout(1500)
                except Exception:
                    break

            await browser.close()

        seen = set()
        for html in all_html:
            soup = BeautifulSoup(html, "lxml")
            items = _parse_cards(soup, SA_TENDERS_URL)
            for item in items:
                if item["content_hash"] not in seen:
                    seen.add(item["content_hash"])
                    results.append(item)

        logger.info(f"[SA-TENDERS] {len(results)} unique tenders")

    except Exception as e:
        logger.exception(f"[SA-TENDERS] Scrape failed: {e}")

    return results


# Engine compatibility shims
async def scrape_aggregator(client, source: Dict) -> List[Dict]:
    return []

async def scrape_detail(client, url: str, source: Dict) -> List[Dict]:
    return []

async def scrape() -> List[Dict]:
    return await scrape_sa_tenders()