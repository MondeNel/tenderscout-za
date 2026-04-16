import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scraper.utils import (
    make_content_hash, detect_industry, detect_province, detect_municipality,
    detect_town, clean_text, get_headers, is_closing_date_expired
)
from typing import List, Dict, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

AGGREGATORS = [
    {
        "name": "sa-tenders.co.za",
        "url": "https://sa-tenders.co.za/tenders",
        "province_hint": None,
        "selectors": {
            "item": "div.tender-item, article, div.listing-item, table tr",
            "title": "h2, h3, .tender-title, a",
            "link": "a[href]",
            "description": "p, .description",
            "closing_date": ".date, .closing-date, time",
            "issuing_body": ".department, .issuer, .authority",
            "document_link": "a[href*='.pdf'], a[href*='.doc']",
        },
    },
    {
        "name": "eTenders Portal (National)",
        "url": "https://www.etenders.gov.za",
        "province_hint": None,
        "selectors": {
            "item": "div.tender-list-item, div.tender-item, tr.tender-row",
            "title": "h3, h4, .tender-title, a",
            "link": "a[href]",
            "description": "p, .description, .tender-description",
            "closing_date": ".closing-date, .tender-closing, time",
            "issuing_body": ".issuer, .department, .authority",
            "document_link": "a[href*='.pdf'], a[href*='.doc']",
        },
    },
    {
        "name": "EasyTenders (Northern Cape)",
        "url": "https://easytenders.co.za/tenders-in/northern-cape",
        "province_hint": "Northern Cape",
        "selectors": {
            "item": "div.tender-item, article, div.listing-item, tr",
            "title": "h2, h3, h4, .tender-title, a",
            "link": "a[href]",
            "description": "p, .description, .tender-description",
            "closing_date": ".date, .closing-date, .tender-closing, time",
            "issuing_body": ".issuer, .department, .tender-authority",
            "document_link": "a[href*='.pdf'], a[href*='.doc']",
        },
    },
    {
        "name": "OnlineTenders (Northern Cape)",
        "url": "https://www.onlinetenders.co.za/tenders/northern-cape",
        "province_hint": "Northern Cape",
        "selectors": {
            "item": "div.tender-item, div.listing-item, article, tr",
            "title": "h2, h3, .tender-title, a",
            "link": "a[href]",
            "description": "p, .description",
            "closing_date": ".date, .closing-date, time",
            "issuing_body": ".issuer, .authority, .department",
            "document_link": "a[href*='.pdf'], a[href*='.doc']",
        },
    },
    {
        "name": "TenderAlerts",
        "url": "https://tenderalerts.co.za",
        "province_hint": None,
        "selectors": {
            "item": "div.tender-item, div.post, article, tr",
            "title": "h2, h3, h4, .tender-title, a",
            "link": "a[href]",
            "description": "p, .entry-content, .description",
            "closing_date": ".date, .closing, time",
            "issuing_body": ".issuer, .department, .authority",
            "document_link": "a[href*='.pdf'], a[href*='.doc']",
        },
    },
]

async def scrape_page(client: httpx.AsyncClient, url: str, source: Dict) -> List[Dict]:
    """Scrape a single page (listing or detail) and return tenders."""
    results = []
    try:
        response = await client.get(url)
        if response.status_code != 200:
            logger.warning(f"{source['name']} returned {response.status_code} for {url}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        sel = source["selectors"]
        items = soup.select(sel["item"])

        for item in items:
            try:
                title_el = item.select_one(sel["title"])
                if not title_el:
                    continue
                title = clean_text(title_el.get_text())
                if not title or len(title) < 8:
                    continue

                link_el = item.select_one(sel["link"])
                if link_el and link_el.get("href"):
                    detail_url = link_el["href"]
                    if detail_url.startswith("/"):
                        detail_url = urljoin(url, detail_url)
                else:
                    detail_url = url

                desc_el = item.select_one(sel["description"]) if sel.get("description") else None
                description = clean_text(desc_el.get_text()) if desc_el else ""

                date_el = item.select_one(sel["closing_date"]) if sel.get("closing_date") else None
                closing_date = clean_text(date_el.get_text()) if date_el else ""

                body_el = item.select_one(sel["issuing_body"]) if sel.get("issuing_body") else None
                issuing_body = clean_text(body_el.get_text()) if body_el else ""

                doc_el = item.select_one(sel["document_link"]) if sel.get("document_link") else None
                document_url = doc_el.get("href") if doc_el else None
                if document_url and document_url.startswith("/"):
                    document_url = urljoin(url, document_url)

                if closing_date and is_closing_date_expired(closing_date):
                    continue

                full_text = f"{title} {description} {issuing_body}"
                province = source.get("province_hint") or detect_province(full_text)
                municipality = detect_municipality(full_text, province)
                town = detect_town(full_text, province)

                results.append({
                    "title": title,
                    "description": description,
                    "issuing_body": issuing_body,
                    "province": province,
                    "municipality": municipality,
                    "town": town,
                    "industry_category": detect_industry(full_text),
                    "closing_date": closing_date,
                    "posted_date": "",
                    "source_url": detail_url,
                    "document_url": document_url,
                    "source_site": source["url"].split("/")[2],
                    "reference_number": "",
                    "contact_info": "",
                    "content_hash": make_content_hash(title, detail_url),
                })
            except Exception as e:
                logger.error(f"{source['name']} item error: {e}")

    except Exception as e:
        logger.exception(f"{source['name']} page scrape failed: {url} - {e}")

    return results

async def scrape_listing_with_pagination(client: httpx.AsyncClient, source: Dict, max_pages: int = 3) -> List[Dict]:
    """Scrape listing pages with pagination up to max_pages."""
    all_results = []
    current_url = source["url"]
    pages_scraped = 0

    while current_url and pages_scraped < max_pages:
        logger.debug(f"Scraping page {pages_scraped+1}: {current_url}")
        page_results = await scrape_page(client, current_url, source)
        all_results.extend(page_results)
        pages_scraped += 1

        # Find next page link
        try:
            response = await client.get(current_url)
            soup = BeautifulSoup(response.text, "lxml")
            next_link = soup.select_one('a.next, a[rel="next"], a:contains("Next")')
            if next_link and next_link.get("href"):
                next_url = next_link["href"]
                current_url = urljoin(current_url, next_url)
            else:
                break
        except Exception:
            break
        # Polite delay between pages
        await asyncio.sleep(1)

    return all_results

async def scrape_aggregator(client: httpx.AsyncClient, source: Dict) -> List[Dict]:
    return await scrape_listing_with_pagination(client, source, max_pages=3)

async def scrape_detail(client: httpx.AsyncClient, url: str, source: Dict) -> List[Dict]:
    """Scrape a single detail page URL (used by engine)."""
    return await scrape_page(client, url, source)

async def scrape() -> List[Dict]:
    """Scrape all aggregators (listing pages)."""
    all_results = []
    async with httpx.AsyncClient(timeout=20, headers=get_headers(), follow_redirects=True, verify=True) as client:
        for source in AGGREGATORS:
            results = await scrape_aggregator(client, source)
            all_results.extend(results)
            logger.info(f"{source['name']}: {len(results)} tenders")
    return all_results