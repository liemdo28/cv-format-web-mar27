"""
CV Format Tool — Authentication & Authorization
JWT-based auth with role system: admin | staff | qc
"""

import os
import re
import time
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ── Config ───────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))  # 8 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

# ── Password hashing ─────────────────────────────────────────────
def hash_password(password: str) -> str:
    """HMAC-SHA256 based password hashing (no external deps)."""
    salt = secrets.token_hex(16)
    key = hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()
    return f"{salt}${key}"


def verify_password(password: str, stored: str) -> bool:
    """Verify password against stored HMAC hash."""
    try:
        salt, key = stored.split("$")
        expected = hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()
        return secrets.compare_digest(expected, key)
    except ValueError:
        return False


# ── JWT tokens ───────────────────────────────────────────────────
def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": int(time.time()),
        "exp": int(time.time()) + REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Role definitions ─────────────────────────────────────────────
ALLOWED_ROLES = {"admin", "staff", "qc"}

# Permission matrix: what each role can do
ROLE_PERMISSIONS = {
    "admin": {
        "cv:upload", "cv:parse", "cv:review", "cv:qc", "cv:export",
        "cv:delete", "cv:view_all", "cv:assign_qc",
        "user:create", "user:read", "user:update", "user:delete",
        "template:manage", "settings:manage",
        "audit:read",
    },
    "staff": {
        "cv:upload", "cv:parse", "cv:review",
        "cv:view_own", "cv:export",
    },
    "qc": {
        "cv:qc", "cv:view_all", "cv:export",
        "audit:read",
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def check_permission(role: str, permission: str):
    if not has_permission(role, permission):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {permission} (role: {role})"
        )


# ── FastAPI security scheme ─────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    sub: str
    email: str
    role: str
    type: str


class CurrentUser(BaseModel):
    id: str
    email: str
    role: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """Extract and validate JWT from Authorization header."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    return CurrentUser(
        id=payload["sub"],
        email=payload["email"],
        role=payload["role"],
    )


def require_role(*allowed_roles: str):
    """Dependency factory: restrict endpoint to specific roles."""
    def dependency(user: CurrentUser = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Allowed roles: {', '.join(allowed_roles)}"
            )
        return user
    return dependency


def require_permission(permission: str):
    """Dependency: require specific permission."""
    def dependency(user: CurrentUser = Depends(get_current_user)):
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
        return user
    return dependency


# ── Audit helper ────────────────────────────────────────────────
def log_action(
    user_id: str,
    user_role: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
):
    """Log an action to the audit log (non-blocking)."""
    try:
        from db import get_db_session, AuditLog
        with get_db_session() as session:
            log = AuditLog(
                user_id=user_id,
                user_role=user_role,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get("user-agent") if request else None,
            )
            session.add(log)
    except Exception as e:
        # Non-blocking — never break the main flow
        print(f"[AUDIT] Failed to log action: {e}")
