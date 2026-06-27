"""
auth_utils.py — Authentication & Authorization Utilities
==========================================================
Provides the core security machinery for TenderScout ZA:

- Password hashing with bcrypt (via passlib).
- JWT creation and verification (via python‑jose).
- An optional OAuth2 bearer scheme that allows unauthenticated requests
  (used for endpoints that can optionally return public data).
- The `get_current_user` dependency that validates the token, fetches
  the user from the database, and injects it into FastAPI route handlers.

Security highlights:
- Timing‑safe password verification (constant‑time compare).
- Token type enforcement (only "access" tokens are accepted).
- Account deactivation check (inactive users get 403, not 401).
- Per‑request caching of the current user on `request.state` to avoid
  duplicate database lookups within the same HTTP request.
"""

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

# ------------------------------------------------------------------
# SECRET KEY — loaded from environment, with a hard stop in production
# ------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    import sys
    if os.getenv("ENV", "development") == "production":
        # Refuse to start – running without a proper secret is a
        # critical security risk in production.
        logger.critical("[AUTH] SECRET_KEY is not set — refusing to start in production")
        sys.exit(1)
    else:
        # In development we fall back to a known value so the app is
        # usable out of the box without extra configuration.
        SECRET_KEY = "dev-only-secret-key-change-before-deploy"
        logger.warning("[AUTH] ⚠️  Using development SECRET_KEY — set SECRET_KEY in .env")

# ------------------------------------------------------------------
# JWT configuration
# ------------------------------------------------------------------
ALGORITHM = "HS256"                       # symmetric signing algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = int(        # default 7 days (10080 minutes)
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 10080)
)
TOKEN_TYPE_ACCESS = "access"              # token type claim value

# ------------------------------------------------------------------
# Password hashing context (bcrypt with auto‑upgrade of old hashes)
# ------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Compare a plain‑text password against a bcrypt hash.

    Uses constant‑time comparison (via passlib) to prevent timing attacks.
    """
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    """
    Hash a plain‑text password using bcrypt.

    The resulting string includes the algorithm identifier, salt,
    and cost factor, and can be passed directly to verify_password.
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    The payload always includes:
    - sub: the user's email address (subject claim)
    - iat: issued‑at timestamp (UTC)
    - exp: expiration timestamp (UTC)
    - type: "access" (to distinguish from refresh tokens in the future)

    Args:
        data:       dict containing at least a "sub" key with the user email.
        expires_delta: optional custom expiry; defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    now    = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "type": TOKEN_TYPE_ACCESS})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Raises:
    - ExpiredSignatureError if the token is past its exp claim.
    - JWTError for any other validation failure (bad signature,
      missing claims, etc.).
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


class OptionalOAuth2PasswordBearer(OAuth2PasswordBearer):
    """
    A variant of OAuth2PasswordBearer that does **not** raise a 401
    when the Authorization header is missing. Instead it returns None.

    This is used for endpoints that can optionally serve public data
    when no token is provided, but require authentication for richer
    results (e.g., the search endpoint with auto‑filtering).

    Additionally, OPTIONS requests (CORS preflight) are always skipped.
    """

    async def __call__(self, request: Request) -> Optional[str]:
        # CORS preflight requests must not require authentication
        if request.method == "OPTIONS":
            return None

        authorization: str = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)

        # If no Authorization header or not a Bearer token, return None
        if not authorization or scheme.lower() != "bearer":
            return None

        return param


# Shared dependency instance – used by route handlers via Depends()
oauth2_scheme = OptionalOAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """
    FastAPI dependency: retrieve the authenticated User from a JWT.

    Behaviour:
    1. If `request.state.current_user` is already set (e.g., by a
       middleware or an earlier dependency in the same request), return
       it immediately – avoids redundant DB queries.
    2. If no token is present, raise 401 Unauthorized.
    3. Decode and validate the JWT:
       - Check token type is "access".
       - Extract the "sub" claim (user email).
    4. Look up the user in the database by email.
       - 401 if user not found.
       - 403 if the user account is deactivated (is_active=False).
    5. Cache the user on `request.state.current_user` for the
       remainder of this request.
    6. Return the User ORM object.

    Raises:
    - 401 for missing/invalid/expired token or unknown user.
    - 403 for deactivated accounts.
    """
    # Short‑circuit: user already resolved earlier in this request
    if hasattr(request.state, "current_user") and request.state.current_user is not None:
        return request.state.current_user

    # No token provided – reject
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode token – distinguish expired vs otherwise invalid
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

    # Extract claims
    email:      str = payload.get("sub")
    token_type: str = payload.get("type")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject non‑access tokens (e.g., if we later add refresh tokens)
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

    # Block deactivated accounts
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Cache for subsequent dependencies in the same request
    request.state.current_user = user
    return user