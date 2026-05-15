"""
scraper/sites/sa_tenders.py — Static Aggregator Scraper (Legacy)
==================================================================
Handles only static-HTML aggregator sites that do NOT require Playwright.
JS‑rendered aggregators (EasyTenders, OnlineTenders, sa‑tenders.co.za)
are now scraped by js_scraper.py (Phase 4).

This module is kept for backward compatibility with the engine's Phase 3,
which iterates over aggregator-type sources with js_required=False.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from scraper.utils import (
    clean_text,
    detect_industry,
    detect_municipality,
    detect_province,
    detect_town,
    get_headers,
    is_closing_date_expired,
    make_content_hash,
)

logger = logging.getLogger(__name__)

# =============================================================================
# STATIC AGGREGATOR CONFIGURATIONS
# =============================================================================
# Only sites that can be scraped with plain HTTP requests belong here.
# js_required must be False — otherwise the engine will skip them in Phase 3.

AGGREGATORS: List[Dict] = [
    {
        "name":          "TenderAlerts",
        "url":           "https://tenderalerts.co.za",
        "province_hint": None,
        "js_required":   False,
        "item_sel":      "div.tender-item, div.alert-item, article, .listing-item",
        "title_sel":     "h3, h4, .alert-title, .title, a",
        "link_sel":      "a[href*='tender'], a.btn, .read-more",
        "closing_sel":   ".closing, .deadline, .date, .expiry",
        "body_sel":      ".issuer, .authority, .organization, .source",
        "next_sel":      "a.next, .pagination a",
    },
]


# =============================================================================
# DATE PARSING
# =============================================================================

def _parse_date_flexible(text: str) -> str:
    """Convert various date formats to DD/MM/YYYY."""
    if not text:
        return ""
    text = clean_text(text)

    # ISO: 2026-01-15
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"

    # "15 Jan 2026" or "15 January 2026"
    m = re.search(
        r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|'
        r'January|February|March|April|May|June|July|August|September|'
        r'October|November|December)\s+(\d{4})',
        text, re.IGNORECASE,
    )
    if m:
        try:
            month_map = {
                "jan": 1, "january": 1, "feb": 2, "february": 2,
                "mar": 3, "march": 3, "apr": 4, "april": 4,
                "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
                "aug": 8, "august": 8, "sep": 9, "september": 9,
                "oct": 10, "october": 10, "nov": 11, "november": 11,
                "dec": 12, "december": 12,
            }
            month_lower = m.group(2).lower()
            month_num = next((v for k, v in month_map.items() if k in month_lower), None)
            if month_num:
                return f"{int(m.group(1)):02d}/{month_num:02d}/{m.group(3)}"
        except Exception:
            pass

    # DD/MM/YYYY
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"

    return ""


# =============================================================================
# HTML PARSER
# =============================================================================

def _parse_items(html: str, source: Dict, page_url: str) -> List[Dict]:
    """Parse tender items from HTML and return engine‑compatible dicts."""
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    items = soup.select(source.get("item_sel", ""))
    if not items:
        logger.debug(f"[SA_TENDERS] No items with '{source['item_sel']}' — fallback to links")
        items = soup.select("a[href]")

    if not items:
        logger.warning(f"[SA_TENDERS] No items found for {source['name']}")
        return []

    province_hint = source.get("province_hint")
    parsed = urlparse(page_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    seen_titles = set()
    results = []

    for item in items:
        try:
            # Title
            title_el = item.select_one(source["title_sel"]) if source.get("title_sel") else item
            if not title_el:
                continue
            title = clean_text(title_el.get_text())
            if not title or len(title) < 8:
                continue
            title_lower = title.lower()
            if title_lower in seen_titles:
                continue
            seen_titles.add(title_lower)

            # Link
            link_el = item.select_one(source["link_sel"]) if source.get("link_sel") else item
            href = link_el.get("href", "") if link_el else ""
            detail_url = href if href.startswith("http") else urljoin(base, href) if href else page_url

            # Closing date
            closing_el = item.select_one(source["closing_sel"]) if source.get("closing_sel") else None
            closing_raw = clean_text(closing_el.get_text()) if closing_el else ""
            closing_date = _parse_date_flexible(closing_raw)
            if closing_date and is_closing_date_expired(closing_date):
                logger.debug(f"[SA_TENDERS] Skipping expired: {title[:50]}")
                continue

            # Issuing body
            body_el = item.select_one(source["body_sel"]) if source.get("body_sel") else None
            issuing_body = clean_text(body_el.get_text()) if body_el else ""

            detection_text = f"{title} {issuing_body}"
            item_text = clean_text(item.get_text())
            if len(item_text) > len(detection_text):
                detection_text = item_text[:500]

            province = province_hint or detect_province(detection_text) or ""
            municipality = detect_municipality(detection_text, province) or ""
            town = detect_town(detection_text, province) or ""

            content_hash = make_content_hash(title, detail_url, closing_date)

            results.append({
                "title":             title,
                "description":       issuing_body or f"Tender listed on {source['name']}",
                "issuing_body":      issuing_body,
                "province":          province,
                "municipality":      municipality,
                "town":              town,
                "industry_category": detect_industry(detection_text),
                "closing_date":      closing_date,
                "posted_date":       "",
                "source_url":        detail_url,
                "document_url":      None,
                "source_site":       parsed.netloc.replace("www.", ""),
                "reference_number":  "",
                "contact_info":      "",
                "content_hash":      content_hash,
                "lat":               None,
                "lng":               None,
            })
        except Exception as e:
            logger.debug(f"[SA_TENDERS] Item parse error: {e}")

    return results


# =============================================================================
# STATIC AGGREGATOR SCRAPER (Pagination)
# =============================================================================

async def scrape_aggregator(
    client: httpx.AsyncClient,
    source: Dict,
    max_pages: int = 5,
) -> List[Dict]:
    """Scrape a static aggregator with pagination."""
    all_results = []
    current_url = source["url"]
    pages_scraped = 0

    while pages_scraped < max_pages:
        try:
            response = await client.get(current_url)
            if response.status_code != 200:
                logger.warning(f"{source['name']} returned {response.status_code}")
                break

            page_results = _parse_items(response.text, source, current_url)
            all_results.extend(page_results)
            pages_scraped += 1
            logger.debug(f"[SA_TENDERS] Page {pages_scraped}: {len(page_results)} tenders")

            soup = BeautifulSoup(response.text, "lxml")
            next_sel = source.get("next_sel", 'a.next, a[rel="next"]')
            next_link = soup.select_one(next_sel)
            if next_link and next_link.get("href"):
                next_href = next_link["href"]
                if next_href.startswith("#") or next_href.startswith("javascript:"):
                    break
                current_url = urljoin(current_url, next_href)
                await asyncio.sleep(1.0)
            else:
                break
        except Exception as e:
            logger.error(f"{source['name']} page {pages_scraped + 1} failed: {e}")
            break

    logger.info(f"[SA_TENDERS] {source['name']}: {len(all_results)} tenders ({pages_scraped} pages)")
    return all_results


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def scrape() -> List[Dict]:
    """Scrape all static aggregators (called by engine Phase 3)."""
    all_results = []
    async with httpx.AsyncClient(
        timeout=30,
        headers=get_headers(),
        follow_redirects=True,
        verify=False,
    ) as client:
        for source in AGGREGATORS:
            try:
                results = await scrape_aggregator(client, source)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"[SA_TENDERS] {source['name']} failed: {e}")
    return all_results