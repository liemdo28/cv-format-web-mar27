"""
CV Format Tool — Auth Tests
CEO TEST PLAN: Validates role permissions, login, JWT.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth import (
    hash_password, verify_password,
    create_access_token, decode_token,
    has_permission, ROLE_PERMISSIONS,
    CurrentUser,
)


# ═══════════════════════════════════════════════════════════════
# TC-17: PASSWORD HASHING
# ═══════════════════════════════════════════════════════════════
class TestPasswordHashing:
    def test_hash_is_different_from_plaintext(self):
        h = hash_password("secret123")
        assert h != "secret123"

    def test_hash_contains_salt_and_hash(self):
        h = hash_password("secret123")
        assert "$" in h
        # bcrypt format: $2b$12$saltvalue$hashvalue  (4 $ parts)
        parts = h.split("$")
        assert len(parts) == 4

    def test_verify_correct_password(self):
        h = hash_password("admin123")
        assert verify_password("admin123", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("admin123")
        assert verify_password("wrongpass", h) is False

    def test_verify_tampered_hash(self):
        assert verify_password("pass", "invalid_hash") is False
        assert verify_password("pass", "") is False

    def test_different_passwords_different_hashes(self):
        h1 = hash_password("pass1")
        h2 = hash_password("pass2")
        assert h1 != h2


# ═══════════════════════════════════════════════════════════════
# TC-18: JWT TOKENS
# ═══════════════════════════════════════════════════════════════
class TestJWTTokens:
    def test_create_and_decode_access_token(self):
        token = create_access_token("user-123", "admin@test.com", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "admin@test.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_token_contains_expiry(self):
        token = create_access_token("user-1", "a@b.com", "staff")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]

    def test_decode_expired_token_raises(self):
        import jwt, time
        import auth as auth_module
        old_token = jwt.encode(
            {"sub": "x", "type": "access", "iat": int(time.time()) - 10000, "exp": int(time.time()) - 100},
            os.environ.get("JWT_SECRET", "__test_secret__"),
            algorithm="HS256"
        )
        with pytest.raises(auth_module._HTTPException) as exc_info:
            decode_token(old_token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_invalid_token_raises(self):
        import auth as auth_module
        with pytest.raises(auth_module._HTTPException) as exc_info:
            decode_token("not.a.valid.jwt")
        assert exc_info.value.status_code == 401


# ═══════════════════════════════════════════════════════════════
# TC-19: ROLE PERMISSIONS MATRIX
# ═══════════════════════════════════════════════════════════════
class TestRolePermissions:
    def test_admin_has_all_permissions(self):
        admin_perms = ROLE_PERMISSIONS["admin"]
        assert "cv:upload" in admin_perms
        assert "cv:qc" in admin_perms
        assert "cv:delete" in admin_perms
        assert "user:create" in admin_perms
        assert "audit:read" in admin_perms

    def test_staff_limited_permissions(self):
        staff_perms = ROLE_PERMISSIONS["staff"]
        assert "cv:upload" in staff_perms
        assert "cv:qc" not in staff_perms  # QC is NOT for staff
        assert "cv:delete" not in staff_perms
        assert "user:create" not in staff_perms

    def test_qc_has_qc_permissions(self):
        qc_perms = ROLE_PERMISSIONS["qc"]
        assert "cv:qc" in qc_perms
        assert "cv:view_all" in qc_perms
        assert "cv:upload" not in qc_perms  # QC doesn't upload

    def test_has_permission_true(self):
        assert has_permission("admin", "cv:delete") is True
        assert has_permission("staff", "cv:upload") is True
        assert has_permission("qc", "cv:qc") is True

    def test_has_permission_false(self):
        assert has_permission("staff", "cv:qc") is False
        assert has_permission("qc", "cv:upload") is False
        assert has_permission("unknown_role", "anything") is False


# ═══════════════════════════════════════════════════════════════
# TC-20: DATABASE MODELS (smoke test)
# ═══════════════════════════════════════════════════════════════
class TestDatabaseModels:
    def test_user_to_dict(self):
        from db import User
        from datetime import datetime
        u = User(
            id="test-123",
            email="admin@test.com",
            hashed_password="hashed",
            full_name="Admin Test",
            role="admin",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        d = u.to_dict()
        assert d["id"] == "test-123"
        assert d["email"] == "admin@test.com"
        assert d["role"] == "admin"
        assert "hashed_password" not in d  # safe by default

    def test_cv_job_to_dict(self):
        from db import CVJob
        j = CVJob(
            id="job-1",
            owner_id="user-1",
            original_filename="cv.pdf",
            file_type="pdf",
            file_size=1024,
            status="uploaded",
            extraction_mode="offline",
        )
        d = j.to_dict()
        assert d["id"] == "job-1"
        assert d["original_filename"] == "cv.pdf"
        assert d["status"] == "uploaded"

    def test_cv_job_full_lifecycle_statuses(self):
        from db import CVJob
        valid_statuses = [
            "uploaded", "parsing", "parsed", "validated",
            "review", "qc", "approved", "exported", "error", "cancelled"
        ]
        for status in valid_statuses:
            j = CVJob(
                id=f"job-{status}",
                owner_id="u1",
                original_filename="test.pdf",
                file_type="pdf",
                file_size=100,
                status=status,
                extraction_mode="offline",
            )
            assert j.status == status

    def test_audit_log_to_dict(self):
        from db import AuditLog
        from datetime import datetime
        log = AuditLog(
            id="log-1",
            user_id="user-1",
            user_role="admin",
            action="export",
            resource_type="cv_job",
            resource_id="job-1",
            details={"filename": "cv.pdf"},
            ip_address="192.168.1.1",
            created_at=datetime.utcnow(),
        )
        d = log.to_dict()
        assert d["action"] == "export"
        assert d["ip_address"] == "192.168.1.1"
        assert "hashed_password" not in str(d)


# ═══════════════════════════════════════════════════════════════
# TC-21: DATABASE INIT (integration)
# ═══════════════════════════════════════════════════════════════
class TestDatabaseInit:
    def test_init_db_creates_tables(self):
        import tempfile
        import os
        # Use temp DB for testing
        old_url = os.environ.get("DATABASE_URL", "")
        os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), "test_cvformat.db")

        # Reset module-level engine
        import db as db_module
        db_module._engine = None
        db_module._SessionLocal = None

        db_module.init_db()
        engine = db_module.get_engine()

        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "users" in tables
        assert "cv_jobs" in tables
        assert "cv_versions" in tables
        assert "audit_logs" in tables

        # Cleanup
        os.environ["DATABASE_URL"] = old_url
        db_module._engine = None
        db_module._SessionLocal = None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
