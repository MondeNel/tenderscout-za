from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
import models

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if os.getenv("ENV", "development") == "production":
        logger.critical("[AUTH] SECRET_KEY not set — refusing to start in production")
        sys.exit(1)
    SECRET_KEY = "dev-only-secret-key-change-before-deploy"
    logger.warning("[AUTH] ⚠️  Using dev SECRET_KEY — set SECRET_KEY in .env before deploying")

ALGORITHM                    = "HS256"  # never read from env — "none" is a known attack vector
ACCESS_TOKEN_EXPIRE_MINUTES  = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 10080))  # 7 days
TOKEN_TYPE_ACCESS            = "access"

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain: str, hashed: str) -> bool: return pwd_context.verify(plain, hashed)
def hash_password(password: str) -> str:              return pwd_context.hash(password)

# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    now    = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return jwt.encode(
        {**data, "exp": expire, "iat": now, "type": TOKEN_TYPE_ACCESS},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

# ---------------------------------------------------------------------------
# OAuth2 scheme — OPTIONS-preflight safe
# ---------------------------------------------------------------------------
# Standard OAuth2PasswordBearer raises 401 on OPTIONS requests (no Auth header),
# which fires before CORSMiddleware attaches its headers → looks like a CORS error.
# Returning None here defers the 401 to get_current_user where headers are set.

class OptionalOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        if request.method == "OPTIONS":
            return None
        authorization = request.headers.get("Authorization", "")
        scheme, param = get_authorization_scheme_param(authorization)
        return param if scheme.lower() == "bearer" else None


oauth2_scheme = OptionalOAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# ---------------------------------------------------------------------------
# Current user dependency
# ---------------------------------------------------------------------------

_UNAUTH = dict(status_code=status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    request:      Request,
    token:        Optional[str]  = Depends(oauth2_scheme),
    db:           Session        = Depends(get_db),
) -> models.User:
    """
    Resolve the authenticated user from a JWT Bearer token.

    - Caches result on request.state — single DB hit per request even when
      multiple dependencies call this.
    - Uses db.get() for PK lookup — hits SQLAlchemy identity map before DB.
    - Distinguishes expired vs invalid tokens in error messages.
    """
    if hasattr(request.state, "current_user") and request.state.current_user:
        return request.state.current_user

    if not token:
        raise HTTPException(detail="Not authenticated", **_UNAUTH)

    try:
        payload = _decode_token(token)
    except ExpiredSignatureError:
        raise HTTPException(detail="Session expired — please log in again", **_UNAUTH)
    except JWTError:
        raise HTTPException(detail="Could not validate credentials", **_UNAUTH)

    email:      str | None = payload.get("sub")
    token_type: str | None = payload.get("type")

    if not email:
        raise HTTPException(detail="Could not validate credentials", **_UNAUTH)
    if token_type != TOKEN_TYPE_ACCESS:
        raise HTTPException(detail="Invalid token type", **_UNAUTH)

    # Query by email (not PK, so db.get() isn't applicable here —
    # but we filter on an indexed column so this is a fast index scan)
    user: models.User | None = (
        db.query(models.User).filter(models.User.email == email).first()
    )

    if user is None:
        raise HTTPException(detail="User not found", **_UNAUTH)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    request.state.current_user = user
    return user