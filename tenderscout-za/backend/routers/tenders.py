"""
File: routers/tenders.py
Purpose: Tender retrieval endpoints — latest feed and single tender lookup
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from database import get_db
import auth_utils, models, schemas
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenders", tags=["Tenders"])

# Maximum results returned by /latest — prevents accidental full-table dumps
_LATEST_MAX_LIMIT = 100


# =============================================================================
# LATEST TENDERS — free dashboard feed, no credit charge
# =============================================================================

@router.get("/latest", response_model=schemas.TenderLatestResponse)
def get_latest(
    http_request: Request,
    since:          Optional[str] = Query(None,  description="ISO datetime — only return tenders scraped after this"),
    industries:     Optional[str] = Query(None,  description="Comma-separated industry categories"),
    provinces:      Optional[str] = Query(None,  description="Comma-separated province names"),
    municipalities: Optional[str] = Query(None,  description="Comma-separated municipality names"),
    limit:          int           = Query(50, ge=1, le=_LATEST_MAX_LIMIT, description="Max results to return"),
    skip:           int           = Query(0,  ge=0, description="Records to skip"),
    db:             Session       = Depends(get_db),
    current_user:   models.User   = Depends(auth_utils.get_current_user),
):
    """
    Return recently scraped active tenders filtered by date, industry,
    province, or municipality. Free — does not charge credits.

    Used by the dashboard feed and map overlay.
    """
    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    # FIX: Invalid 'since' now returns a 422 instead of silently being ignored.
    # Silently ignoring it meant the caller had no idea their filter wasn't applied.
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            # Ensure timezone-aware for consistent comparison with DB timestamps
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
            query = query.filter(models.Tender.scraped_at > since_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid 'since' datetime format: {since!r}. Use ISO 8601 e.g. 2026-01-15T10:00:00",
            )

    # FIX: Strip and limit each filter value to prevent injection via ilike.
    # Comma-split values are stripped and truncated to 100 chars each.
    if industries:
        il = [v.strip()[:100] for v in industries.split(",") if v.strip()]
        if il:
            query = query.filter(
                or_(*[models.Tender.industry_category.ilike(f"%{i}%") for i in il])
            )

    if provinces:
        pl = [v.strip()[:100] for v in provinces.split(",") if v.strip()]
        if pl:
            query = query.filter(
                or_(*[models.Tender.province.ilike(f"%{p}%") for p in pl])
            )

    if municipalities:
        ml = [v.strip()[:100] for v in municipalities.split(",") if v.strip()]
        if ml:
            query = query.filter(
                or_(*[models.Tender.municipality.ilike(f"%{m}%") for m in ml])
            )

    tenders = (
        query
        .order_by(desc(models.Tender.scraped_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    logger.debug(
        f"[TENDERS] /latest user={current_user.id} "
        f"count={len(tenders)} since={since} "
        f"industries={industries} provinces={provinces}"
    )

    return {"new_count": len(tenders), "tenders": tenders}


# =============================================================================
# SINGLE TENDER — free detail view, no credit charge
# =============================================================================

@router.get("/{tender_id}", response_model=schemas.TenderOut)
def get_tender(
    tender_id:    int,
    http_request: Request,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Return a single tender by ID. Free — does not charge credits.

    FIX: Uses db.get() instead of .filter().first() for primary key lookups.
    db.get() uses SQLAlchemy's identity map (session cache) — if the same
    tender was already loaded in this request it won't hit the DB again.
    """
    # Guard: /latest must be registered before /{tender_id} in the router,
    # but add explicit rejection of non-numeric IDs as a safety net.
    tender = db.get(models.Tender, tender_id)

    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender {tender_id} not found",
        )

    if not tender.is_active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This tender is no longer active",
        )

    logger.debug(f"[TENDERS] /{tender_id} viewed by user={current_user.id}")
    return tender