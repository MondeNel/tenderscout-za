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


# =============================================================================
# PROFILE
# =============================================================================

@router.get("/profile", response_model=schemas.UserOut)
def get_profile(
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """Return the current user's profile."""
    return current_user


# =============================================================================
# PREFERENCES
# =============================================================================

@router.put("/preferences", response_model=schemas.UserOut)
def update_preferences(
    prefs: schemas.UserPreferences,          # FIX: typed schema instead of raw dict
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Update user preferences (partial update — only sent fields are changed).

    FIX: Accepts UserPreferences schema instead of a raw dict, which previously
    allowed arbitrary keys (including password_hash, is_active, id) to be
    written directly onto the model via setattr.

    FIX: Validates coordinate pairs — lat without lng (or vice versa) would
    leave the user with a broken location that silently fails map features.
    """
    # Validate coordinate pair completeness
    lat = prefs.business_lat
    lng = prefs.business_lng
    if (lat is None) != (lng is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="business_lat and business_lng must be provided together",
        )

    # Apply only fields that were explicitly sent (not None)
    # Using model_fields_set would be ideal but UserPreferences uses Optional
    # with None-as-unset convention, so we check for None explicitly.
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
        # Nothing to update — return current state without a DB write
        return current_user

    db.commit()
    db.refresh(current_user)

    logger.info(f"[USER] Preferences updated for user {current_user.id}: {updated_fields}")
    return current_user


# =============================================================================
# TRANSACTIONS
# =============================================================================

@router.get("/transactions", response_model=List[schemas.TransactionOut])
def get_transactions(
    skip:  int = Query(default=0,  ge=0,  description="Records to skip"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Return the current user's transaction history.

    FIX: Added pagination via skip/limit so users can retrieve older records
    beyond the previously hardcoded limit of 50.
    """
    return (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .order_by(models.Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )