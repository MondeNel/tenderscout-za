"""
scraper/sites/js_scraper.py — JavaScript-Rendered Aggregator Scrapers
=======================================================================
Scrapes nationwide tender aggregators that require Playwright for
client‑side rendering.

Sites handled:
    - EasyTenders (all 9 provinces)
    - OnlineTenders (province‑specific pages)
    - sa‑tenders.co.za (national)

Exports:
    scrape_all_js_sources() → List[Dict]  (called by engine.run_scraper)
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.base_scraper import BaseTenderScraper
from scraper.playwright_runner import get_page_content
from scraper.utils import (
    clean_text,
    detect_industry,
    detect_province,
    detect_municipality,
    detect_town,
    make_content_hash,
)

logger = logging.getLogger(__name__)

# =============================================================================
# SITE CONFIGURATIONS
# =============================================================================
# Each entry defines a site with province‑specific URLs.
# province_hint is used when the site doesn't explicitly state the province.
# =============================================================================

JS_SITES: List[Dict[str, Any]] = [
    {
        "name": "EasyTenders",
        "base_url": "https://easytenders.co.za",
        "province_urls": {
            "Eastern Cape":  "https://easytenders.co.za/tenders-in/eastern-cape",
            "Free State":    "https://easytenders.co.za/tenders-in/free-state",
            "Gauteng":       "https://easytenders.co.za/tenders-in/gauteng",
            "KwaZulu-Natal": "https://easytenders.co.za/tenders-in/kwazulu-natal",
            "Limpopo":       "https://easytenders.co.za/tenders-in/limpopo",
            "Mpumalanga":    "https://easytenders.co.za/tenders-in/mpumalanga",
            "North West":    "https://easytenders.co.za/tenders-in/north-west",
            "Northern Cape": "https://easytenders.co.za/tenders-in/northern-cape",
            "Western Cape":  "https://easytenders.co.za/tenders-in/western-cape",
        },
        "selectors": {
            "container":  "div.grid > div, article, .tender-item, [class*='tender']",
            "title":      "h2, h3, .font-semibold, .tender-title, a",
            "link":       "a[href]",
            "closing":    ".closing-date, .date, time, .text-sm, [class*='closing']",
            "issuer":     ".issuer, .department, .authority, .text-gray-600",
        },
    },
    {
        "name": "OnlineTenders",
        "base_url": "https://www.onlinetenders.co.za",
        "province_urls": {
            "Eastern Cape":  "https://www.onlinetenders.co.za/tenders/eastern-cape",
            "Free State":    "https://www.onlinetenders.co.za/tenders/free-state",
            "Gauteng":       "https://www.onlinetenders.co.za/tenders/gauteng",
            "KwaZulu-Natal": "https://www.onlinetenders.co.za/tenders/kwazulu-natal",
            "Limpopo":       "https://www.onlinetenders.co.za/tenders/limpopo",
            "Mpumalanga":    "https://www.onlinetenders.co.za/tenders/mpumalanga",
            "North West":    "https://www.onlinetenders.co.za/tenders/north-west",
            "Northern Cape": "https://www.onlinetenders.co.za/tenders/northern-cape",
            "Western Cape":  "https://www.onlinetenders.co.za/tenders/western-cape",
        },
        "selectors": {
            "container":  "div.row > div, .tender-listing, .search-result, table tr",
            "title":      "h4, h5, .tender-title, a strong, td:first-child a",
            "link":       "a[href*='tender'], a[href*='/tenders/']",
            "closing":    ".closing, .date, .deadline, td:nth-child(3), time",
            "issuer":     ".issuer, .authority, .dept, td:nth-child(2)",
        },
    },
    {
        "name": "sa-tenders.co.za",
        "base_url": "https://sa-tenders.co.za",
        "province_urls": {
            "National": "https://sa-tenders.co.za/tenders",
        },
        "selectors": {
            "container":  "div.listing, article.post, div.tender-listing, .card",
            "title":      "h2, h3, .entry-title, .listing-title, a",
            "link":       "a[href*='tender'], a.listing-link, h2 a",
            "closing":    ".closing-date, .deadline, .date, .posted-date",
            "issuer":     ".issuer, .department, .authority, .listing-meta",
        },
    },
]


# =============================================================================
# SCRAPER CLASS
# =============================================================================

class JSAggregatorScraper(BaseTenderScraper):
    """
    Scrapes a JavaScript‑rendered aggregator by visiting each province
    page with Playwright, parsing the HTML, and returning engine‑ready dicts.
    """

    def __init__(self, site_config: Dict[str, Any]) -> None:
        super().__init__(
            name=site_config["name"],
            province=None,               # will be set per tender
            base_url=site_config["base_url"],
        )
        self.config = site_config
        self.province_urls = site_config.get("province_urls", {})

    # ------------------------------------------------------------------
    # Main scraping entry point
    # ------------------------------------------------------------------
    async def scrape(self) -> List[Dict[str, Any]]:
        all_tenders: List[Dict[str, Any]] = []

        async def _scrape_province(province: str, url: str) -> None:
            logger.info(f"  → {self.name} / {province}")
            try:
                html = await get_page_content(
                    url,
                    wait_for="networkidle",
                    timeout=45000,
                    ignore_https_errors=True,   # some aggregators have cert issues
                )
                if not html:
                    logger.warning(f"Empty page for {province}")
                    return
                raw = await self._parse(html, province)
                if raw:
                    all_tenders.extend(self.finalize_batch(raw, province))
            except Exception as exc:
                logger.error(f"Failed {self.name}/{province}: {exc}")

        # Run all provinces concurrently (capped by Playwright semaphore)
        tasks = [_scrape_province(p, u) for p, u in self.province_urls.items()]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"📦 {self.name}: total {len(all_tenders)} tenders")
        return all_tenders

    # ------------------------------------------------------------------
    # HTML parser (per province page)
    # ------------------------------------------------------------------
    async def _parse(self, html: str, province_hint: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        sel  = self.config["selectors"]

        items = soup.select(sel["container"])
        if not items:
            items = soup.select("a[href]")   # fallback: all links

        raw: List[Dict[str, Any]] = []
        base = self.base_url

        for item in items:
            try:
                title_el = item.select_one(sel["title"])
                if not title_el:
                    continue
                title = clean_text(title_el.get_text())
                if not title or len(title) < 8:
                    continue

                link_el = item.select_one(sel["link"])
                href = link_el.get("href", "") if link_el else ""
                full_url = href if href.startswith("http") else urljoin(base, href)

                closing_el = item.select_one(sel["closing"])
                closing_date = clean_text(closing_el.get_text()) if closing_el else ""

                issuer_el = item.select_one(sel["issuer"])
                issuing_body = clean_text(issuer_el.get_text()) if issuer_el else ""

                raw.append({
                    "title":        title,
                    "url":          full_url,
                    "closing_date": closing_date,
                    "issuing_body": issuing_body,
                    "province_hint": province_hint,
                })
            except Exception as e:
                logger.debug(f"Item parse error: {e}")
                continue

        soup.decompose()
        return raw

    # ------------------------------------------------------------------
    # Standardisation (engine‑compatible output)
    # ------------------------------------------------------------------
    def finalize_batch(
        self,
        items: List[Dict[str, Any]],
        province_hint: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        standardized: List[Dict[str, Any]] = []

        for item in items:
            title        = item.get("title", "")
            closing_date = item.get("closing_date", "")
            source_url   = item.get("url", "")
            issuing_body = item.get("issuing_body", "")
            hint         = item.get("province_hint", province_hint)

            hash_val = make_content_hash(title, source_url, closing_date)

            # Geographic detection
            province     = detect_province(f"{title} {issuing_body}") or hint or ""
            municipality = detect_municipality(f"{title} {issuing_body}", province) or ""
            town         = detect_town(f"{title} {issuing_body}", province) or ""
            industry     = detect_industry(f"{title} {issuing_body}")

            standardized.append({
                "title":             title,
                "description":       issuing_body,
                "issuing_body":      issuing_body,
                "province":          province,
                "municipality":      municipality,
                "town":              town,
                "industry_category": industry,
                "closing_date":      closing_date,
                "posted_date":       "",
                "source_url":        source_url,
                "document_url":      None,
                "source_site":       self.base_url.replace("https://", "").replace("www.", ""),
                "reference_number":  "",
                "contact_info":      "",
                "content_hash":      hash_val,
            })

        return standardized


# =============================================================================
# PUBLIC ENTRY POINT – called by engine.run_scraper()
# =============================================================================

async def scrape_all_js_sources() -> List[Dict[str, Any]]:
    """
    Scrape all configured JS aggregators.
    Returns a flat list of engine‑compatible tender dicts.
    """
    logger.info("[JS_SCRAPER] Starting all JS sources...")
    all_tenders: List[Dict[str, Any]] = []

    for cfg in JS_SITES:
        scraper = JSAggregatorScraper(cfg)
        try:
            result = await scraper.scrape()
            all_tenders.extend(result)
        except Exception as exc:
            logger.error(f"[JS_SCRAPER] {cfg['name']} failed: {exc}")

    logger.info(f"[JS_SCRAPER] Total: {len(all_tenders)} tenders from JS sources")
    return all_tenders