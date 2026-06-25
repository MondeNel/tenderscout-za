"""
scraper/scheduler.py — Automated Scraper Scheduler
====================================================
Schedules the tender scraping pipeline using APScheduler.

This module provides:

- Automatic, recurring execution of the full scraping pipeline
  (crawling → city portals → aggregators → JS sites).
- Configurable trigger via environment variables:
    * Cron‑based (default): runs at specified UTC hours
    * Interval‑based: runs every N seconds
- Optional immediate run on application startup.
- Safety measures to prevent overlapping runs.
- Monitoring via a status endpoint that reports last run time,
  result counts, and scheduler health.
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


# ------------------------------------------------------------------
# Helper: safely parse integer environment variables with a fallback
# ------------------------------------------------------------------
def _parse_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, str(default))
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"[SCHEDULER] Invalid {key}={raw!r} — using default {default}")
        return default


# ------------------------------------------------------------------
# Configuration (all overridable via .env)
# ------------------------------------------------------------------

# Cron expression: comma‑separated UTC hours (e.g., "2,8,14,20"
# runs at 02:00, 08:00, 14:00, 20:00). Ignored if interval mode.
SCRAPE_CRON_HOURS = os.getenv("SCRAPE_CRON_HOURS", "2,8,14,20")

# If SCRAPE_INTERVAL_SECONDS > 0, interval mode is used instead of cron.
SCRAPE_INTERVAL_SEC = _parse_int_env("SCRAPE_INTERVAL_SECONDS", 0)

# Whether to trigger a scrape immediately when the scheduler starts.
RUN_ON_START = os.getenv("SCRAPE_RUN_ON_START", "true").lower() == "true"

# Maximum seconds to wait for the scheduler to shut down gracefully
# before forcing it to stop.
SHUTDOWN_WAIT_TIMEOUT = _parse_int_env("SCRAPER_SHUTDOWN_TIMEOUT", 30)

# ------------------------------------------------------------------
# Global state – used by the status endpoint and to prevent
# concurrent runs.
# ------------------------------------------------------------------
scheduler: Optional[AsyncIOScheduler] = None
_last_run_at:  Optional[datetime] = None   # when the last run started
_last_run_new: Optional[int]      = None   # new tenders from last run
_last_run_ok:  Optional[bool]     = None   # True if last run succeeded
_is_running:   bool               = False  # guard to prevent overlap


# ------------------------------------------------------------------
# Scraper job (the function executed by the scheduler)
# ------------------------------------------------------------------
async def _scraper_job():
    """
    Wrapper around `run_scraper()` that updates global state and
    enforces a single‑run‑at‑a‑time policy.

    If a scrape is already in progress when the job is triggered
    (e.g., the previous run is taking longer than the schedule
    interval), the new trigger is silently skipped. APScheduler's
    `coalesce=True` and `max_instances=1` provide additional
    protection, but this guard adds a safety net.
    """
    global _last_run_at, _last_run_new, _last_run_ok, _is_running

    # Prevent overlapping runs at the application level
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


# ------------------------------------------------------------------
# Start / Stop lifecycle
# ------------------------------------------------------------------
def start_scheduler() -> None:
    """
    Initialise and start the APScheduler instance.

    - Creates an AsyncIOScheduler (suitable for asyncio apps).
    - Chooses a trigger:
        * IntervalTrigger if SCRAPE_INTERVAL_SECONDS > 0
        * CronTrigger otherwise (using SCRAPE_CRON_HOURS)
    - Adds the _scraper_job with:
        * max_instances=1   → never run two instances of the same job
        * coalesce=True     → if multiple triggers pile up, only keep
                              the latest
    - Starts the scheduler (background task).
    - If RUN_ON_START is true, schedules an immediate scrape via
      asyncio.create_task (non‑blocking).
    """
    global scheduler

    # Avoid creating a second scheduler if one is already running
    if scheduler is not None and scheduler.running:
        return

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Determine which trigger to use
    if SCRAPE_INTERVAL_SEC > 0:
        trigger = IntervalTrigger(seconds=SCRAPE_INTERVAL_SEC)
        logger.info(f"[SCHEDULER] Interval trigger: every {SCRAPE_INTERVAL_SEC}s")
    else:
        trigger = CronTrigger(hour=SCRAPE_CRON_HOURS, minute="0", timezone="UTC")
        logger.info(f"[SCHEDULER] Cron trigger: hours={SCRAPE_CRON_HOURS} UTC")

    # Register the job
    scheduler.add_job(
        _scraper_job,
        trigger=trigger,
        id="scrape_all_sites",
        name="Scrape all tender sources",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Start the scheduler (runs in the background)
    scheduler.start()
    logger.info("[SCHEDULER] Started")

    # Optional immediate first run
    if RUN_ON_START:
        logger.info("[SCHEDULER] Triggering immediate startup scrape")
        # Schedule the job to run as soon as the event loop is ready
        asyncio.get_event_loop().create_task(_scraper_job())


def stop_scheduler() -> None:
    """
    Gracefully shut down the scheduler when the application stops.

    - APScheduler.shutdown(wait=True) blocks until all currently
      executing jobs finish. Because this may block the event loop,
      we run it in a separate thread with a timeout.
    - If the shutdown takes longer than SHUTDOWN_WAIT_TIMEOUT,
      we force‑stop with shutdown(wait=False).
    - After stopping, the global `scheduler` reference is cleared.
    """
    global scheduler

    if scheduler is None or not scheduler.running:
        scheduler = None
        return

    logger.info(f"[SCHEDULER] Shutting down (timeout={SHUTDOWN_WAIT_TIMEOUT}s)...")

    # Run blocking shutdown in a thread to avoid stalling the event loop
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


# ------------------------------------------------------------------
# Status endpoint data
# ------------------------------------------------------------------
def get_scheduler_status() -> dict:
    """
    Return a dictionary with current scheduler health and last‑run
    statistics, suitable for the `/admin/scheduler-status` endpoint.

    Includes:
    - running: whether the scheduler is active
    - scrape_in_progress: whether a job is executing right now
    - last_run_at, last_run_new_tenders, last_run_ok: last run stats
    - jobs: list of registered APScheduler jobs with next run time
    - config: active configuration (mode, cron hours, interval, etc.)
    """
    jobs = []
    if scheduler is not None:
        for job in scheduler.get_jobs():
            jobs.append({
                "id":       job.id,
                "name":     job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })

    return {
        "running":            scheduler is not None and scheduler.running,
        "scrape_in_progress": _is_running,
        "last_run_at":        _last_run_at.isoformat() if _last_run_at else None,
        "last_run_new_tenders": _last_run_new,
        "last_run_ok":        _last_run_ok,
        "jobs":               jobs,
        "config": {
            "mode":             "interval" if SCRAPE_INTERVAL_SEC > 0 else "cron",
            "cron_hours":       SCRAPE_CRON_HOURS,
            "interval_seconds": SCRAPE_INTERVAL_SEC or None,
            "run_on_start":     RUN_ON_START,
        },
    }