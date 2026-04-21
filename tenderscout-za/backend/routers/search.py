from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from database import get_db
import auth_utils
import models, schemas
import math
import os

router = APIRouter(prefix="/search", tags=["Search"])
CREDITS_PER_RESULT = float(os.getenv("CREDITS_PER_RESULT", 1))

# ---------------------------------------------------------------------------
# Industry alias map
# ---------------------------------------------------------------------------
# Frontend uses old names (from legacy utils.py).
# DB now has new names (from updated utils.py).
# This map lets both work transparently.

_INDUSTRY_ALIASES: dict = {
    # Old → new
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
    # New → self (pass through)
    "Security, Access, Alarms & Fire":   ["Security, Access, Alarms & Fire"],
    "Civil":                             ["Civil"],
    "Building & Trades":                 ["Building & Trades"],
    "Electrical & Automation":           ["Electrical & Automation"],
    "Plumbing & Water":                  ["Plumbing & Water"],
    "IT & Telecoms":                     ["IT & Telecoms"],
    "Cleaning & Facility Management":    ["Cleaning & Facility Management"],
    "Waste Management":                  ["Waste Management"],
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


def _resolve_industries(requested: list) -> list:
    resolved = set()
    for name in requested:
        aliases = _INDUSTRY_ALIASES.get(name)
        if aliases:
            resolved.update(aliases)
        else:
            resolved.add(name)
    return list(resolved)


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.post("/tenders", response_model=schemas.SearchResponse)
def search_tenders(
    request: schemas.SearchRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user)
):
    max_credits = request.page_size * CREDITS_PER_RESULT
    if current_user.credit_balance < max_credits:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Need up to {max_credits}, have {current_user.credit_balance}"
        )

    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    if request.industries:
        resolved = _resolve_industries(request.industries)
        query = query.filter(
            or_(*[models.Tender.industry_category.ilike(f"%{i}%") for i in resolved])
        )
    if request.provinces:
        query = query.filter(
            or_(*[models.Tender.province.ilike(f"%{p}%") for p in request.provinces])
        )
    if request.municipalities:
        query = query.filter(
            or_(*[models.Tender.municipality.ilike(f"%{m}%") for m in request.municipalities])
        )
    if request.towns:
        query = query.filter(
            or_(*[models.Tender.town.ilike(f"%{t}%") for t in request.towns])
        )
    if request.keyword:
        kw = f"%{request.keyword}%"
        query = query.filter(or_(
            models.Tender.title.ilike(kw),
            models.Tender.description.ilike(kw),
            models.Tender.issuing_body.ilike(kw),
        ))

    use_radius = (
        request.user_lat is not None
        and request.user_lng is not None
        and request.radius_km is not None
        and request.radius_km > 0
    )

    if use_radius:
        all_results = query.order_by(desc(models.Tender.scraped_at)).all()
        filtered = []
        for t in all_results:
            if t.lat is not None and t.lng is not None:
                d = _haversine_km(request.user_lat, request.user_lng, t.lat, t.lng)
                if d <= request.radius_km:
                    filtered.append((t, d))
            else:
                filtered.append((t, 99999))  # soft-include uncoordinated tenders
        filtered.sort(key=lambda x: (x[1] == 99999, x[1]))
        total     = len(filtered)
        page_items = [t for t, _ in filtered[(request.page - 1) * request.page_size: request.page * request.page_size]]
    else:
        total      = query.count()
        page_items = (
            query.order_by(desc(models.Tender.scraped_at))
            .offset((request.page - 1) * request.page_size)
            .limit(request.page_size)
            .all()
        )

    credits_charged = len(page_items) * CREDITS_PER_RESULT
    current_user.credit_balance -= credits_charged

    db.add(models.Transaction(
        user_id          = current_user.id,
        amount           = credits_charged,
        transaction_type = "debit",
        description      = f"Search: {len(page_items)} results",
    ))
    db.add(models.SearchLog(
        user_id         = current_user.id,
        query_params    = {
            "industries":    request.industries,
            "provinces":     request.provinces,
            "municipalities":request.municipalities,
            "towns":         request.towns,
            "keyword":       request.keyword,
            "user_lat":      request.user_lat,
            "user_lng":      request.user_lng,
            "radius_km":     request.radius_km,
        },
        result_count    = len(page_items),
        credits_charged = credits_charged,
    ))
    db.commit()

    return {
        "total":           total,
        "page":            request.page,
        "page_size":       request.page_size,
        "results":         page_items,
        "credits_charged": credits_charged,
    }


@router.get("/history")
def search_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user)
):
    return (
        db.query(models.SearchLog)
        .filter(models.SearchLog.user_id == current_user.id)
        .order_by(models.SearchLog.searched_at.desc())
        .limit(20)
        .all()
    )