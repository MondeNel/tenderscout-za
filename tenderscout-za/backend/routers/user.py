from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import auth_utils, models, schemas
from typing import List

router = APIRouter(prefix="/user", tags=["User"])

@router.get("/profile", response_model=schemas.UserOut)
def get_profile(current_user: models.User = Depends(auth_utils.get_current_user)):
    return current_user

@router.put("/preferences", response_model=schemas.UserOut)
def update_preferences(
    prefs: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user)
):
    # Update all preference fields that are sent
    fields = [
        "industry_preferences", "province_preferences", "town_preferences",
        "municipality_preferences", "business_location",
        "business_lat", "business_lng", "search_radius_km",
    ]
    for f in fields:
        if f in prefs:
            setattr(current_user, f, prefs[f])
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/transactions", response_model=List[schemas.TransactionOut])
def get_transactions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user)
):
    return (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .order_by(models.Transaction.created_at.desc())
        .limit(50).all()
    )