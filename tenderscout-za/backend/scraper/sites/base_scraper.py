import asyncio
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin

# Internal imports
from scraper.utils import (
    clean_text, 
    detect_industry, 
    make_content_hash, 
    is_closing_date_expired
)
from scraper.playwright_runner import get_page_content

# Set up logging for this module
logger = logging.getLogger(__name__)

class BaseTenderScraper:
    def __init__(self, name: str, province: str, base_url: str):
        self.name = name
        self.province = province
        self.base_url = base_url

    async def scrape(self) -> List[Dict[str, Any]]:
        """
        Main entry point for the engine.
        Handles the flow from fetching HTML to returning standardized data.
        """
        try:
            logger.info(f"🚀 Starting {self.name} ({self.province})...")
            
            # Fetch content using your Playwright runner
            html = await get_page_content(self.base_url)
            
            if not html:
                logger.error(f"❌ No content retrieved for {self.name}")
                return []

            # Step 1: Extract raw data (to be implemented by child classes)
            raw_tenders = await self.parse(html)
            
            if not raw_tenders:
                logger.warning(f"⚠️ No tenders found on page for {self.name}")
                return []

            # Step 2: Clean, filter, and standardize
            return self.finalize_batch(raw_tenders)

        except Exception as e:
            # Critical Catch: Ensure one site failing doesn't stop the whole engine
            logger.error(f"💥 CRITICAL FAILURE on {self.name}: {str(e)}")
            return []

    async def parse(self, html: str) -> List[Dict[str, Any]]:
        """
        Subclasses MUST override this. 
        This is where Beautiful Soup or Playwright selectors go.
        """
        raise NotImplementedError("Subclasses must implement parse()")

    def finalize_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Standardizes all extracted data. 
        Filters out expired items and ensures data integrity.
        """
        finalized = []
        
        for item in items:
            try:
                title = clean_text(item.get("title", "No Title"))
                closing_date = item.get("closing_date", "")

                # Skip expired tenders to keep your dashboard fresh
                if closing_date and is_closing_date_expired(closing_date):
                    continue

                # Ensure URL is absolute (handles relative links)
                raw_url = item.get("url") or self.base_url
                full_url = urljoin(self.base_url, raw_url)

                processed = {
                    "title": title,
                    "url": full_url,
                    "reference": item.get("reference", "N/A"),
                    "closing_date": closing_date,
                    "issuing_body": self.name,
                    "province": self.province,
                    "industry": detect_industry(title),
                    "hash": make_content_hash(title, full_url)
                }
                
                # Debug feedback
                logger.debug(f"✅ Detected: {processed['title'][:50]}...")
                finalized.append(processed)
                
            except Exception as item_error:
                # If one single tender is malformed, skip it and continue with others
                logger.warning(f"Skipping malformed tender in {self.name}: {item_error}")
                continue
        
        logger.info(f"📦 {self.name}: Successfully processed {len(finalized)} tenders.")
        return finalized