"""
CV Format Tool — Database Layer
SQLAlchemy models + SQLite (local) / PostgreSQL (production-ready)
"""

import os
import sqlite3
from datetime import datetime
from typing import Any, Optional
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    Boolean, Enum, ForeignKey, JSON, UniqueConstraint, Index,
)
from sqlalchemy.orm import (
    declarative_base, relationship, sessionmaker, Session
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.sqlite import BLOB
import uuid

Base = declarative_base()

# ── Environment ───────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////tmp/cvformat.db")

# ── Models ─────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="staff")  # admin | staff | qc
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    cv_jobs = relationship(
        "CVJob", foreign_keys="CVJob.owner_id",
        back_populates="owner", cascade="all, delete-orphan",
    )
    qc_jobs = relationship(
        "CVJob", foreign_keys="CVJob.qc_by",
        back_populates="qc_reviewer",
    )

    def to_dict(self, safe: bool = True) -> dict[str, Any]:
        d = {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        return d


class CVJob(Base):
    """
    One CV processing job = one input file.
    Tracks full lifecycle: uploaded → parsed → reviewed → QC'd → exported.
    """
    __tablename__ = "cv_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    qc_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    # File info
    original_filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)  # bytes
    file_type = Column(String(10), nullable=False)  # pdf | docx

    # Processing state
    status = Column(String(30), nullable=False, default="uploaded",
                    index=True)  # uploaded | parsing | parsed | review | qc | approved | exported | error
    extraction_mode = Column(String(30), nullable=True)  # offline | claude_api | openai_api | ollama

    # Parsed data (JSON blob)
    parsed_data = Column(JSON, nullable=True)
    parsed_at = Column(DateTime, nullable=True)

    # Validation results
    validation_errors = Column(JSON, nullable=True)  # list of ValidationError dicts
    validated_at = Column(DateTime, nullable=True)

    # Review data (staff corrections)
    reviewed_data = Column(JSON, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # QC result
    qc_result = Column(String(20), nullable=True)  # pass | fail | needs_revision
    qc_notes = Column(Text, nullable=True)
    qc_at = Column(DateTime, nullable=True)

    # Output
    output_filename = Column(String(500), nullable=True)
    output_path = Column(String(1000), nullable=True)
    download_url = Column(String(2000), nullable=True)
    exported_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relations
    owner = relationship("User", foreign_keys=[owner_id], back_populates="cv_jobs")
    qc_reviewer = relationship("User", foreign_keys=[qc_by], back_populates="qc_jobs")
    versions = relationship("CVVersion", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_cv_jobs_status_owner", "status", "owner_id"),
        Index("ix_cv_jobs_created", "created_at"),
    )

    def to_dict(self, include_parsed: bool = False) -> dict[str, Any]:
        d = {
            "id": self.id,
            "owner_id": self.owner_id,
            "qc_by": self.qc_by,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "status": self.status,
            "extraction_mode": self.extraction_mode,
            "parsed_at": self.parsed_at.isoformat() if self.parsed_at else None,
            "validation_errors": self.validation_errors,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "reviewed_data": self.reviewed_data,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "qc_result": self.qc_result,
            "qc_notes": self.qc_notes,
            "qc_at": self.qc_at.isoformat() if self.qc_at else None,
            "output_filename": self.output_filename,
            "download_url": self.download_url,
            "exported_at": self.exported_at.isoformat() if self.exported_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_parsed and self.parsed_data:
            d["parsed_data"] = self.parsed_data
        return d


class CVVersion(Base):
    """
    Version history for each CV job.
    Every edit by staff/QC creates a new version snapshot.
    """
    __tablename__ = "cv_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("cv_jobs.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)

    # Who made this version
    changed_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    changed_by_role = Column(String(20), nullable=False)  # admin | staff | qc
    change_type = Column(String(30), nullable=False)  # initial_parse | staff_review | qc_review | export

    # Snapshot
    data_snapshot = Column(JSON, nullable=False)  # full CV data at this version
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    job = relationship("CVJob", back_populates="versions")
    changed_by = relationship("User")

    __table_args__ = (
        UniqueConstraint("job_id", "version_number", name="uq_job_version"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "version_number": self.version_number,
            "changed_by_id": self.changed_by_id,
            "changed_by_role": self.changed_by_role,
            "change_type": self.change_type,
            "data_snapshot": self.data_snapshot,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(Base):
    """Immutable audit log for all critical actions."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    user_role = Column(String(20), nullable=False)
    action = Column(String(100), nullable=False, index=True)  # login | logout | upload | parse | review | qc | export | create_user | update_user
    resource_type = Column(String(50), nullable=True)  # cv_job | user | template
    resource_id = Column(String(36), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relation
    user = relationship("User")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Engine / Session ────────────────────────────────────────────
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        if DATABASE_URL.startswith("sqlite"):
            _engine = create_engine(
                DATABASE_URL,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
                echo=False,
            )
        else:
            _engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_db_session():
    """Thread-safe database session context manager."""
    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Create all tables. Safe to call multiple times."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _seed_default_admin()


def _seed_default_admin():
    """Create default admin if not exists (no demo users)."""
    from auth import hash_password
    with get_db_session() as session:
        existing = session.query(User).filter(User.role == "admin").first()
        if not existing:
            admin = User(
                email="admin@cvformat.local",
                hashed_password=hash_password("liem@dt2155"),
                full_name="System Admin",
                role="admin",
                is_active=True,
            )
            session.add(admin)
            session.commit()
            print("[DB] Seeded default admin user")
