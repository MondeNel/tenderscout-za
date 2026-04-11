import httpx
from bs4 import BeautifulSoup
from scraper.utils import make_content_hash, detect_industry, detect_province, clean_text, get_headers
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)
BASE_URL = "https://tenderbulletins.co.za"


async def scrape() -> List[Dict]:
    results = []
    try:
        async with httpx.AsyncClient(timeout=20, headers=get_headers(), follow_redirects=True) as client:
            response = await client.get(BASE_URL)
            if response.status_code != 200:
                logger.warning(f"tenderbulletins returned {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, "lxml")
            rows = soup.select("table tbody tr, div.tender-row, article.post")

            for row in rows:
                try:
                    title_el = row.select_one("h2, h3, .title, a")
                    if not title_el:
                        continue
                    title = clean_text(title_el.get_text())
                    if not title or len(title) < 8:
                        continue

                    link_el = row.select_one("a[href]")
                    url = link_el["href"] if link_el else BASE_URL
                    if url.startswith("/"):
                        url = f"{BASE_URL}{url}"

                    cells = row.select("td")
                    description = clean_text(cells[1].get_text()) if len(cells) > 1 else ""
                    closing_date = clean_text(cells[-1].get_text()) if cells else ""
                    issuing_body = clean_text(cells[0].get_text()) if cells else ""

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
                        "source_site": "tenderbulletins.co.za",
                        "reference_number": "",
                        "contact_info": "",
                        "content_hash": make_content_hash(title, url),
                    })
                except Exception as e:
                    logger.error(f"tenderbulletins item error: {e}")

    except Exception as e:
        logger.error(f"tenderbulletins scrape failed: {e}")

    logger.info(f"tenderbulletins.co.za: {len(results)} tenders")
    return results
