"""
scraper/sites/js_scraper.py
----------------------------
Playwright scrapers for JS-rendered sites.
Uses async_playwright — works inside FastAPI's asyncio event loop on Windows.
"""

import asyncio
import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlencode
from bs4 import BeautifulSoup
from scraper.utils import (
    make_content_hash, detect_industry, detect_province,
    detect_municipality, detect_town, clean_text, is_closing_date_expired,
)

logger = logging.getLogger(__name__)

JS_SOURCES = [
    {
        "name": "EasyTenders (Northern Cape)",
        "url":  "https://easytenders.co.za/tenders",
        "province_hint": "Northern Cape",
        "query_params":  {"province": "northern-cape"},
    },
]


def _extract_easytenders(html: str, base_url: str, source: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []
    seen_urls = set()

    closing_divs = soup.select("div.clearfix.closing-date")
    logger.info(f"[EASYTENDERS] Found {len(closing_divs)} closing-date divs")

    for closing_div in closing_divs:
        try:
            container = closing_div
            for _ in range(5):
                container = container.parent
                if not container:
                    break
                title_link = container.select_one("h5 a, h4 a, h3 a, .media-body a, a")
                if title_link:
                    break

            if not container:
                continue

            title_link = container.select_one("h5 a, h4 a, h3 a, .media-body a, a")
            if not title_link:
                continue

            title = clean_text(title_link.get_text())
            if not title or len(title) < 10:
                continue

            href = title_link.get("href", "")
            if not href or href == "#":
                continue

            detail_url = href if href.startswith("http") else urljoin(base_url, href)
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            closing_date = clean_text(closing_div.get_text()).replace("Closing", "").strip()
            desc_el  = container.select_one("p, .description")
            body_el  = container.select_one(".issuer, .department, .company, small")
            description  = clean_text(desc_el.get_text()) if desc_el else ""
            issuing_body = clean_text(body_el.get_text()) if body_el else ""

            if closing_date and is_closing_date_expired(closing_date):
                continue

            full_text = f"{title} {description} {issuing_body}"
            province  = detect_province(full_text) or source.get("province_hint", "Northern Cape")

            results.append({
                "title":             title,
                "description":       description,
                "issuing_body":      issuing_body,
                "province":          province,
                "municipality":      detect_municipality(full_text, province),
                "town":              detect_town(full_text, province),
                "industry_category": detect_industry(full_text),
                "closing_date":      closing_date,
                "posted_date":       "",
                "source_url":        detail_url,
                "document_url":      None,
                "source_site":       base_url.split("/")[2].replace("www.", ""),
                "reference_number":  "",
                "contact_info":      "",
                "content_hash":      make_content_hash(title, detail_url),
            })
        except Exception as e:
            logger.debug(f"[EASYTENDERS] Item error: {e}")

    return results


def _extract_generic(html: str, base_url: str, source: Dict) -> List[Dict]:
    """Generic card/link extractor for unknown JS sites."""
    soup = BeautifulSoup(html, "lxml")
    results = []
    TENDER_KW = ["tender", "bid", "rfq", "rfp", "quotation", "procurement"]

    for a in soup.select("a[href]"):
        text = clean_text(a.get_text())
        href = a.get("href", "")
        if not text or len(text) < 15:
            continue
        if not any(kw in text.lower() for kw in TENDER_KW):
            continue
        url = href if href.startswith("http") else urljoin(base_url, href)
        province = detect_province(text) or source.get("province_hint")
        results.append({
            "title":             text,
            "description":       "",
            "issuing_body":      source.get("name", ""),
            "province":          province,
            "municipality":      detect_municipality(text, province),
            "town":              detect_town(text, province),
            "industry_category": detect_industry(text),
            "closing_date":      "",
            "posted_date":       "",
            "source_url":        url,
            "document_url":      None,
            "source_site":       base_url.split("/")[2].replace("www.", ""),
            "reference_number":  "",
            "contact_info":      "",
            "content_hash":      make_content_hash(text, url),
        })
    return results


async def scrape_js_source(source: Dict) -> List[Dict]:
    """Scrape a JS-rendered source using async Playwright."""
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error("[JS_SCRAPER] Playwright not installed — run: pip install playwright && python -m playwright install chromium")
        return []

    base_url = source["url"]
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
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            target_url = base_url
            if source.get("query_params"):
                target_url = f"{base_url}?{urlencode(source['query_params'])}"

            logger.info(f"[JS_SCRAPER] Loading {target_url}")
            await page.goto(target_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            # Scroll to trigger lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            # Paginate up to 5 pages
            all_html = []
            for page_num in range(1, 6):
                all_html.append(await page.content())
                logger.info(f"[JS_SCRAPER] Captured page {page_num}")

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

        # Parse all pages
        seen = set()
        for html in all_html:
            if "easytenders" in base_url:
                items = _extract_easytenders(html, base_url, source)
            else:
                items = _extract_generic(html, base_url, source)

            for item in items:
                h = item["content_hash"]
                if h not in seen:
                    seen.add(h)
                    results.append(item)

        logger.info(f"[JS_SCRAPER] {source['name']}: {len(results)} tenders")

    except Exception as e:
        logger.exception(f"[JS_SCRAPER] {source['name']} failed: {e}")

    return results


async def scrape() -> List[Dict]:
    all_results = []
    for source in JS_SOURCES:
        try:
            results = await scrape_js_source(source)
            all_results.extend(results)
        except Exception as e:
            logger.error(f"[JS_SCRAPER] {source['name']}: {e}")
    return all_results