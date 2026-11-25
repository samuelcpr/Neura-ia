import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "neuraljuris")
SECRET = os.environ.get("AUTH_SECRET", "neuraljuris-dev-secret")
TOKEN_TTL = 60 * 60 * 12  # 12h

bearer = HTTPBearer(auto_error=False)


def _sign(payload: str) -> str:
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(user: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"u": user, "exp": int(time.time()) + TOKEN_TTL}).encode()
    ).decode()
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> str | None:
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        if data.get("exp", 0) < time.time():
            return None
        return data.get("u")
    except Exception:
        return None


def require_auth(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if creds is None or verify_token(creds.credentials) is None:
        raise HTTPException(401, "Não autenticado. Faça login em /auth/login")
    return creds.credentials
