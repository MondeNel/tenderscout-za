"""
File: routers/user.py
Purpose: User profile, preferences, transaction history,
         and available industries list.

This module provides the endpoints that allow a logged‑in user to:

- GET  /user/profile       – retrieve their own account data
- PUT  /user/preferences   – update partial profile preferences
- GET  /user/transactions  – view their credit transaction history
- GET  /user/industries    – list the valid industries for profile setup

All endpoints (except /industries) require JWT authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
import auth_utils, models, schemas
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["User"])


# ------------------------------------------------------------------
# GET /user/profile
# ------------------------------------------------------------------
@router.get("/profile", response_model=schemas.UserOut)
def get_profile(
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Return the authenticated user's profile.

    The response includes all user fields now, including the new company
    profile fields (company_name, registration_number, bee_level,
    company_size) and industry_preferences.

    No extra processing is needed – the ORM User object is returned
    directly and Pydantic serialises it according to UserOut.
    """
    return current_user


# ------------------------------------------------------------------
# PUT /user/preferences
# ------------------------------------------------------------------
@router.put("/preferences", response_model=schemas.UserOut)
def update_preferences(
    prefs: schemas.UserPreferences,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Update one or more profile/preference fields.

    The request body is a `UserPreferences` schema where every field is
    optional. Only non‑None values are applied; omitted fields are left
    unchanged. This allows the frontend to send a partial update (e.g.,
    only changing industries without touching location).

    Validation rules:
    - If business_lat is provided, business_lng must also be provided
      (and vice versa). A 422 error is raised otherwise.
    - Industry choices are validated by Pydantic (see schemas.py).

    Returns the full updated user profile.
    """
    # Validate coordinate pair integrity
    lat = prefs.business_lat
    lng = prefs.business_lng
    if (lat is None) != (lng is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="business_lat and business_lng must be provided together",
        )

    # Map of allowed fields that can be updated
    # Keys match the User model attribute names
    field_map = {
        "industry_preferences":     prefs.industry_preferences,
        "province_preferences":     prefs.province_preferences,
        "town_preferences":         prefs.town_preferences,
        "municipality_preferences": prefs.municipality_preferences,
        "company_name":             prefs.company_name,
        "registration_number":      prefs.registration_number,
        "bee_level":                prefs.bee_level,
        "company_size":             prefs.company_size,
        "business_location":        prefs.business_location,
        "business_lat":             prefs.business_lat,
        "business_lng":             prefs.business_lng,
        "search_radius_km":         prefs.search_radius_km,
    }

    # Apply each non‑None value to the current user object
    updated_fields = []
    for field, value in field_map.items():
        if value is not None:
            setattr(current_user, field, value)
            updated_fields.append(field)

    # If nothing was actually changed, return the user as‑is (saves a DB write)
    if not updated_fields:
        return current_user

    # Persist the changes
    db.commit()
    db.refresh(current_user)
    logger.info(f"[USER] Preferences updated for user {current_user.id}: {updated_fields}")
    return current_user


# ------------------------------------------------------------------
# GET /user/transactions
# ------------------------------------------------------------------
@router.get("/transactions", response_model=List[schemas.TransactionOut])
def get_transactions(
    skip:  int = Query(default=0,  ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Return a paginated list of the user's credit transactions.

    Transactions are ordered by most recent first. The response is a list
    of TransactionOut objects (id, amount, type, description, timestamp).

    Query parameters:
    - skip:  how many records to skip (default 0).
    - limit: maximum records to return (default 50, max 200).
    """
    return (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .order_by(models.Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ------------------------------------------------------------------
# GET /user/industries
# ------------------------------------------------------------------
@router.get("/industries", response_model=List[str])
def get_industries():
    """
    Return the canonical list of 20 industry categories.

    This list is used by the frontend to render industry selection
    dropdowns (registration, profile editing) and must match the
    `INDUSTRY_CHOICES` defined in `schemas.py`.

    The endpoint is public (no authentication required) because it
    serves static reference data.
    """
    return schemas.INDUSTRY_CHOICES