"""
File: routers/tenders.py
Purpose: Tender retrieval endpoints — latest feed and single tender lookup
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

_LATEST_MAX_LIMIT = 100

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
    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
            query = query.filter(models.Tender.scraped_at > since_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid 'since' datetime format: {since!r}",
            )

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

    return {"new_count": len(tenders), "tenders": tenders}

@router.get("/{tender_id}", response_model=schemas.TenderOut)
def get_tender(
    tender_id:    int,
    http_request: Request,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    tender = db.get(models.Tender, tender_id)
    if not tender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tender {tender_id} not found")
    if not tender.is_active:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This tender is no longer active")
    logger.debug(f"[TENDERS] /{tender_id} viewed by user={current_user.id}")
    return tender