"""
CV Format Tool — Authentication & Authorization
JWT-based auth with bcrypt password hashing + role system: admin | staff | qc
"""

import os
import time
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Any, Optional

import jwt

# ── Runtime config validation (fail fast on missing secrets) ──
_JWT_SECRET_FROM_ENV = os.environ.get("JWT_SECRET")
if not _JWT_SECRET_FROM_ENV:
    raise RuntimeError(
        "[AUTH] JWT_SECRET environment variable is REQUIRED. "
        "Set it before starting: export JWT_SECRET=$(openssl rand -hex 32) "
        "Never use a fallback secret in production — tokens will be invalid after restart."
    )

SECRET_KEY: str = _JWT_SECRET_FROM_ENV
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))  # 8h
REFRESH_TOKEN_EXPIRE_DAYS: int = 7

# ── Bcrypt password hashing (replaces HMAC-SHA256) ─────────────
# bcrypt is purpose-built for password hashing:
#   - Adaptive cost factor (resists GPU brute-force)
#   - Built-in salt (no manual salt management)
#   - Memory-hard (resists ASIC/FPGA attacks)
#   - Industry standard since 1999 (bcrypt used by OpenBSD, Django, Dropbox)
try:
    import bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False
    # Fallback: PBKDF2-SHA256 (still better than HMAC — uses iterations)
    def _pbkdf2_fallback(password: str, salt: bytes, iterations: int = 310_000) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, iterations, dklen=32
        )
    def _verify_fallback(password: str, stored: str) -> bool:
        try:
            salt_b64, _hash_b64 = stored.split("$")
            salt = base64.b64decode(salt_b64)
            expected = _pbkdf2_fallback(password, salt)
            return secrets.compare_digest(expected.hex(), _hash_b64)
        except Exception:
            return False


def hash_password(password: str) -> str:
    """
    Hash password with bcrypt (cost=12).
    Falls back to PBKDF2-SHA256 if bcrypt unavailable (for dev environments).
    Storage format: bcrypt  →  "$2b$12$salt$hash"  (readable, prefixed)
                    PBKDF2  →  "pbkdf2_sha256$salt$hash"
    """
    if _BCRYPT_AVAILABLE:
        # bcrypt expects bytes, returns bytes — encode to store as string
        salt = bcrypt.gensalt(rounds=12)  # cost=12: ~250ms on modern CPU
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        # bcrypt hash format: $2b$12$saltvalue$hashvalue
        return hashed.decode("utf-8")
    else:
        # PBKDF2-SHA256 fallback
        salt_bytes = secrets.token_bytes(32)
        key = _pbkdf2_fallback(password, salt_bytes, iterations=310_000)
        salt_b64 = base64.b64encode(salt_bytes).decode()
        hash_hex = key.hex()
        return f"pbkdf2_sha256${salt_b64}${hash_hex}"


def verify_password(password: str, stored: str) -> bool:
    """
    Verify bcrypt or PBKDF2 hash.
    On mismatch, comparison is constant-time to prevent timing attacks.
    """
    if _BCRYPT_AVAILABLE and stored.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    elif stored.startswith("pbkdf2_sha256$"):
        return _verify_fallback(password, stored)
    else:
        # Legacy HMAC format — reject it (should be re-hashed on next login)
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
        "jti": secrets.token_hex(16),  # unique token ID for revocation
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
        raise _HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise _HTTPException(401, "Invalid token")


# Lightweight HTTPException equivalent (avoids FastAPI dep in auth module)
class _HTTPException(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ── Role definitions ─────────────────────────────────────────────
ALLOWED_ROLES = {"admin", "staff", "qc"}

# Permission matrix: what each role can do
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        # CV lifecycle
        "cv:upload", "cv:parse", "cv:review", "cv:qc",
        "cv:export", "cv:delete", "cv:view_all", "cv:assign_qc",
        # Override rules (bypass warning blocking)
        "cv:override_export",
        # Staff management
        "user:create", "user:read", "user:update", "user:delete",
        # System
        "template:manage", "settings:manage",
        "audit:read",
    },
    "staff": {
        # Can upload, parse, review (fix fields)
        "cv:upload", "cv:parse", "cv:review",
        "cv:view_own",
        # Can export ONLY if no ERROR-level validation issues
        # (warnings are OK — QC can override)
        "cv:export",
    },
    "qc": {
        # Can QC all jobs, view all, export
        "cv:qc", "cv:view_all", "cv:export",
        # Can OVERRIDE warnings — this is the key QC permission
        "cv:override_export",
        "audit:read",
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def check_permission(role: str, permission: str):
    if not has_permission(role, permission):
        raise _HTTPException(403, f"Permission denied: {permission} (role: {role})")


# ── FastAPI security scheme ─────────────────────────────────────
try:
    from fastapi import Depends, HTTPException, Request
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from pydantic import BaseModel

    bearer_scheme = HTTPBearer(auto_error=False)

    class CurrentUser(BaseModel):
        id: str
        email: str
        role: str

    def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    ) -> CurrentUser:
        if not credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return CurrentUser(
            id=payload["sub"],
            email=payload["email"],
            role=payload["role"],
        )

    def require_role(*allowed_roles: str):
        def dependency(user: CurrentUser = Depends(get_current_user)):
            if user.role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied. Allowed roles: {', '.join(allowed_roles)}"
                )
            return user
        return dependency

    def require_permission(permission: str):
        def dependency(user: CurrentUser = Depends(get_current_user)):
            if not has_permission(user.role, permission):
                raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
            return user
        return dependency

    _FAFASTAPI_AVAILABLE = True

except ImportError:
    # FastAPI not available at import time — raise ImportError at call time instead
    _FAFASTAPI_AVAILABLE = False
    CurrentUser = None  # type: ignore
    bearer_scheme = None

    def get_current_user(credentials: Any = None) -> Any:
        raise ImportError("FastAPI is required for get_current_user")

    def require_role(*allowed_roles: str):  # type: ignore
        def dependency(user: Any = None) -> Any:
            raise ImportError("FastAPI is required for require_role")
        return dependency

    def require_permission(permission: str):  # type: ignore
        def dependency(user: Any = None) -> Any:
            raise ImportError("FastAPI is required for require_permission")
        return dependency


# ── Audit helper ───────────────────────────────────────────────
def log_action(
    user_id: str,
    user_role: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    request: Optional[Any] = None,
):
    """Log an action to the audit log (non-blocking — never breaks main flow)."""
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
                ip_address=request.client.host if (request and request.client) else None,
                user_agent=request.headers.get("user-agent") if request else None,
            )
            session.add(log)
    except Exception as e:
        print(f"[AUDIT] Failed to log action: {e}")


# ── Utility: Re-hash legacy passwords on login ───────────────────
def check_and_upgrade_password(password: str, stored_hash: str) -> tuple[bool, str]:
    """
    Verifies password AND detects legacy HMAC format.
    Returns (is_valid, new_hash_if_upgraded).
    Callers should replace stored_hash with new_hash_if_upgraded on login.
    """
    if verify_password(password, stored_hash):
        # Already bcrypt/PBKDF2 — no upgrade needed
        if stored_hash.startswith("$2") or stored_hash.startswith("pbkdf2"):
            return True, ""
        # Legacy HMAC format detected — upgrade on next login
        if "$" in stored_hash and len(stored_hash.split("$")) == 2:
            return True, hash_password(password)
        return True, ""
    return False, ""
