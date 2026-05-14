from functools import lru_cache
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JOSEError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .models import User


security = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(self, user: User, claims: dict[str, Any]):
        self.user = user
        self.claims = claims


@lru_cache(maxsize=1)
def _load_jwks(jwks_url: str) -> dict[str, Any]:
    response = httpx.get(jwks_url, timeout=10)
    response.raise_for_status()
    return response.json()


def _verify_token(token: str, settings: Settings) -> dict[str, Any]:
    if not settings.clerk_jwks_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="CLERK_JWKS_URL is not configured")
    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = _load_jwks(settings.clerk_jwks_url)
        key = next((item for item in jwks["keys"] if item["kid"] == unverified_header["kid"]), None)
        if key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown token key")
        options = {"verify_aud": False}
        return jwt.decode(token, key, algorithms=[key["alg"]], issuer=settings.clerk_issuer, options=options)
    except (JOSEError, KeyError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    if settings.auth_disabled:
        clerk_user_id = "dev_user"
        email = "dev@example.com"
        claims: dict[str, Any] = {"sub": clerk_user_id, "email": email}
    else:
        if credentials is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        claims = _verify_token(credentials.credentials, settings)
        clerk_user_id = claims.get("sub")
        email = claims.get("email") or claims.get("email_address")
        if not clerk_user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")

    user = db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
    if user is None:
        user = User(clerk_user_id=clerk_user_id, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return CurrentUser(user=user, claims=claims)
