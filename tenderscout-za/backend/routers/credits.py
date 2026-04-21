from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import auth_utils, models, schemas

router = APIRouter(prefix="/credits", tags=["Credits"])
PACKAGES = {"100": 10.0, "250": 25.0, "500": 50.0}

@router.get("/balance", response_model=schemas.CreditBalance)
def get_balance(current_user: models.User = Depends(auth_utils.get_current_user)):
    return {"balance": current_user.credit_balance, "rand_value": current_user.credit_balance * 10}

@router.post("/topup", response_model=schemas.TopUpResponse)
def topup(
    request: schemas.TopUpRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user)
):
    if request.package not in PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package. Choose 100, 250, or 500")
    credits = PACKAGES[request.package]
    current_user.credit_balance += credits
    db.add(models.Transaction(
        user_id=current_user.id, amount=credits,
        transaction_type="credit", description=f"Top-up: R{request.package} — {credits} credits"
    ))
    db.commit()
    db.refresh(current_user)
    return {"success": True, "credits_added": credits, "new_balance": current_user.credit_balance, "message": f"{credits} credits added successfully"}