"""
File: routers/auth.py
Purpose: Authentication endpoints (register, login)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth_utils
import os

router = APIRouter(prefix="/auth", tags=["Authentication"])
FREE_CREDITS = float(os.getenv("FREE_CREDITS_ON_SIGNUP", 5))


@router.post("/register", response_model=schemas.Token)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Now accepts optional location fields:
    - province: User's province
    - town: User's town/city
    - business_location: Human-readable address
    - business_lat/lng: GPS coordinates
    """
    # Check for existing user
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user with location data if provided
    user = models.User(
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=auth_utils.hash_password(user_data.password),
        credit_balance=FREE_CREDITS,
        # Location tracking — saved during registration
        province_preferences=[user_data.province] if user_data.province else [],
        town_preferences=[user_data.town] if user_data.town else [],
        business_location=user_data.business_location or (user_data.town if user_data.town else None),
        business_lat=user_data.business_lat,
        business_lng=user_data.business_lng,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Record welcome bonus transaction
    db.add(models.Transaction(
        user_id=user.id,
        amount=FREE_CREDITS,
        transaction_type="credit",
        description="Welcome bonus — 5 free credits"
    ))
    db.commit()
    
    # Return JWT token
    return {
        "access_token": auth_utils.create_access_token({"sub": user.email}),
        "token_type": "bearer"
    }


@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate an existing user and return a JWT token.
    """
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not auth_utils.verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    return {
        "access_token": auth_utils.create_access_token({"sub": user.email}),
        "token_type": "bearer"
    }