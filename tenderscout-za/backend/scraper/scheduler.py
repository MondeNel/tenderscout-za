from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from scraper.engine import run_scraper
import os
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler():
    interval = int(os.getenv("SCRAPE_INTERVAL_SECONDS", 60))
    scheduler.add_job(
        run_scraper,
        trigger=IntervalTrigger(seconds=interval),
        id="scrape_all_sites",
        name="Scrape all tender sites",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"[SCHEDULER] Started - scraping every {interval}s")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("[SCHEDULER] Stopped")
