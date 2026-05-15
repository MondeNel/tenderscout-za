"""
File: routers/search.py
Purpose: Tender search with filtering, pagination, radius search, and credit charging
"""

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, and_
from database import get_db
import auth_utils
import models, schemas
import math
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])

try:
    CREDITS_PER_RESULT = Decimal(os.getenv("CREDITS_PER_RESULT", "1"))
except Exception:
    logger.warning("[SEARCH] Invalid CREDITS_PER_RESULT in env — defaulting to 1")
    CREDITS_PER_RESULT = Decimal("1")

_BBOX_PADDING_DEG = 1.0

_INDUSTRY_ALIASES: dict[str, list[str]] = {
    "Security Services":     ["Security, Access, Alarms & Fire"],
    "Construction":          ["Civil", "Building & Trades"],
    "Waste Management":      ["Waste Management"],
    "Electrical Services":   ["Electrical & Automation"],
    "Plumbing":              ["Plumbing & Water"],
    "ICT / Technology":      ["IT & Telecoms"],
    "Maintenance":           ["Building & Trades", "Mechanical, Plant & Equipment"],
    "Mining Services":       ["Mechanical, Plant & Equipment"],
    "Cleaning Services":     ["Cleaning & Facility Management"],
    "Catering":              ["Catering"],
    "Consulting":            ["Consultants", "Engineering Consultants"],
    "Transport & Logistics": ["Transport & Logistics"],
    "Healthcare":            ["Medical & Healthcare"],
    "Landscaping":           ["Cleaning & Facility Management"],
    "Security, Access, Alarms & Fire":   ["Security, Access, Alarms & Fire"],
    "Civil":                             ["Civil"],
    "Building & Trades":                 ["Building & Trades"],
    "Electrical & Automation":           ["Electrical & Automation"],
    "Plumbing & Water":                  ["Plumbing & Water"],
    "IT & Telecoms":                     ["IT & Telecoms"],
    "Cleaning & Facility Management":    ["Cleaning & Facility Management"],
    "Mechanical, Plant & Equipment":     ["Mechanical, Plant & Equipment"],
    "Transport & Logistics":             ["Transport & Logistics"],
    "Materials, Supply & Services":      ["Materials, Supply & Services"],
    "Consultants":                       ["Consultants"],
    "Engineering Consultants":           ["Engineering Consultants"],
    "Medical & Healthcare":              ["Medical & Healthcare"],
    "HR & Training":                     ["HR & Training"],
    "Accounting, Banking & Legal":       ["Accounting, Banking & Legal"],
    "Media & Marketing":                 ["Media & Marketing"],
    "Travel, Tourism & Hospitality":     ["Travel, Tourism & Hospitality"],
}

def _resolve_industries(requested: list[str]) -> list[str]:
    resolved: set[str] = set()
    for name in requested:
        aliases = _INDUSTRY_ALIASES.get(name)
        resolved.update(aliases if aliases else [name])
    return list(resolved)

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _bbox_filter(query, lat: float, lng: float, radius_km: float):
    pad = (radius_km / 111.0) + _BBOX_PADDING_DEG
    return query.filter(
        and_(
            models.Tender.lat.isnot(None),
            models.Tender.lng.isnot(None),
            models.Tender.lat.between(lat - pad, lat + pad),
            models.Tender.lng.between(lng - pad, lng + pad),
        )
    )

@router.post("/tenders", response_model=schemas.SearchResponse)
def search_tenders(
    http_request: Request,
    search: schemas.SearchRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    balance = Decimal(str(current_user.credit_balance))
    if balance < CREDITS_PER_RESULT:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message":   "Insufficient credits. Please top up.",
                "balance":   float(balance),
                "required":  float(CREDITS_PER_RESULT),
                "topup_url": "/credits/topup",
            },
        )

    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    if search.industries:
        resolved = _resolve_industries(search.industries)
        query = query.filter(
            or_(*[models.Tender.industry_category.ilike(f"%{i}%") for i in resolved])
        )
    if search.provinces:
        query = query.filter(
            or_(*[models.Tender.province.ilike(f"%{p}%") for p in search.provinces])
        )
    if search.municipalities:
        query = query.filter(
            or_(*[models.Tender.municipality.ilike(f"%{m}%") for m in search.municipalities])
        )
    if search.towns:
        query = query.filter(
            or_(*[models.Tender.town.ilike(f"%{t}%") for t in search.towns])
        )
    if search.keyword:
        kw = f"%{search.keyword}%"
        query = query.filter(or_(
            models.Tender.title.ilike(kw),
            models.Tender.description.ilike(kw),
            models.Tender.issuing_body.ilike(kw),
        ))

    use_radius = (
        search.user_lat is not None
        and search.user_lng is not None
        and search.radius_km is not None
        and search.radius_km > 0
    )

    if use_radius:
        bbox_query     = _bbox_filter(query, search.user_lat, search.user_lng, search.radius_km)
        coordinated    = bbox_query.order_by(desc(models.Tender.scraped_at)).all()
        uncoordinated  = (
            query
            .filter(or_(models.Tender.lat.is_(None), models.Tender.lng.is_(None)))
            .order_by(desc(models.Tender.scraped_at))
            .all()
        )

        in_radius = []
        for t in coordinated:
            d = _haversine_km(search.user_lat, search.user_lng, t.lat, t.lng)
            if d <= search.radius_km:
                in_radius.append((t, d))

        in_radius.sort(key=lambda x: x[1])
        filtered = in_radius + [(t, None) for t in uncoordinated]

        total      = len(filtered)
        start      = (search.page - 1) * search.page_size
        page_items = [t for t, _ in filtered[start: start + search.page_size]]

    else:
        total      = query.count()
        page_items = (
            query
            .order_by(desc(models.Tender.scraped_at))
            .offset((search.page - 1) * search.page_size)
            .limit(search.page_size)
            .all()
        )

    credits_charged = min(
        Decimal(str(len(page_items))) * CREDITS_PER_RESULT,
        balance,
    )
    current_user.credit_balance = float(balance - credits_charged)

    db.add(models.Transaction(
        user_id=current_user.id,
        amount=credits_charged,
        transaction_type="debit",
        description=f"Search: {len(page_items)} results",
    ))
    db.add(models.SearchLog(
        user_id=current_user.id,
        query_params={
            "industries":     search.industries,
            "provinces":      search.provinces,
            "municipalities": search.municipalities,
            "towns":          search.towns,
            "keyword":        search.keyword,
            "user_lat":       search.user_lat,
            "user_lng":       search.user_lng,
            "radius_km":      search.radius_km,
        },
        result_count=len(page_items),
        credits_charged=credits_charged,
    ))
    db.commit()

    logger.info(
        f"[SEARCH] user={current_user.id} results={len(page_items)} "
        f"charged={credits_charged} balance={balance - credits_charged}"
    )

    return {
        "total":           total,
        "page":            search.page,
        "page_size":       search.page_size,
        "results":         page_items,
        "credits_charged": float(credits_charged),
    }

@router.get("/history", response_model=list[schemas.SearchHistoryOut])
def search_history(
    skip:  int = Query(default=0,  ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    return (
        db.query(models.SearchLog)
        .filter(models.SearchLog.user_id == current_user.id)
        .order_by(models.SearchLog.searched_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )