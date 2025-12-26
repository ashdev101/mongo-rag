from fastapi import Request, HTTPException
from backend.security.tokens import _sign, _verify
from backend.config import Settings


def issue_csrf(browser_token: str) -> str:
    return _sign({"bt": browser_token}, Settings.CSRF_TOKEN_TTL)


def validate_csrf(request: Request, browser_token: str):
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("x-csrf-token")

    if not cookie_token or not header_token:
        raise HTTPException(403, "CSRF missing")

    if cookie_token != header_token:
        raise HTTPException(403, "CSRF mismatch")

    try:
        payload = _verify(cookie_token)
    except ValueError:
        raise HTTPException(403, "CSRF token invalid or expired")

    if payload["bt"] != browser_token:
        raise HTTPException(403, "CSRF token invalid or expired")
