from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database import get_db
from routers._query_helpers import apply_ilike_filter
import auth_utils, models, schemas
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenders", tags=["Tenders"])

_LATEST_MAX = 100


# ---------------------------------------------------------------------------
# Latest tenders — free, no credit charge
# ---------------------------------------------------------------------------

@router.get("/latest", response_model=schemas.TenderLatestResponse)
def get_latest(
    http_request:   Request,
    since:          Optional[str] = Query(None, description="ISO datetime — tenders scraped after this"),
    industries:     Optional[str] = Query(None, description="Comma-separated industry categories"),
    provinces:      Optional[str] = Query(None, description="Comma-separated province names"),
    municipalities: Optional[str] = Query(None, description="Comma-separated municipality names"),
    limit:          int           = Query(50, ge=1, le=_LATEST_MAX),
    skip:           int           = Query(0,  ge=0),
    db:             Session       = Depends(get_db),
    current_user:   models.User   = Depends(auth_utils.get_current_user),
):
    """Return recently scraped active tenders. Free — no credit charge."""
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
                detail=f"Invalid 'since' format: {since!r}. Use ISO 8601, e.g. 2026-01-15T10:00:00",
            )

    # Strip and cap each value at 100 chars to prevent ilike injection
    def _split(val: str) -> list[str]:
        return [v.strip()[:100] for v in val.split(",") if v.strip()]

    query = apply_ilike_filter(query, models.Tender.industry_category, _split(industries)     if industries     else [])
    query = apply_ilike_filter(query, models.Tender.province,          _split(provinces)      if provinces      else [])
    query = apply_ilike_filter(query, models.Tender.municipality,      _split(municipalities) if municipalities else [])

    tenders = query.order_by(desc(models.Tender.scraped_at)).offset(skip).limit(limit).all()

    logger.debug(
        f"[TENDERS] /latest user={current_user.id} count={len(tenders)} "
        f"since={since} industries={industries} provinces={provinces}"
    )
    return {"new_count": len(tenders), "tenders": tenders}


# ---------------------------------------------------------------------------
# Single tender — free, no credit charge
# ---------------------------------------------------------------------------

@router.get("/{tender_id}", response_model=schemas.TenderOut)
def get_tender(
    tender_id:    int,
    http_request: Request,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """Return a single tender by ID. Free — no credit charge."""
    tender = db.get(models.Tender, tender_id)  # uses identity map cache

    if not tender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Tender {tender_id} not found")
    if not tender.is_active:
        raise HTTPException(status_code=status.HTTP_410_GONE,
                            detail="This tender is no longer active")

    logger.debug(f"[TENDERS] /{tender_id} user={current_user.id}")
    return tender