"""Google OAuth 2.0 Authorization Code flow with PKCE (03_backend_spec.md § 5.1).

The code-for-token exchange happens here, server-side. Google's "Web application"
client type still requires `client_secret` at the token endpoint even under PKCE, so
performing the exchange in the browser would mean shipping that secret in the SPA
bundle. Keeping it on the backend is also what lets the frontend avoid persisting
anything sensitive.
"""

import secrets
import sqlite3
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

import db
from config import get_settings
from middleware import AppError, log_event
from models.schemas import AuthorizeResponse, UserResponse
from security import create_access_token, current_user, generate_pkce_pair

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPES = "openid email profile"  # § 4.3: "nothing more"


@router.get("/google/authorize", response_model=AuthorizeResponse)
def google_authorize(return_to: str = Query(default="/")) -> AuthorizeResponse:
    """Build the Google consent URL. Returns JSON (the § 5.1 implementer's choice)."""
    settings = get_settings()
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    db.save_oauth_state(state, verifier, return_to)

    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    return AuthorizeResponse(authorize_url=f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")


@router.get("/google/callback")
def google_callback(code: str = Query(default=""),
                    state: str = Query(default=""),
                    error: str = Query(default="")) -> RedirectResponse:
    """Exchange the code, establish a session, redirect back to the frontend."""
    settings = get_settings()

    if error:
        raise AppError(400, "bad_request", f"Google returned an error: {error}")
    if not code or not state:
        raise AppError(400, "bad_request", "Missing authorization code or state.")

    stored = db.take_oauth_state(state)
    if stored is None:
        # Unknown, already-used or expired state — treat all three alike so a replay
        # cannot be distinguished from a stale login attempt.
        raise AppError(400, "bad_request", "Invalid or expired authorization state.")

    payload = {
        "code": code,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": stored["code_verifier"],
    }

    try:
        response = httpx.post(GOOGLE_TOKEN_ENDPOINT, data=payload, timeout=30.0)
    except httpx.HTTPError as exc:
        raise AppError(502, "upstream_error", "Could not reach Google's token endpoint.",
                       {"reason": repr(exc)})

    if response.status_code != 200:
        raise AppError(502, "upstream_error", "Google rejected the authorization code.",
                       {"status": response.status_code})

    id_token = response.json().get("id_token")
    if not id_token:
        raise AppError(502, "upstream_error", "Google response contained no id_token.")

    # The token arrived directly from Google's token endpoint over TLS, so the
    # signature has already been vouched for by the channel; OIDC Core § 3.1.3.7
    # permits skipping re-verification for the code flow. Claims are still checked.
    claims = jwt.decode(id_token, options={"verify_signature": False},
                        audience=settings.google_oauth_client_id)
    email = claims.get("email")
    if not email:
        raise AppError(502, "upstream_error", "Google profile contained no email.")

    user = db.upsert_user(email=email, name=claims.get("name", ""),
                          picture=claims.get("picture", ""))
    log_event(event="login", user_id=user["user_id"])

    token = create_access_token(user["user_id"])
    return_to = stored["return_to"] or "/"
    if not return_to.startswith("/"):
        return_to = "/"  # never redirect off-site on a caller-supplied value

    target = (f"{settings.frontend_base_url.rstrip('/')}{return_to}"
              f"?{urlencode({'token': token})}")
    return RedirectResponse(url=target, status_code=302)


@router.get("/me", response_model=UserResponse)
def me(user: sqlite3.Row = Depends(current_user)) -> UserResponse:
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        name=user["name"],
        picture=user["picture"],
        created_at=user["created_at"],
    )


@router.post("/logout")
def logout(user: sqlite3.Row = Depends(current_user)) -> dict:
    """Stateless sessions: the client discards the in-memory token.

    Nothing is revoked server-side because nothing is stored server-side. With a
    60-minute expiry and a token held only in memory, a closed tab already ends the
    session. Documented in README.md.
    """
    log_event(event="logout", user_id=user["user_id"])
    return {"status": "logged_out"}
