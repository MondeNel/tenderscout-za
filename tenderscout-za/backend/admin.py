"""
Admin endpoints — all require authentication.
Extracted from main.py so main.py stays focused on app wiring only.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

import auth_utils
import models
from database import get_db
from scraper.scheduler import get_scheduler_status

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/scraper-status")
def scraper_status(
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    rows = (
        db.query(models.ScraperStatus)
        .order_by(models.ScraperStatus.last_scraped_at.desc())
        .all()
    )
    return [
        {
            "site":         r.site_name,
            "last_scraped": r.last_scraped_at.isoformat() if r.last_scraped_at else None,
            "result_count": r.last_result_count,
            "is_healthy":   r.is_healthy,
            "last_error":   r.last_error,
        }
        for r in rows
    ]


@router.post("/trigger-scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    current_user:     models.User = Depends(auth_utils.get_current_user),
):
    from scraper.engine import run_scraper
    background_tasks.add_task(run_scraper)
    logger.info(f"[ADMIN] Scrape triggered by user={current_user.id}")
    return {
        "message":   "Scraper triggered in background",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/scheduler-status")
def scheduler_status(
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    return get_scheduler_status()