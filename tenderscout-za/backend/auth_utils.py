from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, ExpiredSignatureError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from database import get_db
import models
import os
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    # FIX: Fail loudly at import time rather than silently using a weak default.
    # A missing SECRET_KEY in production would allow anyone to forge tokens.
    import sys
    if os.getenv("ENV", "development") == "production":
        logger.critical("[AUTH] SECRET_KEY is not set — refusing to start in production")
        sys.exit(1)
    else:
        # Development only — loud warning so it's never missed
        SECRET_KEY = "dev-only-secret-key-change-before-deploy"
        logger.warning("[AUTH] ⚠️  Using development SECRET_KEY — set SECRET_KEY in .env")

# FIX: Algorithm hardcoded — never read from env.
# Allowing "none" or weak algorithms via env var is a known JWT attack vector.
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 10080))  # 7 days

# Token type claim — prevents a future password-reset token being used as an
# access token (defence in depth for when you add other token types)
TOKEN_TYPE_ACCESS = "access"

# =============================================================================
# PASSWORD HASHING
# =============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# =============================================================================
# JWT — TOKEN CREATION & DECODING
# =============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Includes:
      - sub:  user identifier (email)
      - exp:  expiry timestamp
      - type: "access" — prevents other token types being used here
      - iat:  issued-at timestamp (useful for audit logs)
    """
    to_encode = data.copy()
    now    = datetime.now(timezone.utc)   # FIX: utcnow() deprecated in Python 3.11+
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp":  expire,
        "iat":  now,
        "type": TOKEN_TYPE_ACCESS,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    FIX: Raises ExpiredSignatureError separately from JWTError so callers
    can show "session expired, please log in again" vs "invalid token".
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# =============================================================================
# OAUTH2 SCHEME — preflight-safe
# =============================================================================
# FIX: Standard OAuth2PasswordBearer raises 401 on OPTIONS preflight requests
# because they never carry an Authorization header. That 401 fires before
# CORSMiddleware attaches its headers, making it look like a CORS error.
#
# OptionalOAuth2PasswordBearer returns None for OPTIONS and missing tokens,
# deferring the 401 to get_current_user where CORS headers are already attached.

class OptionalOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        if request.method == "OPTIONS":
            return None

        authorization: str = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)

        if not authorization or scheme.lower() != "bearer":
            return None  # get_current_user handles the 401
        return param


oauth2_scheme = OptionalOAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# =============================================================================
# CURRENT USER DEPENDENCY
# =============================================================================

def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """
    Resolve the current authenticated user from the JWT token.

    Optimisations & fixes:
      - Caches resolved user on request.state — DB hit only once per request
        even if multiple dependencies call get_current_user
      - Checks is_active — deactivated users rejected even with valid token
      - Distinguishes expired vs invalid tokens in error messages
      - Validates token type claim against TOKEN_TYPE_ACCESS
    """
    # Cache hit — skip DB for the same request
    if hasattr(request.state, "current_user") and request.state.current_user is not None:
        return request.state.current_user

    # No token
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode JWT — distinguish expired from malformed
    try:
        payload = _decode_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate claims
    email:      str = payload.get("sub")
    token_type: str = payload.get("type")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject non-access tokens (e.g. future password-reset tokens)
    if token_type != TOKEN_TYPE_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from DB
    user = db.query(models.User).filter(models.User.email == email).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject deactivated accounts even with a valid token
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Cache on request state for this request's lifetime only
    request.state.current_user = user
    return user