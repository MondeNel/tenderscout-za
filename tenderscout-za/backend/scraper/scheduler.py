"""
scheduler.py — Automated Scraper Scheduler
===========================================
Schedules and runs the tender scraping pipeline at regular intervals using APScheduler.

Features:
    - Configurable interval via SCRAPE_INTERVAL_SECONDS environment variable
    - Prevents overlapping runs (max_instances=1)
    - Graceful shutdown handling
    - Comprehensive logging

Usage:
    from scheduler import start_scheduler, stop_scheduler
    
    # Start the scheduler
    start_scheduler()
    
    # Keep the application running
    import asyncio
    asyncio.get_event_loop().run_forever()
    
    # Stop gracefully on shutdown
    stop_scheduler()

Environment Variables:
    SCRAPE_INTERVAL_SECONDS: Interval between scraper runs (default: 3600 = 1 hour)
"""

import asyncio
import os
import logging
import signal
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from scraper.engine import run_scraper

logger = logging.getLogger(__name__)

# =============================================================================
# SCHEDULER CONFIGURATION
# =============================================================================

# Default to 6 hours for production (was 1 hour — more reasonable for 60+ sites)
DEFAULT_INTERVAL_SECONDS = 21600  # 6 hours

# Alternative: Use cron trigger for specific times
# DEFAULT_CRON_HOUR = 6  # 6 AM daily
# DEFAULT_CRON_MINUTE = 0

scheduler: Optional[AsyncIOScheduler] = None


# =============================================================================
# JOB WRAPPER WITH ERROR HANDLING
# =============================================================================

async def _scraper_job_wrapper():
    """
    Wrapper for the scraper job with error handling and logging.
    
    Prevents scheduler from crashing if the scraper encounters an error.
    """
    logger.info("[SCHEDULER] ═══════════════════════════════════════════════════")
    logger.info("[SCHEDULER] Starting scheduled scraper run...")
    logger.info("[SCHEDULER] ═══════════════════════════════════════════════════")
    
    try:
        new_tenders = await run_scraper()
        logger.info(f"[SCHEDULER] Scheduled run complete — {new_tenders} new tenders added")
    except Exception as e:
        logger.error(f"[SCHEDULER] Scheduled run failed: {e}", exc_info=True)
    
    logger.info("[SCHEDULER] ═══════════════════════════════════════════════════")


# =============================================================================
# SCHEDULER LIFECYCLE
# =============================================================================

def start_scheduler(use_cron: bool = False) -> AsyncIOScheduler:
    """
    Start the APScheduler with the scraper job.
    
    Args:
        use_cron: If True, use cron trigger (daily at specific time).
                  If False, use interval trigger (every N seconds).
    
    Returns:
        The configured AsyncIOScheduler instance
        
    Environment Variables:
        SCRAPE_INTERVAL_SECONDS: Interval in seconds (for interval trigger)
        SCRAPE_CRON_HOUR: Hour of day for cron trigger (0-23, default: 6)
        SCRAPE_CRON_MINUTE: Minute for cron trigger (0-59, default: 0)
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("[SCHEDULER] Scheduler already running")
        return scheduler
    
    scheduler = AsyncIOScheduler()
    
    if use_cron:
        # Use cron trigger — run at specific time daily
        hour = int(os.getenv("SCRAPE_CRON_HOUR", "6"))
        minute = int(os.getenv("SCRAPE_CRON_MINUTE", "0"))
        
        scheduler.add_job(
            _scraper_job_wrapper,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="scrape_all_sites",
            name="Scrape all tender sites (daily)",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
            coalesce=True,     # If missed, run once when possible
        )
        logger.info(f"[SCHEDULER] Started — running daily at {hour:02d}:{minute:02d}")
    else:
        # Use interval trigger — run every N seconds
        interval = int(os.getenv("SCRAPE_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS)))
        
        scheduler.add_job(
            _scraper_job_wrapper,
            trigger=IntervalTrigger(seconds=interval),
            id="scrape_all_sites",
            name="Scrape all tender sites",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
            coalesce=True,     # If missed, run once when possible
        )
        
        hours = interval // 3600
        minutes = (interval % 3600) // 60
        logger.info(f"[SCHEDULER] Started — scraping every {interval}s ({hours}h {minutes}m)")
    
    scheduler.start()
    return scheduler


def stop_scheduler(wait: bool = True):
    """
    Stop the scheduler gracefully.
    
    Args:
        wait: If True, wait for running jobs to complete
    """
    global scheduler
    
    if scheduler is None:
        logger.warning("[SCHEDULER] No scheduler running")
        return
    
    logger.info("[SCHEDULER] Shutting down...")
    scheduler.shutdown(wait=wait)
    scheduler = None
    logger.info("[SCHEDULER] Stopped")


def get_scheduler_status() -> dict:
    """
    Get the current status of the scheduler.
    
    Returns:
        Dictionary with scheduler status information
    """
    global scheduler
    
    if scheduler is None:
        return {"running": False, "jobs": []}
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    
    return {
        "running": scheduler.running,
        "jobs": jobs,
    }


# =============================================================================
# SIGNAL HANDLERS (for graceful shutdown)
# =============================================================================

def _setup_signal_handlers():
    """
    Set up signal handlers for graceful shutdown on SIGINT/SIGTERM.
    """
    loop = asyncio.get_event_loop()
    
    def handle_shutdown():
        logger.info("[SCHEDULER] Received shutdown signal")
        stop_scheduler(wait=False)
        loop.stop()
    
    try:
        loop.add_signal_handler(signal.SIGINT, handle_shutdown)
        loop.add_signal_handler(signal.SIGTERM, handle_shutdown)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass


# =============================================================================
# MAIN ENTRY POINT (for running scheduler standalone)
# =============================================================================

async def main():
    """
    Main entry point for running the scheduler as a standalone service.
    """
    # Set up signal handlers for graceful shutdown
    _setup_signal_handlers()
    
    # Start the scheduler
    start_scheduler()
    
    # Print status
    status = get_scheduler_status()
    logger.info(f"[SCHEDULER] Status: {status}")
    
    # Keep the event loop running
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("[SCHEDULER] Keyboard interrupt received")
    finally:
        stop_scheduler()


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # Run the scheduler
    asyncio.run(main())