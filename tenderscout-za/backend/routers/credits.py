from decimal import Decimal
import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from database import get_db
import auth_utils, models, schemas

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/credits", tags=["Credits"])

# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
# Structure: package_key → (credits_awarded, rand_price)
# 1 credit = R1.00

PACKAGES: dict[str, tuple[Decimal, int]] = {
    "100": (Decimal("100.00"), 100),
    "250": (Decimal("250.00"), 250),
    "500": (Decimal("500.00"), 500),
}

RAND_PER_CREDIT = Decimal("1.00")


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

@router.get("/balance", response_model=schemas.CreditBalance)
def get_balance(
    request:      Request,
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    balance = Decimal(str(current_user.credit_balance))
    return {"balance": float(balance), "rand_value": float(balance * RAND_PER_CREDIT)}


# ---------------------------------------------------------------------------
# Top-up
# ---------------------------------------------------------------------------

@router.post("/topup", response_model=schemas.TopUpResponse, status_code=status.HTTP_200_OK)
def topup(
    request:      Request,
    body:         schemas.TopUpRequest,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Add credits to the user's balance using Decimal arithmetic throughout
    to prevent float precision drift on the Numeric DB column.
    """
    credits_to_add, rand_price = PACKAGES[body.package]
    current_balance = Decimal(str(current_user.credit_balance))
    new_balance     = current_balance + credits_to_add

    current_user.credit_balance = new_balance
    db.add(models.Transaction(
        user_id=current_user.id,
        amount=credits_to_add,
        transaction_type="credit",
        description=f"Top-up: R{rand_price} — {credits_to_add:.0f} credits",
    ))
    db.commit()
    db.refresh(current_user)

    logger.info(f"[CREDITS] user={current_user.id} +{credits_to_add} credits (R{rand_price}) → {new_balance}")

    return {
        "success":       True,
        "credits_added": float(credits_to_add),
        "new_balance":   float(new_balance),
        "message":       f"{credits_to_add:.0f} credits added successfully",
    }