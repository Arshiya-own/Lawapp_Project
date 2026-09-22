"""Session tokens and the authenticated-user dependency.

`01_architecture.md` § 4.3 allows either HTTP-only cookies or an Authorization Bearer
JWT. Bearer is used here, with the 60-minute expiry the spec binds for that choice.
The frontend holds the token in memory only — never `localStorage` (`02_frontend_spec.md`
F-17) — so the callback hands it over as a query parameter on the redirect and the SPA
keeps it in React state.
"""

import base64
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import db
from config import get_settings
from middleware import AppError

ALGORITHM = "HS256"

# auto_error=False so a missing header raises our 401 envelope rather than FastAPI's
# default {"detail": ...} shape, which would break the § 4 contract.
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expiry_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_signing_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_signing_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AppError(401, "unauthenticated", "Session has expired.")
    except jwt.InvalidTokenError:
        raise AppError(401, "unauthenticated", "Invalid session token.")


def current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> sqlite3.Row:
    """Resolve the caller, or raise 401. Also tags the request for § 10 logging."""
    if credentials is None or not credentials.credentials:
        raise AppError(401, "unauthenticated", "Authentication required.")

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise AppError(401, "unauthenticated", "Invalid session token.")

    user = db.get_user(user_id)
    if user is None:
        raise AppError(401, "unauthenticated", "Invalid session token.")

    request.state.user_id = user_id
    return user


# --- PKCE (01_architecture.md § 4.3) ----------------------------------------


def generate_pkce_pair() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for the S256 method.

    RFC 7636: the verifier is 43–128 unreserved characters; the challenge is the
    base64url-encoded SHA-256 of it, with padding stripped.
    """
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge
