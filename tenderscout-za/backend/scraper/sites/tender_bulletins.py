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

# All bulletin sources were unreachable (DNS failures) and have been removed.
# If new working domains are found, add them here.
SOURCES: List[Dict] = []


def _parse_row(row, base_url: str, source: Dict) -> Optional[Dict]:
    sel = source["selectors"]

    title_el = row.select_one(sel["title"])
    if not title_el:
        return None
    title = clean_text(title_el.get_text())
    if not title or len(title) < 8:
        return None

    link_el = row.select_one(sel["link"])
    if link_el and link_el.get("href"):
        detail_url = link_el["href"]
        if not detail_url.startswith("http"):
            detail_url = urljoin(base_url, detail_url)
    else:
        detail_url = base_url

    def _extract(selector: str) -> str:
        if not selector:
            return ""
        el = row.select_one(selector)
        return clean_text(el.get_text()) if el else ""

    description  = _extract(sel.get("description", ""))
    closing_date = _extract(sel.get("closing_date", ""))
    issuing_body = _extract(sel.get("issuing_body", ""))

    doc_el = row.select_one(sel.get("document_link", "")) if sel.get("document_link") else None
    document_url = doc_el.get("href") if doc_el else None
    if document_url and not document_url.startswith("http"):
        document_url = urljoin(base_url, document_url)

    if closing_date and is_closing_date_expired(closing_date):
        return None

    full_text = f"{title} {description} {issuing_body}"
    province = source.get("province_hint") or detect_province(full_text)
    municipality = detect_municipality(full_text, province)
    town = detect_town(full_text, province)

    return {
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
    }


async def scrape_page(client: httpx.AsyncClient, url: str, source: Dict) -> List[Dict]:
    results = []
    try:
        response = await client.get(url)
        if response.status_code != 200:
            logger.warning(f"{source['name']} returned {response.status_code} for {url}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        rows = soup.select(source["selectors"]["row"])

        for row in rows:
            try:
                parsed = _parse_row(row, url, source)
                if parsed:
                    results.append(parsed)
            except Exception as e:
                logger.error(f"{source['name']} row parse error: {e}")

    except Exception as e:
        logger.exception(f"{source['name']} page scrape failed [{url}]: {e}")

    return results


async def scrape_source(client: httpx.AsyncClient, source: Dict, max_pages: int = 3) -> List[Dict]:
    all_results = []
    current_url = source["url"]

    for page_num in range(max_pages):
        page_results = await scrape_page(client, current_url, source)
        all_results.extend(page_results)

        try:
            response = await client.get(current_url)
            soup = BeautifulSoup(response.text, "lxml")
            next_link = soup.select_one('a.next, a[rel="next"]')
            if next_link and next_link.get("href"):
                current_url = urljoin(current_url, next_link["href"])
                await asyncio.sleep(1.0)
            else:
                break
        except Exception:
            break

    return all_results


async def scrape_detail(client: httpx.AsyncClient, url: str, source: Dict) -> List[Dict]:
    return await scrape_page(client, url, source)


async def scrape() -> List[Dict]:
    if not SOURCES:
        logger.info("No bulletin sources configured — skipping")
        return []

    all_results = []
    async with httpx.AsyncClient(
        timeout=20, headers=get_headers(), follow_redirects=True, verify=False
    ) as client:
        for source in SOURCES:
            try:
                results = await scrape_source(client, source)
                all_results.extend(results)
                logger.info(f"{source['name']}: {len(results)} tenders")
            except Exception as e:
                logger.error(f"{source['name']}: scrape failed — {e}")
    return all_results