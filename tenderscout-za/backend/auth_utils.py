from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

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

# SECURE: Environment variable check with fallback only for local dev
SECRET_KEY = os.getenv("SECRET_KEY")
ENV = os.getenv("ENV", "development")

if not SECRET_KEY:
    if ENV == "production":
        logger.critical("[AUTH] ❌ SECRET_KEY MISSING IN PRODUCTION. TERMINATING.")
        raise RuntimeError("SECRET_KEY must be set in production environment.")
    else:
        SECRET_KEY = "dev_secret_key_placeholder_for_tenderscout"
        logger.warning("[AUTH] ⚠️ Using insecure dev secret key.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 10080)) # 7 Days
TOKEN_TYPE_ACCESS = "access"

# =============================================================================
# PASSWORD HASHING
# =============================================================================

# Optimized bcrypt: explicitly setting rounds ensures consistent performance
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# =============================================================================
# JWT OPERATIONS
# =============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now, # Not Before: token isn't valid until now
        "jti": str(uuid.uuid4()), # Unique ID for future blacklisting
        "type": TOKEN_TYPE_ACCESS,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# =============================================================================
# CUSTOM SCHEME (CORS & Preflight Friendly)
# =============================================================================

class SafeOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        # Handle OPTIONS requests immediately to prevent 401/CORS loops
        if request.method == "OPTIONS":
            return None

        authorization: str = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        
        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        return param

oauth2_scheme = SafeOAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# =============================================================================
# DEPENDENCIES
# =============================================================================

async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """
    Optimized user resolution with request-state caching.
    """
    # 1. Check Request Cache
    if hasattr(request.state, "user"):
        return request.state.user

    # 2. Token Presence
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # 3. Decode & Validate Claims
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        t_type: str = payload.get("type")
        
        if email is None or t_type != TOKEN_TYPE_ACCESS:
            raise JWTError()
            
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 4. Database Lookup
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # 5. Set Request Cache
    request.state.user = user
    return user