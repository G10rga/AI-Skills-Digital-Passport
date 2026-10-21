"""Auth for the MVP.

- Admin endpoints: `X-Admin-Key: <ADMIN_API_KEY>` (or Bearer). If
  ADMIN_API_KEY is unset the API is open — local demo only.
- Student: POST /auth/login {email} exchanges a known BTU email for a
  signed bearer token (HMAC, stdlib). Production replaces this one
  function with BTU SSO/OAuth — endpoints already only see the token.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import Header, HTTPException


def make_token(email: str, secret: str, ttl_hours: int, verified: bool = False) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(
        {"email": email, "verified": verified,
         "exp": int(time.time()) + ttl_hours * 3600}).encode()).decode()
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def read_token_data(token: str, secret: str) -> dict | None:
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data if data["exp"] > time.time() else None
    except Exception:
        return None


def read_token(token: str, secret: str) -> str | None:
    data = read_token_data(token, secret)
    return data["email"] if data else None


class Auth:
    def __init__(self, settings):
        self.s = settings

    def require_admin(self, x_admin_key: str | None = Header(default=None),
                      authorization: str | None = Header(default=None)) -> None:
        if not self.s.admin_api_key:
            return
        bearer = authorization.removeprefix("Bearer ").strip() if authorization else None
        if x_admin_key != self.s.admin_api_key and bearer != self.s.admin_api_key:
            raise HTTPException(401, "Admin API key required (X-Admin-Key header)")

    def student_email(self, authorization: str | None = Header(default=None),
                      email: str | None = None) -> str:
        if authorization:
            data = read_token_data(authorization.removeprefix("Bearer ").strip(),
                                   self.s.app_secret)
            if not data:
                raise HTTPException(401, "Invalid or expired student token")
            if self.s.require_verified_account and not data.get("verified"):
                raise HTTPException(403, "Account verification required: "
                                         "confirm your email with the verification code first")
            return data["email"]
        if email and self.s.allow_dev_email_auth and not self.s.require_verified_account:
            return email  # demo fallback, only when verification is switched off
        raise HTTPException(401, "Sign in required (Authorization: Bearer <token>)")
