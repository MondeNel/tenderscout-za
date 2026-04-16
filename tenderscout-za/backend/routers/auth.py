from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
import auth_utils
import os
import re

router = APIRouter(prefix="/auth", tags=["Authentication"])
FREE_CREDITS = float(os.getenv("FREE_CREDITS_ON_SIGNUP", 5))
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@router.post("/register", response_model=schemas.Token)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    # Validate email format
    if not EMAIL_REGEX.match(user_data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=auth_utils.hash_password(user_data.password),
        credit_balance=FREE_CREDITS,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(
        models.Transaction(
            user_id=user.id,
            amount=FREE_CREDITS,
            transaction_type="credit",
            description="Welcome bonus — 5 free credits",
        )
    )
    db.commit()

    return {
        "access_token": auth_utils.create_access_token({"sub": user.email}),
        "token_type": "bearer",
    }


@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not auth_utils.verify_password(
        credentials.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "access_token": auth_utils.create_access_token({"sub": user.email}),
        "token_type": "bearer",
    }