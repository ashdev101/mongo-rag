from fastapi import Request, HTTPException
from backend.config import Settings


def enforce_browser_request(request: Request):
    headers = request.headers

    origin = headers.get("origin")
    referer = headers.get("referer")

    if origin not in Settings.ALLOWED_ORIGINS:
        raise HTTPException(403, "Invalid origin")

    if not referer or not any(referer.startswith(o) for o in Settings.ALLOWED_ORIGINS):
        raise HTTPException(403, "Invalid referer")

    required = [
        "sec-fetch-site",
        "sec-fetch-mode",
        "sec-fetch-dest",
        "accept-language",
    ]

    for h in required:
        if h not in headers:
            raise HTTPException(403, "Non-browser request")
        

if __name__ == "__main__":
    from fastapi import Request

    class MockRequest:
        def __init__(self):
            self.headers = {
                "origin": "http://example.com",
                "referer": "http://example.com/page",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-dest": "document",
                "accept-language": "en-US,en;q=0.9",
            }

    req = MockRequest()

    enforce_browser_request(req)
    print("Browser request enforced successfully.")

