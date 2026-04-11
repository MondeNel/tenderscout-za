import httpx
from bs4 import BeautifulSoup
from scraper.utils import make_content_hash, detect_industry, detect_province, clean_text, get_headers
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)
BASE_URL = "https://sa-tenders.co.za"


async def scrape() -> List[Dict]:
    results = []
    try:
        async with httpx.AsyncClient(timeout=20, headers=get_headers(), follow_redirects=True) as client:
            response = await client.get(f"{BASE_URL}/tenders")
            if response.status_code != 200:
                logger.warning(f"sa-tenders returned {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, "lxml")
            items = soup.select("div.tender-item, article, div.listing-item, table tr")

            for item in items:
                try:
                    title_el = item.select_one("h2, h3, .tender-title, a")
                    if not title_el:
                        continue
                    title = clean_text(title_el.get_text())
                    if not title or len(title) < 8:
                        continue

                    link_el = item.select_one("a[href]")
                    url = link_el["href"] if link_el else BASE_URL
                    if url.startswith("/"):
                        url = f"{BASE_URL}{url}"

                    desc_el = item.select_one("p, .description")
                    description = clean_text(desc_el.get_text()) if desc_el else ""

                    date_el = item.select_one(".date, .closing-date, time")
                    closing_date = clean_text(date_el.get_text()) if date_el else ""

                    body_el = item.select_one(".department, .issuer, .authority")
                    issuing_body = clean_text(body_el.get_text()) if body_el else ""

                    full_text = f"{title} {description} {issuing_body}"

                    results.append({
                        "title": title,
                        "description": description,
                        "issuing_body": issuing_body,
                        "province": detect_province(full_text),
                        "town": None,
                        "industry_category": detect_industry(full_text),
                        "closing_date": closing_date,
                        "posted_date": "",
                        "source_url": url,
                        "source_site": "sa-tenders.co.za",
                        "reference_number": "",
                        "contact_info": "",
                        "content_hash": make_content_hash(title, url),
                    })
                except Exception as e:
                    logger.error(f"sa-tenders item error: {e}")

    except Exception as e:
        logger.error(f"sa-tenders scrape failed: {e}")

    logger.info(f"sa-tenders.co.za: {len(results)} tenders")
    return results
