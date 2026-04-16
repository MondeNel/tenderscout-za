from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import auth_utils  # FIX: was `from auth import get_current_user`
import models, schemas
from typing import List

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/profile", response_model=schemas.UserOut)
def get_profile(current_user: models.User = Depends(auth_utils.get_current_user)):
    return current_user


@router.put("/preferences", response_model=schemas.UserOut)
def update_preferences(
    prefs: schemas.UserPreferences,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user)
):
    current_user.industry_preferences = prefs.industry_preferences
    current_user.province_preferences = prefs.province_preferences
    current_user.town_preferences = prefs.town_preferences
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
        .limit(50)
        .all()
    )