from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth_utils
import os

router = APIRouter(prefix="/auth", tags=["Authentication"])
FREE_CREDITS = float(os.getenv("FREE_CREDITS_ON_SIGNUP", 5))

@router.post("/register", response_model=schemas.Token)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = models.User(
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=auth_utils.hash_password(user_data.password),
        credit_balance=FREE_CREDITS,
        # NEW: Save location if provided during registration
        province_preferences=[user_data.province] if user_data.province else [],
        town_preferences=[user_data.town] if user_data.town else [],
        business_location=user_data.business_location,
        business_lat=user_data.business_lat,
        business_lng=user_data.business_lng,
    )

    

@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not auth_utils.verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "access_token": auth_utils.create_access_token({"sub": user.email}),
        "token_type": "bearer"
    }