"""
File: routers/tenders.py
Purpose: Tender retrieval endpoints — latest feed and single tender lookup.

This module provides two endpoints for browsing and inspecting tenders:

- GET /tenders/latest   – paginated list of recent tenders, with optional
                         filters (industry, province, municipality, and a
                         "since" timestamp for incremental updates).
- GET /tenders/{id}     – detail view of a single tender by its ID.

Both endpoints require authentication (JWT) via the shared get_current_user
dependency.
"""

import logging

from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from database import get_db
import auth_utils, models, schemas
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenders", tags=["Tenders"])

# Maximum number of tenders that can be requested in one call
_LATEST_MAX_LIMIT = 100


# ------------------------------------------------------------------
# GET /tenders/latest
# ------------------------------------------------------------------
@router.get("/latest", response_model=schemas.TenderLatestResponse)
def get_latest(
    http_request: Request,
    since:          Optional[str] = Query(None),
    industries:     Optional[str] = Query(None),
    provinces:      Optional[str] = Query(None),
    municipalities: Optional[str] = Query(None),
    limit:          int           = Query(50, ge=1, le=_LATEST_MAX_LIMIT),
    skip:           int           = Query(0,  ge=0),
    db:             Session       = Depends(get_db),
    current_user:   models.User   = Depends(auth_utils.get_current_user),
):
    """
    Return a paginated feed of the most recent active tenders.

    Query parameters (all optional):

    - since:          ISO‑8601 datetime string (e.g. "2026-06-25T12:00:00Z").
                      Only tenders scraped *after* this timestamp are returned.
                      This is used by the frontend's live polling to fetch
                      new tenders since the last check.
    - industries:     Comma‑separated list of industry names (ILIKE match).
    - provinces:      Comma‑separated list of province names (ILIKE match).
    - municipalities: Comma‑separated list of municipality names (ILIKE match).
    - limit:          Maximum results per page (default 50, max 100).
    - skip:           Number of results to skip for pagination (offset).

    Response:
    {
      "new_count": <number of results in this page>,
      "tenders":   [ ... TenderOut objects ... ]
    }
    """
    # Base query: only active (open) tenders
    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    # --------------------------------------------------------------
    # "since" filter – incremental updates
    # --------------------------------------------------------------
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            # If the timestamp has no timezone, assume UTC
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
            query = query.filter(models.Tender.scraped_at > since_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid 'since' datetime format: {since!r}",
            )

    # --------------------------------------------------------------
    # Industry filter – split comma‑separated string into a list
    # --------------------------------------------------------------
    if industries:
        # Truncate each value to 100 chars to prevent abuse of the
        # database query length, then build an OR ILIKE chain.
        il = [v.strip()[:100] for v in industries.split(",") if v.strip()]
        if il:
            query = query.filter(
                or_(*[models.Tender.industry_category.ilike(f"%{i}%") for i in il])
            )

    # --------------------------------------------------------------
    # Province filter
    # --------------------------------------------------------------
    if provinces:
        pl = [v.strip()[:100] for v in provinces.split(",") if v.strip()]
        if pl:
            query = query.filter(
                or_(*[models.Tender.province.ilike(f"%{p}%") for p in pl])
            )

    # --------------------------------------------------------------
    # Municipality filter
    # --------------------------------------------------------------
    if municipalities:
        ml = [v.strip()[:100] for v in municipalities.split(",") if v.strip()]
        if ml:
            query = query.filter(
                or_(*[models.Tender.municipality.ilike(f"%{m}%") for m in ml])
            )

    # --------------------------------------------------------------
    # Ordering and pagination
    # --------------------------------------------------------------
    tenders = (
        query
        .order_by(desc(models.Tender.scraped_at))   # newest first
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {"new_count": len(tenders), "tenders": tenders}


# ------------------------------------------------------------------
# GET /tenders/{tender_id}
# ------------------------------------------------------------------
@router.get("/{tender_id}", response_model=schemas.TenderOut)
def get_tender(
    tender_id:    int,
    http_request: Request,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Fetch a single tender by its database primary key.

    Error responses:
    - 404 Not Found: the tender ID does not exist.
    - 410 Gone:     the tender exists but has been marked inactive
                    (e.g., closing date passed, or manually deactivated).

    On success, the full TenderOut representation is returned.
    """
    # Use db.get() for primary key lookup – faster than .filter().first()
    tender = db.get(models.Tender, tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender {tender_id} not found"
        )
    if not tender.is_active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This tender is no longer active"
        )

    logger.debug(f"[TENDERS] /{tender_id} viewed by user={current_user.id}")
    return tender