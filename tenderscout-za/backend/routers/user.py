from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
import auth_utils, models, schemas
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["User"])

# Preference fields that can be updated via PUT /user/preferences.
# Explicit list prevents arbitrary model fields being written via setattr.
_PREF_FIELDS = (
    "industry_preferences",
    "province_preferences",
    "town_preferences",
    "municipality_preferences",
    "business_location",
    "business_lat",
    "business_lng",
    "search_radius_km",
)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=schemas.UserOut)
def get_profile(current_user: models.User = Depends(auth_utils.get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

@router.put("/preferences", response_model=schemas.UserOut)
def update_preferences(
    prefs:        schemas.UserPreferences,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Partial update — only fields included in the request body are changed.

    Supports clearing a list preference to [] by sending an explicit empty
    list. Sending null / omitting the field leaves it unchanged.

    Uses Pydantic's model_fields_set to distinguish "field was sent as []"
    from "field was not included in the request body at all".
    """
    lat = prefs.business_lat
    lng = prefs.business_lng
    if (lat is None) != (lng is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="business_lat and business_lng must be provided together",
        )

    # model_fields_set contains only fields the client explicitly included.
    # This lets us distinguish `{"industry_preferences": []}` (clear it)
    # from a request that simply omits industry_preferences (leave it alone).
    sent_fields = prefs.model_fields_set & set(_PREF_FIELDS)
    if not sent_fields:
        return current_user  # nothing to update — skip the DB write

    for field in sent_fields:
        setattr(current_user, field, getattr(prefs, field))

    db.commit()
    db.refresh(current_user)

    logger.info(f"[USER] user={current_user.id} updated: {sorted(sent_fields)}")
    return current_user


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@router.get("/transactions", response_model=List[schemas.TransactionOut])
def get_transactions(
    skip:         int     = Query(default=0,  ge=0),
    limit:        int     = Query(default=50, ge=1, le=200),
    db:           Session = Depends(get_db),
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