import asyncio
import logging
from typing import List, Dict
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlencode
from scraper.utils import (
    make_content_hash, detect_industry, detect_province, detect_municipality,
    detect_town, clean_text, is_closing_date_expired
)
import os

logger = logging.getLogger(__name__)

DEBUG_MODE = True
DEBUG_DIR = "debug_html"

if DEBUG_MODE and not os.path.exists(DEBUG_DIR):
    os.makedirs(DEBUG_DIR)

JS_SOURCES = [
    {
        "name": "EasyTenders (Northern Cape)",
        "url": "https://easytenders.co.za/tenders",
        "province_hint": "Northern Cape",
        "query_params": {"province": "northern-cape"},
    },
    # OnlineTenders removed - requires paid subscription to view details
]


def extract_tenders_from_html(html: str, base_url: str, source: Dict) -> List[Dict]:
    """Extract tenders using site-specific logic."""
    soup = BeautifulSoup(html, "lxml")
    results = []
    source_name = source["name"]
    
    if "EasyTenders" in source_name:
        # Find all closing date divs
        closing_divs = soup.select("div.clearfix.closing-date")
        logger.info(f"EasyTenders: Found {len(closing_divs)} closing date divs")
        
        seen_urls = set()
        
        for closing_div in closing_divs:
            try:
                # Find the container with the title link
                container = closing_div
                for _ in range(5):
                    if container and container.name == "div":
                        title_link = container.select_one("h5 a, h4 a, h3 a, a")
                        if title_link:
                            break
                    container = container.parent if container else None
                
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
                desc_el = container.select_one("p, .description")
                description = clean_text(desc_el.get_text()) if desc_el else ""
                body_el = container.select_one(".issuer, .department, .company, small")
                issuing_body = clean_text(body_el.get_text()) if body_el else ""
                
                if closing_date and is_closing_date_expired(closing_date):
                    continue
                
                full_text = f"{title} {description} {issuing_body}"
                province = detect_province(full_text) or source.get("province_hint", "Northern Cape")
                
                results.append({
                    "title": title,
                    "description": description,
                    "issuing_body": issuing_body,
                    "province": province,
                    "municipality": detect_municipality(full_text, province),
                    "town": detect_town(full_text, province),
                    "industry_category": detect_industry(full_text),
                    "closing_date": closing_date,
                    "posted_date": "",
                    "source_url": detail_url,
                    "document_url": None,
                    "source_site": base_url.split("/")[2].replace("www.", ""),
                    "reference_number": "",
                    "contact_info": "",
                    "content_hash": make_content_hash(title, detail_url),
                })
            except Exception as e:
                logger.debug(f"Item parsing error: {e}")
    
    return results


async def scrape_with_playwright(base_url: str, source: Dict) -> List[Dict]:
    """Scrape a JS-rendered page using Playwright."""
    def _sync_scrape():
        results = []
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")
            return results

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--ignore-certificate-errors', '--disable-web-security']
                )
                context = browser.new_context(
                    ignore_https_errors=True,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = context.new_page()

                target_url = base_url
                if "query_params" in source:
                    target_url = f"{base_url}?{urlencode(source['query_params'])}"

                logger.info(f"Navigating to: {target_url}")
                page.goto(target_url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(4000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                
                content = page.content()
                
                if DEBUG_MODE:
                    filename = f"{DEBUG_DIR}/{source['name'].replace(' ', '_')}.html"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(content)

                browser.close()

            results = extract_tenders_from_html(content, base_url, source)

        except Exception as e:
            logger.exception(f"Playwright scrape failed for {source['name']}: {e}")

        return results

    return await asyncio.to_thread(_sync_scrape)


async def scrape_js_source(source: Dict) -> List[Dict]:
    """Scrape a single JS source."""
    return await scrape_with_playwright(source["url"], source)


async def scrape() -> List[Dict]:
    """Scrape all JS-rendered sources."""
    all_results = []
    for source in JS_SOURCES:
        try:
            results = await scrape_js_source(source)
            all_results.extend(results)
            logger.info(f"{source['name']}: {len(results)} tenders")
        except Exception as e:
            logger.error(f"{source['name']}: scrape failed — {e}")
    return all_results