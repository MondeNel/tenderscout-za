from decimal import Decimal
import math
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from database import get_db
import auth_utils, models, schemas
from routers._query_helpers import apply_ilike_filter, ilike_any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

try:
    CREDITS_PER_RESULT = Decimal(os.getenv("CREDITS_PER_RESULT", "1"))
except Exception:
    logger.warning("[SEARCH] Invalid CREDITS_PER_RESULT — defaulting to 1")
    CREDITS_PER_RESULT = Decimal("1")

# Bounding-box padding added around radius before the haversine pass.
# 1° latitude ≈ 111 km — conservative and safe.
_BBOX_PADDING_DEG = 1.0

# ---------------------------------------------------------------------------
# Industry alias map
# ---------------------------------------------------------------------------
# Maps legacy/alternative names → current canonical names.
# Current names map to themselves so all names pass through correctly.

_INDUSTRY_ALIASES: dict[str, list[str]] = {
    "Security Services":             ["Security, Access, Alarms & Fire"],
    "Construction":                  ["Civil", "Building & Trades"],
    "Waste Management":              ["Waste Management"],
    "Electrical Services":           ["Electrical & Automation"],
    "Plumbing":                      ["Plumbing & Water"],
    "ICT / Technology":              ["IT & Telecoms"],
    "Maintenance":                   ["Building & Trades", "Mechanical, Plant & Equipment"],
    "Mining Services":               ["Mechanical, Plant & Equipment"],
    "Cleaning Services":             ["Cleaning & Facility Management"],
    "Catering":                      ["Catering"],
    "Consulting":                    ["Consultants", "Engineering Consultants"],
    "Transport & Logistics":         ["Transport & Logistics"],
    "Healthcare":                    ["Medical & Healthcare"],
    "Landscaping":                   ["Cleaning & Facility Management"],
    # Current names — pass-through
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
        resolved.update(_INDUSTRY_ALIASES.get(name) or [name])
    return list(resolved)


# ---------------------------------------------------------------------------
# Haversine + bounding box
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _apply_bbox(query, lat: float, lng: float, radius_km: float):
    """
    Pre-filter to a bounding box before the in-memory haversine pass.
    Cuts the candidate set from the full table to the geographic area of
    interest — essential on a 100k+ row dataset.
    """
    pad = (radius_km / 111.0) + _BBOX_PADDING_DEG
    return query.filter(
        and_(
            models.Tender.lat.isnot(None),
            models.Tender.lng.isnot(None),
            models.Tender.lat.between(lat - pad, lat + pad),
            models.Tender.lng.between(lng - pad, lng + pad),
        )
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@router.post("/tenders", response_model=schemas.SearchResponse)
def search_tenders(
    http_request: Request,
    search:       schemas.SearchRequest,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Search tenders with filtering, optional radius search, pagination,
    and per-result credit charging.
    """
    balance = Decimal(str(current_user.credit_balance))
    if balance < CREDITS_PER_RESULT:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message":   "Insufficient credits. Please top up to continue searching.",
                "balance":   float(balance),
                "required":  float(CREDITS_PER_RESULT),
                "topup_url": "/credits/topup",
            },
        )

    # Base query
    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    # Filters — ilike is acceptable at current scale (~3k tenders).
    # Switch to PostgreSQL tsvector / Meilisearch at ~100k+.
    if search.industries:
        resolved = _resolve_industries(search.industries)
        query = query.filter(ilike_any(models.Tender.industry_category, resolved))

    query = apply_ilike_filter(query, models.Tender.province,     search.provinces)
    query = apply_ilike_filter(query, models.Tender.municipality,  search.municipalities)
    query = apply_ilike_filter(query, models.Tender.town,          search.towns)

    if search.keyword:
        kw = f"%{search.keyword}%"
        from sqlalchemy import or_
        query = query.filter(or_(
            models.Tender.title.ilike(kw),
            models.Tender.description.ilike(kw),
            models.Tender.issuing_body.ilike(kw),
        ))

    # Radius vs standard path
    use_radius = (
        search.user_lat is not None
        and search.user_lng is not None
        and search.radius_km is not None
        and search.radius_km > 0
    )

    if use_radius:
        # Coordinated tenders: bbox pre-filter → haversine pass
        coordinated = (
            _apply_bbox(query, search.user_lat, search.user_lng, search.radius_km)
            .order_by(desc(models.Tender.scraped_at))
            .all()
        )
        # Uncoordinated tenders: no lat/lng — append after radius results
        uncoordinated = (
            query
            .filter(models.Tender.lat.is_(None))
            .order_by(desc(models.Tender.scraped_at))
            .all()
        )

        in_radius = sorted(
            [(t, _haversine_km(search.user_lat, search.user_lng, t.lat, t.lng))
             for t in coordinated
             if _haversine_km(search.user_lat, search.user_lng, t.lat, t.lng) <= search.radius_km],
            key=lambda x: x[1],
        )
        all_results = [t for t, _ in in_radius] + uncoordinated
        total       = len(all_results)
        start       = (search.page - 1) * search.page_size
        page_items  = all_results[start: start + search.page_size]

    else:
        # Single query — fetch all matching, then slice in Python.
        # Consistent with radius path; avoids the count() + fetch double round-trip.
        # Fine at current scale; add DB-side pagination for 100k+ rows.
        all_results = query.order_by(desc(models.Tender.scraped_at)).all()
        total       = len(all_results)
        start       = (search.page - 1) * search.page_size
        page_items  = all_results[start: start + search.page_size]

    # Charge credits
    credits_charged = min(Decimal(str(len(page_items))) * CREDITS_PER_RESULT, balance)
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
        f"charged={credits_charged} balance={balance - credits_charged:.2f} "
        f"radius={search.radius_km} keyword={bool(search.keyword)}"
    )

    return {
        "total":           total,
        "page":            search.page,
        "page_size":       search.page_size,
        "results":         page_items,
        "credits_charged": float(credits_charged),
    }


# ---------------------------------------------------------------------------
# Search history
# ---------------------------------------------------------------------------

@router.get("/history", response_model=list[schemas.SearchHistoryOut])
def search_history(
    skip:  int     = Query(default=0,  ge=0),
    limit: int     = Query(default=20, ge=1, le=100),
    db:    Session = Depends(get_db),
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