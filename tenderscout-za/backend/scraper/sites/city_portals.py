import httpx
from bs4 import BeautifulSoup
from scraper.utils import make_content_hash, detect_industry, detect_province, clean_text, get_headers, is_likely_expired
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

CITY_PORTALS = [
    {
        "name": "City of Cape Town",
        "url": "https://www.capetown.gov.za/work/tenders",
        "province": "Western Cape",
        "town": "Cape Town",
        "scrape_type": "links"
    },
    {
        "name": "City of Johannesburg",
        "url": "https://www.joburg.org.za/work_/Pages/Tenders/Tenders.aspx",
        "province": "Gauteng",
        "town": "Johannesburg",
        "scrape_type": "links"
    },
    {
        "name": "City of Tshwane",
        "url": "https://www.tshwane.gov.za/Sites/Departments/Financial-Services/Pages/Tenders.aspx",
        "province": "Gauteng",
        "town": "Pretoria",
        "scrape_type": "links"
    },
    {
        "name": "City of Ekurhuleni",
        "url": "https://www.ekurhuleni.gov.za/tenders",
        "province": "Gauteng",
        "town": "Ekurhuleni",
        "scrape_type": "links"
    },
    {
        "name": "eThekwini Municipality",
        "url": "https://www.durban.gov.za/City_Services/finance/SCM/Pages/Quotations-Tenders.aspx",
        "province": "KwaZulu-Natal",
        "town": "Durban",
        "scrape_type": "links"
    },
    {
        "name": "Buffalo City Metro",
        "url": "https://www.buffalocity.gov.za/tenders",
        "province": "Eastern Cape",
        "town": "East London",
        "scrape_type": "links"
    },
    {
        "name": "Mangaung Municipality",
        "url": "https://www.mangaung.co.za/tenders",
        "province": "Free State",
        "town": "Bloemfontein",
        "scrape_type": "links"
    },
    {
        "name": "Nelson Mandela Bay",
        "url": "https://www.nelsonmandelabay.gov.za/tenders",
        "province": "Eastern Cape",
        "town": "Gqeberha",
        "scrape_type": "links"
    },
    {
        "name": "Siyathemba Municipality",
        "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/tenders",
        "province": "Northern Cape",
        "town": "Prieska",
        "scrape_type": "phoca"
    },
    {
        "name": "Siyathemba Municipality (Quotations)",
        "url": "https://www.siyathemba.gov.za/index.php/tenders-quotations/quotations",
        "province": "Northern Cape",
        "town": "Prieska",
        "scrape_type": "phoca"
    },
    {
        "name": "Northern Cape DEDAT",
        "url": "http://www.northern-cape.gov.za/dedat/index.php?option=com_phocadownload&view=category&id=14&Itemid=824",
        "province": "Northern Cape",
        "town": "Kimberley",
        "scrape_type": "phoca"
    },
]

TENDER_KEYWORDS = ["tender", "bid", "rfq", "rfp", "quotation", "procurement", "supply", "contract"]


async def scrape_phoca(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """
    Scrapes Joomla sites using the Phoca Download component.
    Tenders are listed as downloadable PDF links with title attributes.
    """
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")

        # Phoca Download renders file links in spans/divs with class 'phocadownload'
        # or as plain anchor tags with .pdf hrefs and title attributes
        candidates = (
            soup.select("div.phocadownload a, span.phocadownload a") +
            soup.select("a[href*='.pdf'], a[href*='download'], a[title]")
        )

        seen = set()
        for link in candidates:
            href = link.get("href", "")
            title = clean_text(link.get("title") or link.get_text())

            if not title or len(title) < 5:
                continue

            # Skip nav/menu links
            nav_words = ["home", "about", "contact", "login", "forgot", "gallery",
                         "council", "notice", "vacancy", "vacancies", "budget",
                         "annual report", "financial statement", "organogram"]
            if any(n in title.lower() for n in nav_words):
                continue

            full_url = href if href.startswith("http") else f"https://www.siyathemba.gov.za{href}"

            # Deduplicate by title
            if title in seen:
                continue
            seen.add(title)

            # Skip likely expired tenders (old year in URL or title)
            if is_likely_expired(title, full_url if full_url.startswith('http') else city['url']):
                continue

            listing_url = city["url"]
            # document_url: direct link to the file if available, else None
            doc_url = None
            if href and href.startswith("http") and any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".zip"]):
                doc_url = href
            elif href and any(ext in href.lower() for ext in [".pdf", ".doc", ".docx"]):
                doc_url = full_url if full_url.startswith("http") else None

            results.append({
                "title": title,
                "description": f"Tender/Bid document from {city['name']}. Click to view all current tenders on their website.",
                "issuing_body": city["name"],
                "province": city["province"],
                "town": city["town"],
                "industry_category": detect_industry(title),
                "closing_date": "",
                "posted_date": "",
                "source_url": listing_url,
                "document_url": doc_url,
                "source_site": city["url"].split("/")[2],
                "reference_number": "",
                "contact_info": "",
                "content_hash": make_content_hash(title, listing_url),
            })

    except Exception as e:
        logger.error(f"{city['name']} (phoca) scrape failed: {e}")

    return results


async def scrape_links(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    """
    Generic link scraper for standard municipal tender pages.
    """
    results = []
    try:
        response = await client.get(city["url"])
        if response.status_code != 200:
            logger.warning(f"{city['name']} returned {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        base = city["url"].split("/")[2]

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = clean_text(link.get_text())

            if not text or len(text) < 10:
                continue
            if not any(kw in text.lower() or kw in href.lower() for kw in TENDER_KEYWORDS):
                continue

            full_url = href if href.startswith("http") else f"https://{base}{href}"

            is_download = any(x in full_url for x in ['download=', '.pdf', '.doc', '.zip'])
            # source_url = stable listing page always
            # document_url = direct deep link to the tender page or file
            doc_url = full_url if full_url != city["url"] else None

            results.append({
                "title": text,
                "description": f"Tender from {city['name']}. Visit their website to view full tender details.",
                "issuing_body": city["name"],
                "province": city["province"],
                "town": city["town"],
                "industry_category": detect_industry(text),
                "closing_date": "",
                "posted_date": "",
                "source_url": city["url"],
                "document_url": doc_url,
                "source_site": base,
                "reference_number": "",
                "contact_info": "",
                "content_hash": make_content_hash(text, city["url"]),
            })

    except Exception as e:
        logger.error(f"{city['name']} scrape failed: {e}")

    return results


async def scrape_city(client: httpx.AsyncClient, city: Dict) -> List[Dict]:
    if city.get("scrape_type") == "phoca":
        return await scrape_phoca(client, city)
    return await scrape_links(client, city)


async def scrape() -> List[Dict]:
    results = []
    async with httpx.AsyncClient(
        timeout=20,
        headers=get_headers(),
        follow_redirects=True,
        verify=False
    ) as client:
        for city in CITY_PORTALS:
            city_results = await scrape_city(client, city)
            results.extend(city_results)
            logger.info(f"{city['name']}: {len(city_results)} tenders")
    return results
