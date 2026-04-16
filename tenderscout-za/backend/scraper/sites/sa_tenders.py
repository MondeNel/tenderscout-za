import httpx
from bs4 import BeautifulSoup
from scraper.utils import make_content_hash, detect_industry, detect_province, detect_municipality, detect_town, clean_text, get_headers
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Aggregator sources
# ---------------------------------------------------------------------------
# For aggregators we don't know the province from the URL structure, so we
# rely on detect_province(full_text) — but we also carry a `province` hint
# where the URL makes it unambiguous (e.g. a Northern Cape-specific page).
# ---------------------------------------------------------------------------

AGGREGATORS = [
    {
        "name": "sa-tenders.co.za",
        "url": "https://sa-tenders.co.za/tenders",
        "province_hint": None,  # national aggregator — detect from text
        "selectors": {
            "item": "div.tender-item, article, div.listing-item, table tr",
            "title": "h2, h3, .tender-title, a",
            "link": "a[href]",
            "description": "p, .description",
            "closing_date": ".date, .closing-date, time",
            "issuing_body": ".department, .issuer, .authority",
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
        },
    },
    {
        "name": "EasyTenders (Northern Cape)",
        "url": "https://easytenders.co.za/tenders-in/northern-cape",
        "province_hint": "Northern Cape",   # URL confirms province
        "selectors": {
            "item": "div.tender-item, article, div.listing-item, tr",
            "title": "h2, h3, h4, .tender-title, a",
            "link": "a[href]",
            "description": "p, .description, .tender-description",
            "closing_date": ".date, .closing-date, .tender-closing, time",
            "issuing_body": ".issuer, .department, .tender-authority",
        },
    },
    {
        "name": "OnlineTenders (Northern Cape)",
        "url": "https://www.onlinetenders.co.za/tenders/northern-cape",
        "province_hint": "Northern Cape",   # URL confirms province
        "selectors": {
            "item": "div.tender-item, div.listing-item, article, tr",
            "title": "h2, h3, .tender-title, a",
            "link": "a[href]",
            "description": "p, .description",
            "closing_date": ".date, .closing-date, time",
            "issuing_body": ".issuer, .authority, .department",
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
        },
    },
]


async def scrape_aggregator(client: httpx.AsyncClient, source: Dict) -> List[Dict]:
    results = []
    try:
        response = await client.get(source["url"])
        if response.status_code != 200:
            logger.warning(f"{source['name']} returned {response.status_code}")
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
                    url = link_el["href"]
                    if url.startswith("/"):
                        url = source["url"].rstrip("/") + url
                else:
                    url = source["url"]

                desc_el = item.select_one(sel["description"]) if sel.get("description") else None
                description = clean_text(desc_el.get_text()) if desc_el else ""

                date_el = item.select_one(sel["closing_date"]) if sel.get("closing_date") else None
                closing_date = clean_text(date_el.get_text()) if date_el else ""

                body_el = item.select_one(sel["issuing_body"]) if sel.get("issuing_body") else None
                issuing_body = clean_text(body_el.get_text()) if body_el else ""

                full_text = f"{title} {description} {issuing_body}"

                # Province: use hint if available (URL is unambiguous),
                # otherwise detect from text
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
        for source in AGGREGATORS:
            results = await scrape_aggregator(client, source)
            all_results.extend(results)
    return all_results