"""
File: routers/user.py
Purpose: User profile, preferences, and transaction history endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
import auth_utils, models, schemas
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["User"])

@router.get("/profile", response_model=schemas.UserOut)
def get_profile(
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    return current_user

@router.put("/preferences", response_model=schemas.UserOut)
def update_preferences(
    prefs: schemas.UserPreferences,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    lat = prefs.business_lat
    lng = prefs.business_lng
    if (lat is None) != (lng is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="business_lat and business_lng must be provided together",
        )

    field_map = {
        "industry_preferences":     prefs.industry_preferences,
        "province_preferences":     prefs.province_preferences,
        "town_preferences":         prefs.town_preferences,
        "municipality_preferences": prefs.municipality_preferences,
        "business_location":        prefs.business_location,
        "business_lat":             prefs.business_lat,
        "business_lng":             prefs.business_lng,
        "search_radius_km":         prefs.search_radius_km,
    }

    updated_fields = []
    for field, value in field_map.items():
        if value is not None:
            setattr(current_user, field, value)
            updated_fields.append(field)

    if not updated_fields:
        return current_user

    db.commit()
    db.refresh(current_user)
    logger.info(f"[USER] Preferences updated for user {current_user.id}: {updated_fields}")
    return current_user

@router.get("/transactions", response_model=List[schemas.TransactionOut])
def get_transactions(
    skip:  int = Query(default=0,  ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    return (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .order_by(models.Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )