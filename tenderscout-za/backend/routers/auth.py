"""
File: routers/auth.py
Purpose: Authentication endpoints (register, login)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth_utils
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

try:
    FREE_CREDITS = float(os.getenv("FREE_CREDITS_ON_SIGNUP", "5"))
except ValueError:
    logger.warning("[AUTH] Invalid FREE_CREDITS_ON_SIGNUP — defaulting to 5")
    FREE_CREDITS = 5.0

@router.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    email = user_data.email.lower().strip()

    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    user = models.User(
        email=email,
        full_name=user_data.full_name.strip(),
        password_hash=auth_utils.hash_password(user_data.password),
        credit_balance=FREE_CREDITS,
        province_preferences=[user_data.province] if user_data.province else None,
        town_preferences=[user_data.town] if user_data.town else None,
        business_location=user_data.business_location or user_data.town or None,
        business_lat=user_data.business_lat,
        business_lng=user_data.business_lng,
    )
    db.add(user)
    db.flush()

    db.add(models.Transaction(
        user_id=user.id,
        amount=FREE_CREDITS,
        transaction_type="credit",
        description=f"Welcome bonus — {FREE_CREDITS:.0f} free credits",
    ))
    db.commit()
    db.refresh(user)

    logger.info(f"[AUTH] New user registered: {email}")
    return {
        "access_token": auth_utils.create_access_token({"sub": user.email}),
        "token_type": "bearer",
    }

@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    email = credentials.email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email).first()

    dummy_hash = auth_utils.hash_password("dummy-timing-prevention")
    password_ok = auth_utils.verify_password(
        credentials.password,
        user.password_hash if user else dummy_hash,
    )

    if not user or not password_ok:
        logger.warning(f"[AUTH] Failed login attempt for: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

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