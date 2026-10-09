"""Server-side security middleware: HTTP method restriction, CORS, security headers."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_settings

settings = get_settings()

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "cross-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


async def restrict_methods(request: Request, call_next):
    """Reject any HTTP method outside the configured whitelist with 405."""
    if request.method not in settings.ALLOWED_METHODS and request.method != "OPTIONS":
        allow = ", ".join(settings.ALLOWED_METHODS + ["OPTIONS"])
        return JSONResponse(
            status_code=405,
            content={"detail": f"Method {request.method} not allowed"},
            headers={"Allow": allow},
        )
    return await call_next(request)


async def head_to_get(request: Request, call_next):
    """FastAPI routes do not match HEAD; serve it as GET without the body.

    Installed innermost so only this layer sees the rewritten method
    (outer layers keep logging/reporting the original HEAD).
    """
    if request.method != "HEAD":
        return await call_next(request)

    original_method = request.scope["method"]
    request.scope["method"] = "GET"
    try:
        response = await call_next(request)
        # Fully consume the body iterator so no bytes are streamed for HEAD.
        async for _ in response.body_iterator:
            pass
        return response
    finally:
        request.scope["method"] = original_method


async def security_headers(request: Request, call_next):
    """Attach SECURITY_HEADERS to every response, including unhandled 500s."""
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    response.headers.update(SECURITY_HEADERS)
    return response


def add_head_support(app: FastAPI) -> None:
    app.add_middleware(BaseHTTPMiddleware, dispatch=head_to_get)


def add_restrict_methods(app: FastAPI) -> None:
    app.add_middleware(BaseHTTPMiddleware, dispatch=restrict_methods)


def add_security_headers(app: FastAPI) -> None:
    app.add_middleware(BaseHTTPMiddleware, dispatch=security_headers)


def configure_cors(app: FastAPI) -> None:
    """Add CORS middleware. Call LAST so it wraps all response-producing layers."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=settings.ALLOWED_METHODS,
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
        max_age=600,
    )
