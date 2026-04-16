import httpx
from bs4 import BeautifulSoup
from scraper.utils import make_content_hash, detect_industry, detect_province, detect_municipality, detect_town, clean_text, get_headers
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

SOURCES = [
    {
        "name": "tenderbulletins.co.za",
        "url": "https://tenderbulletins.co.za",
        "province_hint": None,   # national — detect from text
        "selectors": {
            "row": "table tbody tr, div.tender-row, article.post",
            "title": "h2, h3, .title, a",
            "link": "a[href]",
            "description": "td:nth-child(2), .description",
            "closing_date": "td:last-child, .closing-date",
            "issuing_body": "td:first-child, .issuer",
        },
    },
    {
        "name": "tendersbulletins.co.za (Northern Cape)",
        "url": "https://tendersbulletins.co.za/location/northern-cape",
        "province_hint": "Northern Cape",   # URL confirms province
        "selectors": {
            "row": "div.tender-item, article, tr",
            "title": "h2, h3, .title, a",
            "link": "a[href]",
            "description": "p, .description",
            "closing_date": ".date, .closing-date, time",
            "issuing_body": ".issuer, .department, .authority",
        },
    },
]


async def scrape_source(client: httpx.AsyncClient, source: Dict) -> List[Dict]:
    results = []
    try:
        response = await client.get(source["url"])
        if response.status_code != 200:
            logger.warning(f"{source['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        sel = source["selectors"]
        rows = soup.select(sel["row"])

        for row in rows:
            try:
                title_el = row.select_one(sel["title"])
                if not title_el:
                    continue
                title = clean_text(title_el.get_text())
                if not title or len(title) < 8:
                    continue

                link_el = row.select_one(sel["link"])
                if link_el and link_el.get("href"):
                    url = link_el["href"]
                    if url.startswith("/"):
                        url = source["url"].rstrip("/") + url
                else:
                    url = source["url"]

                # Helper that works for both td-selector and class-selector columns
                def extract(selector):
                    el = row.select_one(selector) if selector else None
                    return clean_text(el.get_text()) if el else ""

                description  = extract(sel.get("description"))
                closing_date = extract(sel.get("closing_date"))
                issuing_body = extract(sel.get("issuing_body"))

                full_text = f"{title} {description} {issuing_body}"

                # Province: hint wins; fall back to text detection
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
                    "source_url": url,
                    "source_site": source["url"].split("/")[2],
                    "reference_number": "",
                    "contact_info": "",
                    "content_hash": make_content_hash(title, url),
                })
            except Exception as e:
                logger.error(f"{source['name']} item error: {e}")

    except Exception as e:
        logger.error(f"{source['name']} scrape failed: {e}")

    logger.info(f"{source['name']}: {len(results)} tenders")
    return results


async def scrape() -> List[Dict]:
    all_results = []
    async with httpx.AsyncClient(timeout=20, headers=get_headers(), follow_redirects=True) as client:
        for source in SOURCES:
            results = await scrape_source(client, source)
            all_results.extend(results)
    return all_results