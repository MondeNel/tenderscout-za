import logging
import httpx
from sqlalchemy.orm import Session
from database import SessionLocal
import models
from scraper.utils import get_headers
from scraper.crawler import run_crawler
from scraper.sites import city_portals, sa_tenders, tender_bulletins
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Build unified source registry
ALL_SOURCES = []
ALL_SOURCES.extend([{**c, "source_type": "city"} for c in city_portals.CITY_PORTALS])
ALL_SOURCES.extend([{**a, "source_type": "aggregator"} for a in sa_tenders.AGGREGATORS])
ALL_SOURCES.extend([{**s, "source_type": "bulletin"} for s in tender_bulletins.SOURCES])

def get_source_by_name(name: str) -> Optional[Dict]:
    for src in ALL_SOURCES:
        if src["name"] == name:
            return src
    return None

async def scrape_detail_url(client: httpx.AsyncClient, url: str, source: Dict) -> List[Dict]:
    """Scrape a single detail page URL using the appropriate site scraper."""
    src_type = source.get("source_type")
    if src_type == "city":
        # Use city_portals.scrape_city with overridden URL
        city_override = {**source, "url": url}
        return await city_portals.scrape_city(client, city_override)
    elif src_type == "aggregator":
        return await sa_tenders.scrape_detail(client, url, source)
    elif src_type == "bulletin":
        return await tender_bulletins.scrape_detail(client, url, source)
    else:
        logger.warning(f"Unknown source type for {source['name']}")
        return []

async def scrape_listing_source(client: httpx.AsyncClient, source: Dict) -> List[Dict]:
    """Scrape a listing page (used for initial seeding or full refresh)."""
    src_type = source.get("source_type")
    if src_type == "city":
        return await city_portals.scrape_city(client, source)
    elif src_type == "aggregator":
        return await sa_tenders.scrape_aggregator(client, source)
    elif src_type == "bulletin":
        return await tender_bulletins.scrape_source(client, source)
    return []

def upsert_tenders(db: Session, tenders: List[Dict]) -> int:
    new_count = 0
    for t in tenders:
        if not t.get("content_hash"):
            continue
        exists = db.query(models.Tender).filter(models.Tender.content_hash == t["content_hash"]).first()
        if not exists:
            db.add(models.Tender(**t))
            new_count += 1
    db.commit()
    return new_count

async def run_scraper():
    logger.info("[ENGINE] Starting scrape cycle (crawler + scraper)")
    db = SessionLocal()
    total_new = 0

    # Phase 1: Crawler discovers new URLs (city portals only; aggregators have their own pagination)
    crawl_index = await run_crawler(db)

    # Phase 2: Process discovered URLs
    async with httpx.AsyncClient(timeout=30, headers=get_headers(), follow_redirects=True, verify=True) as client:
        for site_name, urls in crawl_index.items():
            if not urls:
                continue
            source = get_source_by_name(site_name)
            if not source:
                logger.warning(f"No source config for {site_name}, skipping")
                continue
            scraped_tenders = []
            for entry in urls:
                url = entry["url"]
                try:
                    tenders = await scrape_detail_url(client, url, source)
                    scraped_tenders.extend(tenders)
                except Exception as e:
                    logger.exception(f"Error scraping {url}: {e}")
            if scraped_tenders:
                new = upsert_tenders(db, scraped_tenders)
                total_new += new
                logger.info(f"{site_name}: {len(scraped_tenders)} tenders extracted, {new} new")

    # Phase 3: Also run listing scrapers for aggregators that don't have crawler entries
    # (They rely on pagination, not BFS crawling)
    async with httpx.AsyncClient(timeout=30, headers=get_headers(), follow_redirects=True, verify=True) as client:
        for source in ALL_SOURCES:
            if source["source_type"] in ("aggregator", "bulletin"):
                try:
                    listing_results = await scrape_listing_source(client, source)
                    if listing_results:
                        new = upsert_tenders(db, listing_results)
                        total_new += new
                        logger.info(f"{source['name']} (listing): {len(listing_results)} tenders, {new} new")
                except Exception as e:
                    logger.exception(f"Error scraping listing {source['name']}: {e}")

    db.close()
    logger.info(f"[ENGINE] Cycle complete — {total_new} new tenders")
    return total_new