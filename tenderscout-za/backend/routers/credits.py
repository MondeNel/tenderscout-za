"""
File: routers/credits.py
Purpose: Credit balance enquiry and top‑up (demo) endpoints.

This module provides:
- GET  /credits/balance  → current balance in credits and rand equivalent
- POST /credits/topup    → add credits by selecting a predefined package

Design notes:
- All monetary values are stored and calculated as Decimal to avoid
  floating‑point rounding errors.
- The top‑up flow is a demo: no real payment gateway is integrated.
  Production should call PayFast/Stripe and only credit after successful
  payment confirmation.
- Transaction records are immutable — each top‑up creates a new row
  in the transactions table for auditability.
"""

from decimal import Decimal
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from database import get_db
import auth_utils, models, schemas
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/credits", tags=["Credits"])

# ------------------------------------------------------------------
# Available top‑up packages
#   key    → (credits, price in rands)
# ------------------------------------------------------------------
# Maps the package label from the API request to a credit amount and its
# rand price (1 credit = R1 in the current demo model).
# ------------------------------------------------------------------
PACKAGES: dict[str, tuple[Decimal, int]] = {
    "100": (Decimal("100.00"), 100),   # 100 credits for R100
    "250": (Decimal("250.00"), 250),   # 250 credits for R250
    "500": (Decimal("500.00"), 500),   # 500 credits for R500
}

# How many rand one credit is worth (1:1 in demo)
RAND_PER_CREDIT = Decimal("1.00")


# ------------------------------------------------------------------
# GET /credits/balance
# ------------------------------------------------------------------
@router.get("/balance", response_model=schemas.CreditBalance)
def get_balance(
    request: Request,
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Return the authenticated user's current credit balance.

    The response includes both the raw credit balance and its approximate
    rand value (useful for displaying "R50.00 worth of credits" in the UI).
    """
    # Convert float from DB to Decimal for safe arithmetic
    balance = Decimal(str(current_user.credit_balance))
    return {
        "balance":    float(balance),
        "rand_value": float(balance * RAND_PER_CREDIT),
    }


# ------------------------------------------------------------------
# POST /credits/topup
# ------------------------------------------------------------------
@router.post("/topup", response_model=schemas.TopUpResponse, status_code=status.HTTP_200_OK)
def topup(
    request: Request,
    body: schemas.TopUpRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Add credits to the user's account (demo implementation).

    Process:
    1. Look up the selected package (validated by Pydantic to be
       one of "100", "250", "500").
    2. Calculate the new balance.
    3. Update the user's credit_balance in the database.
    4. Record an immutable transaction for audit trail.
    5. Commit both changes atomically.

    Production notes:
    - Before crediting, a real payment gateway callback/webhook would
      be verified.
    - The transaction description includes the rand value for clarity.
    """
    # Retrieve the credit amount and rand price for the chosen package
    credits_to_add, rand_price = PACKAGES[body.package]

    # Current balance as Decimal (float from DB is converted to string first)
    current_balance = Decimal(str(current_user.credit_balance))
    new_balance = current_balance + credits_to_add

    # Update the user's balance in the ORM object
    current_user.credit_balance = new_balance

    # Create an audit transaction
    db.add(models.Transaction(
        user_id=current_user.id,
        amount=credits_to_add,
        transaction_type="credit",                     # "credit" for additions
        description=f"Top-up: R{rand_price} — {credits_to_add:.0f} credits",
    ))
    # Persist both the user update and the transaction
    db.commit()
    db.refresh(current_user)

    logger.info(
        f"[CREDITS] User {current_user.id} topped up {credits_to_add} credits "
        f"(R{rand_price}). New balance: {new_balance}"
    )

    return {
        "success":       True,
        "credits_added": float(credits_to_add),
        "new_balance":   float(new_balance),
        "message":       f"{credits_to_add:.0f} credits added successfully",
    }