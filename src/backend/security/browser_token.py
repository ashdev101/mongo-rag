from fastapi import Request, HTTPException
from backend.security.tokens import _sign, _verify
from backend.config import Settings


def issue_browser_token(request: Request) -> str:
    payload = {
        "ua": request.headers.get("user-agent", ""),
    }
    return _sign(payload, Settings.BROWSER_TOKEN_TTL)


def validate_browser_token(request: Request) -> dict:
    token = request.cookies.get("browser_token")
    if not token:
        raise HTTPException(403, "Missing browser token")
    try :
        payload = _verify(token)
    except ValueError:
        raise HTTPException(403, "Browser token invalid or expired")

    if payload["ua"] != request.headers.get("user-agent", ""):
        raise HTTPException(403, "Browser token UA mismatch")

    return payload

if __name__ == "__main__" :
    req = Request("http://example.com")
    token = issue_browser_token(req)
    print(token)

    validate = validate_browser_token(req)
    print(validate)
