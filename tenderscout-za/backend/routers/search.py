from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from database import get_db
import auth_utils  # FIX: was `from auth import get_current_user`
import models, schemas
import os

router = APIRouter(prefix="/search", tags=["Search"])
CREDITS_PER_RESULT = float(os.getenv("CREDITS_PER_RESULT", 1))


@router.post("/tenders", response_model=schemas.SearchResponse)
def search_tenders(
    request: schemas.SearchRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user)
):
    # FIX: pre-flight check uses page_size (max possible cost), which is correct —
    # user must have enough credits to cover a full page. Actual charge is based
    # on results returned, so users are never overcharged.
    max_credits_needed = request.page_size * CREDITS_PER_RESULT
    if current_user.credit_balance < max_credits_needed:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient credits. Need up to {max_credits_needed}, "
                f"have {current_user.credit_balance}"
            )
        )

    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    if request.industries:
        query = query.filter(
            or_(*[models.Tender.industry_category.ilike(f"%{i}%") for i in request.industries])
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
            models.Tender.issuing_body.ilike(kw)
        ))

    total = query.count()
    results = (
        query.order_by(desc(models.Tender.scraped_at))
        .offset((request.page - 1) * request.page_size)
        .limit(request.page_size)
        .all()
    )

    # FIX: charge only for results actually returned
    credits_charged = len(results) * CREDITS_PER_RESULT
    current_user.credit_balance -= credits_charged

    db.add(models.Transaction(
        user_id=current_user.id,
        amount=credits_charged,
        transaction_type="debit",
        description=f"Search: {len(results)} results"
    ))
    db.add(models.SearchLog(
        user_id=current_user.id,
        query_params={
            "industries": request.industries,
            "provinces": request.provinces,
            "municipalities": request.municipalities,
            "towns": request.towns,
            "keyword": request.keyword,
        },
        result_count=len(results),
        credits_charged=credits_charged
    ))
    db.commit()

    return {
        "total": total,
        "page": request.page,
        "page_size": request.page_size,
        "results": results,
        "credits_charged": credits_charged
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