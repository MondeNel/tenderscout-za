"""
scraper/scheduler.py — Automated Scraper Scheduler
====================================================
Schedules the tender scraping pipeline using APScheduler.

Design:
  - Runs immediately on startup (first-run), then on cron schedule
  - Prevents overlapping runs via max_instances=1
  - Graceful shutdown with configurable wait timeout
  - Tracks last run time and result for /admin/scheduler-status

Environment Variables:
    SCRAPE_CRON_HOURS   Comma-separated hours to run daily (default: "2,8,14,20")
    SCRAPE_INTERVAL_SECONDS  Alternative: run every N seconds (overrides cron)
    SCRAPE_RUN_ON_START Run a scrape immediately at startup (default: true)
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

# =============================================================================
# CONFIGURATION
# =============================================================================

def _parse_int_env(key: str, default: int) -> int:
    """Safe env var parsing — logs warning and uses default on invalid value."""
    raw = os.getenv(key, str(default))
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"[SCHEDULER] Invalid {key}={raw!r} — using default {default}")
        return default


# Cron hours: run at 02:00, 08:00, 14:00, 20:00 by default
# This gives 4 runs/day at fixed, predictable times regardless of restart time
SCRAPE_CRON_HOURS     = os.getenv("SCRAPE_CRON_HOURS", "2,8,14,20")
SCRAPE_INTERVAL_SEC   = _parse_int_env("SCRAPE_INTERVAL_SECONDS", 0)  # 0 = use cron
RUN_ON_START          = os.getenv("SCRAPE_RUN_ON_START", "true").lower() == "true"
SHUTDOWN_WAIT_TIMEOUT = _parse_int_env("SCRAPER_SHUTDOWN_TIMEOUT", 30)  # seconds

# =============================================================================
# STATE
# =============================================================================

scheduler:      Optional[AsyncIOScheduler] = None
_last_run_at:   Optional[datetime]         = None
_last_run_new:  Optional[int]              = None
_last_run_ok:   Optional[bool]             = None
_is_running:    bool                       = False   # True while a scrape is in progress


# =============================================================================
# JOB WRAPPER
# =============================================================================

async def _scraper_job():
    """
    Wrapped scraper job — catches all exceptions so the scheduler never crashes.
    Updates last-run state for /admin/scheduler-status reporting.
    """
    global _last_run_at, _last_run_new, _last_run_ok, _is_running

    if _is_running:
        logger.warning("[SCHEDULER] Skipping run — previous scrape still in progress")
        return

    _is_running = True
    started_at  = datetime.now(timezone.utc)
    logger.info("[SCHEDULER] ── Scheduled scraper run starting ──")

    try:
        new_tenders  = await run_scraper()
        _last_run_new = new_tenders
        _last_run_ok  = True
        logger.info(f"[SCHEDULER] Run complete — {new_tenders} new tenders")
    except Exception as e:
        _last_run_ok  = False
        _last_run_new = 0
        logger.error(f"[SCHEDULER] Run failed: {e}", exc_info=True)
    finally:
        _last_run_at = started_at
        _is_running  = False


# =============================================================================
# LIFECYCLE
# =============================================================================

def start_scheduler() -> None:
    """
    Start the APScheduler.

    Trigger selection (in priority order):
      1. SCRAPE_INTERVAL_SECONDS > 0 → IntervalTrigger (every N seconds)
      2. Default → CronTrigger at SCRAPE_CRON_HOURS

    FIX: CronTrigger at fixed times is far more predictable for a tender
    platform than interval-from-startup, which drifts every server restart.

    FIX: If SCRAPE_RUN_ON_START=true, fires an immediate background scrape
    so a fresh deployment doesn't sit at 0 tenders until the first schedule.
    """
    global scheduler

    if scheduler is not None and scheduler.running:
        logger.warning("[SCHEDULER] Already running — ignoring start_scheduler() call")
        return

    scheduler = AsyncIOScheduler(timezone="UTC")

    if SCRAPE_INTERVAL_SEC > 0:
        # Interval mode — useful in development
        trigger = IntervalTrigger(seconds=SCRAPE_INTERVAL_SEC)
        hours   = SCRAPE_INTERVAL_SEC // 3600
        mins    = (SCRAPE_INTERVAL_SEC % 3600) // 60
        logger.info(f"[SCHEDULER] Using interval trigger: every {hours}h {mins}m")
    else:
        # FIX: Cron mode — fixed times, not relative to restart
        trigger = CronTrigger(hour=SCRAPE_CRON_HOURS, minute="0", timezone="UTC")
        logger.info(f"[SCHEDULER] Using cron trigger: hours={SCRAPE_CRON_HOURS} UTC")

    scheduler.add_job(
        _scraper_job,
        trigger=trigger,
        id="scrape_all_sites",
        name="Scrape all tender sources",
        replace_existing=True,
        max_instances=1,   # Prevent overlapping runs
        coalesce=True,     # If missed while down, run once on resume
    )

    scheduler.start()
    logger.info("[SCHEDULER] Started")

    # FIX: Immediate first run so new deployments aren't empty until the
    # first cron window fires (potentially hours away)
    if RUN_ON_START:
        logger.info("[SCHEDULER] Triggering immediate startup scrape")
        asyncio.get_event_loop().create_task(_scraper_job())


def stop_scheduler() -> None:
    """
    Stop the scheduler gracefully with a configurable timeout.

    FIX: wait=True with no timeout hangs indefinitely if a scrape is running
    at shutdown. Now waits up to SCRAPER_SHUTDOWN_TIMEOUT seconds then forces.
    """
    global scheduler

    if scheduler is None:
        return

    if not scheduler.running:
        scheduler = None
        return

    logger.info(f"[SCHEDULER] Shutting down (timeout={SHUTDOWN_WAIT_TIMEOUT}s)...")

    try:
        # APScheduler's shutdown(wait=True) blocks the current thread.
        # We give it SHUTDOWN_WAIT_TIMEOUT seconds then force-stop.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(scheduler.shutdown, True)
            try:
                future.result(timeout=SHUTDOWN_WAIT_TIMEOUT)
                logger.info("[SCHEDULER] Stopped cleanly")
            except concurrent.futures.TimeoutError:
                logger.warning(
                    f"[SCHEDULER] Shutdown timed out after {SHUTDOWN_WAIT_TIMEOUT}s "
                    f"— forcing stop"
                )
                scheduler.shutdown(wait=False)
    except Exception as e:
        logger.error(f"[SCHEDULER] Error during shutdown: {e}")
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
    finally:
        scheduler = None


# =============================================================================
# STATUS
# =============================================================================

def get_scheduler_status() -> dict:
    """
    Return current scheduler state for /admin/scheduler-status.

    FIX: Now includes last_run_at, last_run_new_tenders, last_run_ok,
    and is_running — previously only returned job next_run_time.
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
        "running":              scheduler is not None and scheduler.running,
        "scrape_in_progress":   _is_running,
        "last_run_at":          _last_run_at.isoformat() if _last_run_at else None,
        "last_run_new_tenders": _last_run_new,
        "last_run_ok":          _last_run_ok,
        "jobs":                 jobs,
        "config": {
            "mode":             "interval" if SCRAPE_INTERVAL_SEC > 0 else "cron",
            "cron_hours":       SCRAPE_CRON_HOURS,
            "interval_seconds": SCRAPE_INTERVAL_SEC or None,
            "run_on_start":     RUN_ON_START,
        },
    }


# =============================================================================
# STANDALONE ENTRY POINT
# =============================================================================

async def _main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    start_scheduler()
    logger.info(f"[SCHEDULER] Status: {get_scheduler_status()}")
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("[SCHEDULER] Keyboard interrupt")
    finally:
        stop_scheduler()


if __name__ == "__main__":
    asyncio.run(_main())