from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from database import get_db
from auth import get_current_user
import models, schemas
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/tenders", tags=["Tenders"])


@router.get("/latest", response_model=schemas.TenderLatestResponse)
def get_latest(
    since: Optional[str] = Query(None),
    industries: Optional[str] = Query(None),
    provinces: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = db.query(models.Tender).filter(models.Tender.is_active == True)

    if since:
        try:
            query = query.filter(models.Tender.scraped_at > datetime.fromisoformat(since))
        except ValueError:
            pass

    if industries:
        il = industries.split(",")
        query = query.filter(or_(*[models.Tender.industry_category.ilike(f"%{i}%") for i in il]))

    if provinces:
        pl = provinces.split(",")
        query = query.filter(or_(*[models.Tender.province.ilike(f"%{p}%") for p in pl]))

    tenders = query.order_by(desc(models.Tender.scraped_at)).limit(50).all()
    return {"new_count": len(tenders), "tenders": tenders}


@router.get("/{tender_id}", response_model=schemas.TenderOut)
def get_tender(
    tender_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    tender = db.query(models.Tender).filter(models.Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender
