"""
Aggregator scrapers.
Currently, reliable HTML aggregators are empty - SA-Tenders requires Playwright.
eTenders API is blocked/changed.
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# No working HTML aggregators currently
AGGREGATORS: List[Dict] = []


async def scrape() -> List[Dict]:
    """Scrape all aggregators."""
    logger.info("No aggregators configured - skipping")
    return []