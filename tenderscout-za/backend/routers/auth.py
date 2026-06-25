"""
File: routers/auth.py
Purpose: Authentication endpoints for user registration and login.

This module handles:
- New user registration with automatic welcome credits and optional company/industry details
- Login with timing‑safe password verification to prevent user enumeration
- Account deactivation checks
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth_utils
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# ------------------------------------------------------------------
# Configuration – free credits awarded to every new account
# ------------------------------------------------------------------
try:
    FREE_CREDITS = float(os.getenv("FREE_CREDITS_ON_SIGNUP", "5"))
except ValueError:
    logger.warning("[AUTH] Invalid FREE_CREDITS_ON_SIGNUP — defaulting to 5")
    FREE_CREDITS = 5.0


# ------------------------------------------------------------------
# POST /auth/register
# ------------------------------------------------------------------
@router.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account.

    1. Normalise email (lowercase, stripped) to prevent duplicate accounts
       with case differences.
    2. Reject duplicate emails with 400.
    3. Clean the industry list: remove duplicates, empty strings, and strip whitespace.
    4. Create a User row with supplied data plus optional company fields.
    5. Grant the welcome credits and record a credit transaction.
    6. Return a JWT access token (user is logged in immediately).

    Security notes:
    - email is lowercased to avoid "User@Example.com" vs "user@example.com"
    - Industry choices are validated at the Pydantic schema level before this function runs
    """
    # Normalise email to prevent duplicates with different cases
    email = user_data.email.lower().strip()

    # Check for existing account
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    # Clean the industry list: deduplicate and remove blank entries
    industries = user_data.industries or []
    industries = list(dict.fromkeys([i.strip() for i in industries if i.strip()]))

    # Build the new user object – note the new company profile fields
    user = models.User(
        email=email,
        full_name=user_data.full_name.strip(),
        password_hash=auth_utils.hash_password(user_data.password),
        industry_preferences=industries if industries else None,
        company_name=user_data.company_name,
        registration_number=user_data.registration_number,
        bee_level=user_data.bee_level,
        company_size=user_data.company_size,
        credit_balance=FREE_CREDITS,
        province_preferences=[user_data.province] if user_data.province else None,
        town_preferences=[user_data.town] if user_data.town else None,
        business_location=user_data.business_location or user_data.town or None,
        business_lat=user_data.business_lat,
        business_lng=user_data.business_lng,
    )
    db.add(user)
    db.flush()  # get user.id for the welcome transaction

    # Record the welcome credits as a transaction
    db.add(models.Transaction(
        user_id=user.id,
        amount=FREE_CREDITS,
        transaction_type="credit",
        description=f"Welcome bonus — {FREE_CREDITS:.0f} free credits",
    ))
    db.commit()
    db.refresh(user)

    logger.info(f"[AUTH] New user registered: {email} with industries: {industries}")
    return {
        "access_token": auth_utils.create_access_token({"sub": user.email}),
        "token_type": "bearer",
    }


# ------------------------------------------------------------------
# POST /auth/login
# ------------------------------------------------------------------
@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate an existing user and return a JWT.

    Security measures:
    - Email is normalised (lowercase, stripped) before lookup.
    - Timing‑safe password comparison: we always hash the supplied password
      and compare it against the stored hash, even if the user doesn't exist.
      This prevents an attacker from measuring response times to determine
      valid email addresses.
    - Generic error message ("Invalid email or password") on failure –
      never reveals whether the email exists.
    - Deactivated accounts (is_active=False) receive a 403 even with
      correct credentials.
    """
    email = credentials.email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email).first()

    # Timing‑safe check: always hash, compare against dummy if user not found
    dummy_hash = auth_utils.hash_password("dummy-timing-prevention")
    password_ok = auth_utils.verify_password(
        credentials.password,
        user.password_hash if user else dummy_hash,
    )

    # Reject with a generic message – do not reveal if email exists
    if not user or not password_ok:
        logger.warning(f"[AUTH] Failed login attempt for: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Block deactivated accounts
    if not user.is_active:
        logger.warning(f"[AUTH] Login attempt on deactivated account: {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    logger.info(f"[AUTH] User logged in: {email}")
    return {
        "access_token": auth_utils.create_access_token({"sub": user.email}),
        "token_type": "bearer",
    }