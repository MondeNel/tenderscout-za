"""
scraper/sites/etenders.py — eTenders Portal (National) Scraper
===============================================================
Uses Playwright with interaction logic to handle JS‑heavy content,
then standardises output to match the engine's expected schema.
"""

import logging
from typing import Any, Dict, List

from scraper.base_scraper import BaseTenderScraper
from scraper.playwright_runner import interact_and_scrape
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
# CONSTANTS
# =============================================================================

ETENDERS_URL  = "https://www.etenders.gov.za/Home/opportunities?id=1"
ETENDERS_BASE = "https://www.etenders.gov.za"


class ETenderScraper(BaseTenderScraper):
    """
    Scraper for the national eTenders portal.

    Overrides scrape() to use interactive Playwright (clicking, selecting,
    dismissing modals) rather than a simple page fetch.
    """

    def __init__(self) -> None:
        super().__init__(
            name="eTenders Portal (National)",
            province=None,          # Province is detected per tender
            base_url=ETENDERS_URL,
        )

    # ------------------------------------------------------------------
    # Interaction logic (used by interact_and_scrape)
    # ------------------------------------------------------------------
    @staticmethod
    def _interaction_actions() -> List[Dict[str, Any]]:
        """Playwright actions that prepare the fully rendered tender table."""
        return [
            # 1. Remove Bootstrap modals and backdrops
            {
                "type": "eval",
                "js": (
                    "document.querySelectorAll('.modal, .modal-backdrop')"
                    ".forEach(el => el.remove());"
                    "document.body.classList.remove('modal-open');"
                ),
            },
            # 2. Wait for network to settle
            {"type": "waitnet"},
            # 3. Let the DataTable finish initialising
            {"type": "wait", "ms": 2000},
            # 4. Set page size to 100 to minimise pagination
            {
                "type": "select",
                "selector": "select[name$='_length']",
                "value": "100",
            },
            # 5. Wait again for the table to reload
            {"type": "waitnet"},
        ]

    # ------------------------------------------------------------------
    # Main scraping entry point (overrides BaseTenderScraper.scrape)
    # ------------------------------------------------------------------
    async def scrape(self) -> List[Dict[str, Any]]:
        """
        Run the eTenders scraper: interact → render → parse → standardise.
        """
        try:
            logger.info(f"🚀 Starting {self.name}")
            html = await interact_and_scrape(
                url=ETENDERS_URL,
                actions=self._interaction_actions(),
                timeout=90_000,
                ignore_https_errors=True,   # eTenders has a mis‑configured cert
            )
            if not html:
                logger.error(f"❌ No HTML returned for {self.name}")
                return []

            raw = await self.parse(html)
            if not raw:
                logger.warning(f"⚠️ No tenders extracted from {self.name}")
                return []

            return self.finalize_batch(raw)

        except Exception as exc:
            logger.error(f"💥 {self.name} failed: {exc}", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # HTML parser – extracts raw rows from the DataTable
    # ------------------------------------------------------------------
    async def parse(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse the eTenders DataTable (id="tenderList") and return raw dicts.
        """
        from bs4 import BeautifulSoup

        soup   = BeautifulSoup(html, "lxml")
        table = soup.find("table", id="tenderList")

        if not table:
            logger.error("❌ Table 'tenderList' not found – check interaction logic")
            soup.decompose()
            return []

        rows = table.find_all("tr", class_=["odd", "even"])
        raw  = []

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            try:
                # Columns: 0=expand, 1=reference, 2=description (title+link), 3=closing, 4=category
                title_cell = cells[2]
                link_tag   = title_cell.find("a")
                title      = clean_text(title_cell.get_text())
                reference  = clean_text(cells[1].get_text())
                closing    = clean_text(cells[3].get_text())
                raw_url    = link_tag.get("href", "") if link_tag else ""

                raw.append({
                    "title":        title,
                    "reference":    reference,
                    "closing_date": closing,
                    "url":          raw_url,
                })
            except Exception as e:
                logger.debug(f"Skipping row in {self.name}: {e}")
                continue

        soup.decompose()
        logger.info(f"✨ {self.name}: extracted {len(raw)} raw rows")
        return raw

    # ------------------------------------------------------------------
    # Final standardization – aligns output with engine's Tender schema
    # ------------------------------------------------------------------
    def finalize_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert raw extraction dicts to the same format expected by
        the engine's upsert_tenders() and the Tender database model.
        """
        standardized: List[Dict[str, Any]] = []

        for item in items:
            title        = clean_text(item.get("title", ""))
            closing_date = item.get("closing_date", "")
            raw_url      = item.get("url", "")

            # Build absolute URL
            if raw_url.startswith("/"):
                source_url = f"{ETENDERS_BASE}{raw_url}"
            elif raw_url.startswith("http"):
                source_url = raw_url
            else:
                source_url = ETENDERS_URL   # fallback to listing

            # Content hash includes closing_date to avoid re‑issue dedup bug
            hash_val = make_content_hash(title, source_url, closing_date)

            # Geographic / industry detection
            province     = detect_province(title) or ""
            municipality = detect_municipality(title, province) or ""
            town         = detect_town(title, province) or ""
            industry     = detect_industry(title)

            standardized.append({
                "title":             title,
                "description":       "",
                "issuing_body":      "National Government (eTenders)",
                "province":          province,
                "municipality":      municipality,
                "town":              town,
                "industry_category": industry,
                "closing_date":      closing_date,
                "posted_date":       "",
                "source_url":        source_url,
                "document_url":      None,
                "source_site":       "etenders.gov.za",
                "reference_number":  item.get("reference", ""),
                "contact_info":      "",
                "content_hash":      hash_val,
            })

        logger.info(f"📦 {self.name}: standardized {len(standardized)} tenders")
        return standardized


# =============================================================================
# PUBLIC ENTRY POINT – called by engine.run_scraper()
# =============================================================================

async def scrape_etenders() -> List[Dict[str, Any]]:
    """Create a fresh scraper instance and run it."""
    scraper = ETenderScraper()
    return await scraper.scrape()