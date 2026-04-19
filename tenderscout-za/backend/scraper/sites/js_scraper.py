"""
scraper/sites/js_scraper.py
----------------------------
EasyTenders scraper — ALL provinces, not just Northern Cape.
Uses Windows-compatible Playwright runner.
"""

import logging
import re
from typing import List, Dict
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from scraper.utils import (
    make_content_hash, detect_industry, detect_province,
    detect_municipality, detect_town, clean_text, is_closing_date_expired,
)
from scraper.playwright_runner import run_sync

logger = logging.getLogger(__name__)

# All SA provinces with their EasyTenders URL slugs
EASYTENDERS_PROVINCES = [
    ("Gauteng",       "gauteng"),
    ("Western Cape",  "western-cape"),
    ("KwaZulu-Natal", "kwazulu-natal"),
    ("Eastern Cape",  "eastern-cape"),
    ("Free State",    "free-state"),
    ("Limpopo",       "limpopo"),
    ("Mpumalanga",    "mpumalanga"),
    ("North West",    "north-west"),
    ("Northern Cape", "northern-cape"),
]

JS_SOURCES = [
    {
        "name":        "EasyTenders",
        "url":         "https://easytenders.co.za/tenders",
        "scrape_type": "js_playwright",
        "allow_province_detection": True,
        "province":    None,
        "town":        None,
        "notes":       "Multi-province — scrapes all 9 provinces",
    },
]


def _extract_tenders(html: str, base_url: str, province_hint: str = None) -> List[Dict]:
    soup    = BeautifulSoup(html, "lxml")
    results = []
    seen    = set()

    closing_divs = soup.select("div.clearfix.closing-date, .closing-date, [class*='closing']")

    for closing_div in closing_divs:
        try:
            container = closing_div
            for _ in range(6):
                if not container:
                    break
                title_link = container.select_one("h5 a, h4 a, h3 a, h2 a, .media-body a")
                if title_link:
                    break
                container = container.parent

            if not container:
                continue

            title_link = container.select_one("h5 a, h4 a, h3 a, h2 a, .media-body a, a")
            if not title_link:
                continue

            title = clean_text(title_link.get_text())
            if not title or len(title) < 10 or title in seen:
                continue

            href       = title_link.get("href", "")
            detail_url = href if href.startswith("http") else urljoin(base_url, href)
            seen.add(title)

            closing_date = re.sub(r'(?i)closing\s*', '', clean_text(closing_div.get_text())).strip()
            if closing_date and is_closing_date_expired(closing_date):
                continue

            body_el    = container.select_one("p, .description, small")
            issuing    = clean_text(body_el.get_text()) if body_el else ""
            full_text  = f"{title} {issuing} {province_hint or ''}"
            province   = detect_province(full_text) or province_hint

            results.append({
                "title":             title,
                "description":       issuing,
                "issuing_body":      issuing,
                "province":          province,
                "municipality":      detect_municipality(full_text, province),
                "town":              detect_town(full_text, province),
                "industry_category": detect_industry(full_text),
                "closing_date":      closing_date,
                "posted_date":       "",
                "source_url":        detail_url,
                "document_url":      None,
                "source_site":       "easytenders.co.za",
                "reference_number":  "",
                "contact_info":      "",
                "content_hash":      make_content_hash(title, detail_url),
            })
        except Exception as e:
            logger.debug(f"EasyTenders item error: {e}")

    return results


def _scrape_all_provinces(_playwright) -> List[Dict]:
    """Scrape EasyTenders for all 9 provinces in one browser session."""
    browser = _playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage",
              "--ignore-certificate-errors", "--disable-web-security"],
    )
    context = browser.new_context(
        ignore_https_errors=True,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
    )
    page    = browser.new_page()
    all_results: List[Dict] = []
    seen_hashes: set = set()

    for province_name, province_slug in EASYTENDERS_PROVINCES:
        url = f"https://easytenders.co.za/tenders-in/{province_slug}"
        try:
            logger.info(f"[EASYTENDERS] Scraping {province_name}...")
            page.goto(url, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

            tenders = _extract_tenders(page.content(), url, province_name)
            new = 0
            for t in tenders:
                if t["content_hash"] not in seen_hashes:
                    seen_hashes.add(t["content_hash"])
                    all_results.append(t)
                    new += 1
            logger.info(f"[EASYTENDERS] {province_name}: {new} tenders")
        except Exception as e:
            logger.warning(f"[EASYTENDERS] {province_name} failed: {e}")

    browser.close()
    logger.info(f"[EASYTENDERS] Total: {len(all_results)} tenders across all provinces")
    return all_results


async def scrape_js_source(source: Dict) -> List[Dict]:
    try:
        return await run_sync(_scrape_all_provinces)
    except Exception as e:
        logger.error(f"[EASYTENDERS] Scrape failed: {e}")
        return []


async def scrape() -> List[Dict]:
    return await scrape_js_source(JS_SOURCES[0])