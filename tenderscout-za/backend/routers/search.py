"""
File: routers/search.py
Purpose: Tender search with filtering, pagination, radius search, credit charging,
         and automatic industry filtering based on user preferences.

This module provides the main search endpoint (POST /search/tenders) and a
search history endpoint (GET /search/history). It is the central point where
users discover relevant tenders.

Key features:
- Multi‑filter search: industries, provinces, municipalities, towns, keyword
- Radius search with a bounding‑box pre‑filter for performance
- Credit charging: each displayed result costs a configurable number of credits
- Automatic industry filtering: if the user doesn't specify industries, their
  saved preferences are applied automatically
- Industry alias resolution: legacy industry names map to the current 20 categories
- Immutable audit trail: every search creates a SearchLog and a debit Transaction
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

# ------------------------------------------------------------------
# Configuration – credits consumed per tender result shown
# ------------------------------------------------------------------
# Can be overridden via CREDITS_PER_RESULT environment variable.
# Default: 1 credit per result.
# ------------------------------------------------------------------
try:
    CREDITS_PER_RESULT = Decimal(os.getenv("CREDITS_PER_RESULT", "1"))
except Exception:
    logger.warning("[SEARCH] Invalid CREDITS_PER_RESULT in env — defaulting to 1")
    CREDITS_PER_RESULT = Decimal("1")

# ------------------------------------------------------------------
# Bounding‑box padding (degrees) for radius pre‑filter
# ------------------------------------------------------------------
# When a radius search is requested, we first filter tenders to those
# whose lat/lng fall within a square that fully contains the circle.
# This avoids running the haversine formula on every tender in the
# database. The padding is an extra degree added to each side to
# account for edge cases.
# ------------------------------------------------------------------
_BBOX_PADDING_DEG = 1.0

# ------------------------------------------------------------------
# Industry alias map
# ------------------------------------------------------------------
# Some industry names used by scrapers are legacy names that have been
# merged or renamed. This map ensures that when a user searches for a
# modern industry name (key), any tender tagged with an older alias
# (values) is also returned.
# ------------------------------------------------------------------
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
    """
    Translate a list of user‑facing industry names into the set of actual
    tender industry_category values to search for.

    For each requested industry, if it exists as a key in _INDUSTRY_ALIASES,
    its aliases are added to the output. Otherwise the industry itself is kept.
    Duplicates are removed.
    """
    resolved: set[str] = set()
    for name in requested:
        aliases = _INDUSTRY_ALIASES.get(name)
        resolved.update(aliases if aliases else [name])
    return list(resolved)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great‑circle distance between two points in kilometres
    using the Haversine formula.

    This is used to filter tenders to those within the user‑specified
    radius after the bounding‑box pre‑filter narrows the candidate set.
    """
    R = 6371.0  # Earth's mean radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bbox_filter(query, lat: float, lng: float, radius_km: float):
    """
    Add a bounding‑box pre‑filter to the SQLAlchemy query.

    This dramatically reduces the number of tenders that need to be
    checked with the expensive haversine calculation. Only tenders
    with coordinates within a square that covers the radius circle
    (plus a small padding) are included.

    Returns the filtered query.
    """
    # Convert radius to approximate degrees (1° ≈ 111 km)
    pad = (radius_km / 111.0) + _BBOX_PADDING_DEG
    return query.filter(
        and_(
            models.Tender.lat.isnot(None),
            models.Tender.lng.isnot(None),
            models.Tender.lat.between(lat - pad, lat + pad),
            models.Tender.lng.between(lng - pad, lng + pad),
        )
    )


# ------------------------------------------------------------------
# POST /search/tenders
# ------------------------------------------------------------------
@router.post("/tenders", response_model=schemas.SearchResponse)
def search_tenders(
    http_request: Request,
    search: schemas.SearchRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Perform a tender search with optional filters, radius, and pagination.

    Preconditions:
    - The user must have at least CREDITS_PER_RESULT credits.
      A 402 Payment Required response is returned otherwise.

    Filters applied (in order):
    1. Only active tenders (is_active == True)
    2. If no industries in the request, fall back to the user's saved
       industry preferences (auto‑filtering).
    3. Resolve industry aliases and apply OR ILIKE filter.
    4. Province / municipality / town filters (OR ILIKE).
    5. Keyword search across title, description, and issuing_body.
    6. Radius search (when coordinates and radius are provided):
       - First applies a bounding‑box pre‑filter on the database query.
       - Then computes haversine distance on the candidates.
       - Tenders without coordinates are included as un‑filtered
         fallbacks (appended at the end of results).
    7. Pagination (page & page_size).

    Credit charging:
    - The user is charged `min(results_count, balance)` * CREDITS_PER_RESULT.
    - A debit transaction is recorded.
    - A SearchLog entry is created for audit/history.

    Returns:
    SearchResponse with total results, current page, page_size,
    list of TenderOut objects, and credits charged.
    """
    # --------------------------------------------------------------
    # Credit gate – user must be able to afford at least one result
    # --------------------------------------------------------------
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

    # --------------------------------------------------------------
    # Auto‑filter by user’s saved industries
    # --------------------------------------------------------------
    # If the user did not provide any industry filter in the request,
    # we automatically apply their saved industry preferences (set
    # during registration or updated in user preferences).
    # This is what makes the dashboard "just work" for logged‑in
    # companies – they only see tenders relevant to their business.
    # --------------------------------------------------------------
    if not search.industries:
        user_industries = current_user.industry_prefs  # returns list
        if user_industries:
            search.industries = user_industries
            logger.info(f"[SEARCH] Auto‑filtering by user industries: {user_industries}")

    # --------------------------------------------------------------
    # Base query – only active (open) tenders
    # --------------------------------------------------------------
    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    # --------------------------------------------------------------
    # Apply all optional filters
    # --------------------------------------------------------------
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

    # --------------------------------------------------------------
    # Determine if we should perform a radius (geographic) search
    # --------------------------------------------------------------
    use_radius = (
        search.user_lat is not None
        and search.user_lng is not None
        and search.radius_km is not None
        and search.radius_km > 0
    )

    # --------------------------------------------------------------
    # Execute the query – two different paths
    # --------------------------------------------------------------
    if use_radius:
        # ----------------------------------------------------------
        # Radius search path
        # ----------------------------------------------------------
        # 1. Apply the bounding‑box pre‑filter to get candidates
        #    (coarse filter in SQL).
        bbox_query = _bbox_filter(query, search.user_lat, search.user_lng, search.radius_km)
        # 2. Fetch all candidates (this is acceptable because the bbox
        #    already limits the result set).
        coordinated = bbox_query.order_by(desc(models.Tender.scraped_at)).all()

        # Also fetch tenders without coordinates separately so they
        # are still included (the "uncoordinated" group).
        uncoordinated = (
            query
            .filter(or_(models.Tender.lat.is_(None), models.Tender.lng.is_(None)))
            .order_by(desc(models.Tender.scraped_at))
            .all()
        )

        # 3. Filter coordinated tenders by exact haversine distance
        in_radius = []
        for t in coordinated:
            d = _haversine_km(search.user_lat, search.user_lng, t.lat, t.lng)
            if d <= search.radius_km:
                in_radius.append((t, d))

        # 4. Sort in‑radius tenders by distance (closest first)
        in_radius.sort(key=lambda x: x[1])

        # 5. Append uncoordinated tenders at the end (they have no
        #    distance, so they appear after all located tenders).
        filtered = in_radius + [(t, None) for t in uncoordinated]

        # 6. Paginate the combined, sorted list
        total      = len(filtered)
        start      = (search.page - 1) * search.page_size
        page_items = [t for t, _ in filtered[start: start + search.page_size]]

    else:
        # ----------------------------------------------------------
        # No radius – simple database pagination
        # ----------------------------------------------------------
        total      = query.count()
        page_items = (
            query
            .order_by(desc(models.Tender.scraped_at))
            .offset((search.page - 1) * search.page_size)
            .limit(search.page_size)
            .all()
        )

    # --------------------------------------------------------------
    # Credit charging and audit trail
    # --------------------------------------------------------------
    # Charge for the number of results actually returned on this page
    # (capped at the user's current balance to prevent negative balances).
    credits_charged = min(
        Decimal(str(len(page_items))) * CREDITS_PER_RESULT,
        balance,
    )
    current_user.credit_balance = float(balance - credits_charged)

    # Record a debit transaction
    db.add(models.Transaction(
        user_id=current_user.id,
        amount=credits_charged,
        transaction_type="debit",
        description=f"Search: {len(page_items)} results",
    ))
    # Record search parameters for history / audit
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

    # --------------------------------------------------------------
    # Return paginated response
    # --------------------------------------------------------------
    return {
        "total":           total,
        "page":            search.page,
        "page_size":       search.page_size,
        "results":         page_items,
        "credits_charged": float(credits_charged),
    }


# ------------------------------------------------------------------
# GET /search/history
# ------------------------------------------------------------------
@router.get("/history", response_model=list[schemas.SearchHistoryOut])
def search_history(
    skip:  int = Query(default=0,  ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Return the authenticated user's search history, ordered by most
    recent first, with pagination (skip / limit).
    """
    return (
        db.query(models.SearchLog)
        .filter(models.SearchLog.user_id == current_user.id)
        .order_by(models.SearchLog.searched_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )