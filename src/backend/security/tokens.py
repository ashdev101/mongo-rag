import time
import hmac
import hashlib
import base64
import json
from backend.config import Settings

# SECRET_KEY = b"CHANGE_ME_SUPER_SECRET"
# BROWSER_TOKEN_TTL = 600    # 10 min
# CSRF_TOKEN_TTL = 300       # 5 min


def _sign(payload: dict, ttl: int) -> str:
    payload["exp"] = int(time.time()) + ttl
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(Settings.SECRET_KEY, raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + b"." + sig).decode()


def _verify(token: str) -> dict:
    decoded = base64.urlsafe_b64decode(token.encode())
    raw, sig = decoded.rsplit(b".", 1)

    expected = hmac.new(Settings.SECRET_KEY, raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Bad signature")

    payload = json.loads(raw)
    if payload["exp"] < time.time():
        raise ValueError("Token expired")

    return payload

if __name__ == "__main__":
    token = _sign({"foo" : "bar"} , 10)
    print(token)

    verify = _verify(token)
    print(verify)
