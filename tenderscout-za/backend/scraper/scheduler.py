"""
scraper/scheduler.py — Automated Scraper Scheduler
====================================================
Schedules the tender scraping pipeline using APScheduler.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from scraper.engine import run_scraper

logger = logging.getLogger(__name__)

def _parse_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, str(default))
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"[SCHEDULER] Invalid {key}={raw!r} — using default {default}")
        return default

SCRAPE_CRON_HOURS     = os.getenv("SCRAPE_CRON_HOURS", "2,8,14,20")
SCRAPE_INTERVAL_SEC   = _parse_int_env("SCRAPE_INTERVAL_SECONDS", 0)
RUN_ON_START          = os.getenv("SCRAPE_RUN_ON_START", "true").lower() == "true"
SHUTDOWN_WAIT_TIMEOUT = _parse_int_env("SCRAPER_SHUTDOWN_TIMEOUT", 30)

scheduler: Optional[AsyncIOScheduler] = None
_last_run_at:   Optional[datetime] = None
_last_run_new:  Optional[int] = None
_last_run_ok:   Optional[bool] = None
_is_running:    bool = False

async def _scraper_job():
    global _last_run_at, _last_run_new, _last_run_ok, _is_running
    if _is_running:
        logger.warning("[SCHEDULER] Skipping run — previous scrape still in progress")
        return
    _is_running = True
    started_at = datetime.now(timezone.utc)
    try:
        new_tenders = await run_scraper()
        _last_run_new = new_tenders
        _last_run_ok  = True
        logger.info(f"[SCHEDULER] Run complete — {new_tenders} new tenders")
    except Exception as e:
        _last_run_ok  = False
        _last_run_new = 0
        logger.error(f"[SCHEDULER] Run failed: {e}")
    finally:
        _last_run_at = started_at
        _is_running  = False

def start_scheduler() -> None:
    global scheduler
    if scheduler is not None and scheduler.running:
        return
    scheduler = AsyncIOScheduler(timezone="UTC")
    if SCRAPE_INTERVAL_SEC > 0:
        trigger = IntervalTrigger(seconds=SCRAPE_INTERVAL_SEC)
        logger.info(f"[SCHEDULER] Interval trigger: every {SCRAPE_INTERVAL_SEC}s")
    else:
        trigger = CronTrigger(hour=SCRAPE_CRON_HOURS, minute="0", timezone="UTC")
        logger.info(f"[SCHEDULER] Cron trigger: hours={SCRAPE_CRON_HOURS} UTC")
    scheduler.add_job(
        _scraper_job, trigger=trigger, id="scrape_all_sites",
        name="Scrape all tender sources", replace_existing=True,
        max_instances=1, coalesce=True,
    )
    scheduler.start()
    logger.info("[SCHEDULER] Started")
    if RUN_ON_START:
        logger.info("[SCHEDULER] Triggering immediate startup scrape")
        asyncio.get_event_loop().create_task(_scraper_job())

def stop_scheduler() -> None:
    global scheduler
    if scheduler is None or not scheduler.running:
        scheduler = None
        return
    logger.info(f"[SCHEDULER] Shutting down (timeout={SHUTDOWN_WAIT_TIMEOUT}s)...")
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(scheduler.shutdown, True)
        try:
            future.result(timeout=SHUTDOWN_WAIT_TIMEOUT)
            logger.info("[SCHEDULER] Stopped cleanly")
        except concurrent.futures.TimeoutError:
            logger.warning(f"[SCHEDULER] Shutdown timed out — forcing stop")
            scheduler.shutdown(wait=False)
    scheduler = None

def get_scheduler_status() -> dict:
    jobs = []
    if scheduler is not None:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id, "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
    return {
        "running": scheduler is not None and scheduler.running,
        "scrape_in_progress": _is_running,
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
        "last_run_new_tenders": _last_run_new,
        "last_run_ok": _last_run_ok,
        "jobs": jobs,
        "config": {
            "mode": "interval" if SCRAPE_INTERVAL_SEC > 0 else "cron",
            "cron_hours": SCRAPE_CRON_HOURS,
            "interval_seconds": SCRAPE_INTERVAL_SEC or None,
            "run_on_start": RUN_ON_START,
        },
    }