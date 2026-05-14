import asyncio
from typing import List, Dict, Any
from scraper.utils import clean_text, detect_industry, make_content_hash, is_closing_date_expired
from scraper.playwright_runner import get_page_content

class BaseTenderScraper:
    def __init__(self, name: str, province: str, base_url: str):
        self.name = name
        self.province = province
        self.base_url = base_url

    async def scrape(self) -> List[Dict[str, Any]]:
        """Main entry point for the engine."""
        print(f"[SCRAPER] Starting {self.name} ({self.province})...")
        html = await get_page_content(self.base_url)
        
        if not html:
            print(f"[ERROR] No content retrieved for {self.name}")
            return []

        raw_tenders = await self.parse(html)
        return self.finalize_batch(raw_tenders)

    async def parse(self, html: str) -> List[Dict[str, Any]]:
        """Override this in child classes to extract specific table data."""
        raise NotImplementedError("Subclasses must implement parse()")

    def finalize_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Standardizes all extracted data using utils.py."""
        finalized = []
        for item in items:
            title = clean_text(item.get("title", "No Title"))
            closing_date = item.get("closing_date", "")

            # Skip expired tenders to keep data fresh
            if closing_date and is_closing_date_expired(closing_date):
                continue

            processed = {
                "title": title,
                "url": item.get("url") or self.base_url,
                "reference": item.get("reference", "N/A"),
                "closing_date": closing_date,
                "issuing_body": self.name,
                "province": self.province,
                "industry": detect_industry(title),
                "hash": make_content_hash(title, item.get("url", self.base_url))
            }
            
            # Use your debug line
            print(f"    Detected: {processed['title'][:50]}... | Body: {processed['issuing_body'][:30]}")
            finalized.append(processed)
        
        return finalized