# type: ignore[all]
# pyright: ignoreFile
# This stub file tells the IDE the packages exist at runtime.
# Packages ARE in requirements.txt — all errors below are false positives.

import fitz
import openai
import anthropic
import uvicorn
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Any, Dict, List, Optional, Tuple, Union

def create_engine(url: str, **kwargs: Any) -> Any: ...
def declarative_base() -> Any: ...
def Column(*args: Any, **kwargs: Any) -> Any: ...
def sessionmaker(**kwargs: Any) -> Any: ...

class sqlite3: ...  # type: ignore
class sqlalchemy: ...  # type: ignore

# auth module
def hash_password(password: str) -> str: ...
def verify_password(password: str, stored: str) -> bool: ...
def create_access_token(user_id: str, email: str, role: str) -> str: ...
def create_refresh_token(user_id: str) -> str: ...
def decode_token(token: str) -> Dict[str, Any]: ...
def get_current_user(credentials: Any) -> Any: ...
def require_permission(permission: str) -> Any: ...
def require_role(*allowed_roles: str) -> Any: ...
def log_action(user_id: str, user_role: str, action: str, **kwargs: Any) -> None: ...
ROLE_PERMISSIONS: Dict[str, Any]
ALLOWED_ROLES: set[str]

# db module
def init_db() -> None: ...
def get_db_session() -> Any: ...

class User:  # type: ignore
    id: str
    email: str
    hashed_password: str
    full_name: str
    role: str
    is_active: bool
    def to_dict(self, safe: bool = True) -> Dict[str, Any]: ...

class CVJob:  # type: ignore
    id: str
    owner_id: str
    qc_by: Optional[str]
    original_filename: str
    file_size: int
    file_type: str
    status: str
    extraction_mode: str
    parsed_data: Optional[Dict[str, Any]]
    parsed_at: Any
    validation_errors: Optional[List[Dict[str, Any]]]
    validated_at: Any
    reviewed_data: Optional[Dict[str, Any]]
    reviewed_at: Any
    qc_result: Optional[str]
    qc_notes: Optional[str]
    qc_at: Any
    output_filename: Optional[str]
    output_path: Optional[str]
    download_url: Optional[str]
    exported_at: Any
    completed_at: Any
    created_at: Any
    updated_at: Any
    def to_dict(self, include_parsed: bool = False) -> Dict[str, Any]: ...

class CVVersion:  # type: ignore
    id: str
    job_id: str
    version_number: int
    changed_by_id: str
    changed_by_role: str
    change_type: str
    data_snapshot: Dict[str, Any]
    notes: Optional[str]
    created_at: Any
    def to_dict(self) -> Dict[str, Any]: ...

class AuditLog:  # type: ignore
    id: str
    user_id: str
    user_role: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: Any
    def to_dict(self) -> Dict[str, Any]: ...

# validation module
class ValidationSeverity: ...  # type: ignore

class ValidationError:  # type: ignore
    field: str
    code: str
    message: str
    severity: str
    value: Any
    suggestion: str
    def __init__(self, field: str, code: str, message: str, severity: str, value: Any = ..., suggestion: str = ...) -> None: ...

class ValidationResult:  # type: ignore
    is_valid: bool
    is_exportable: bool
    errors: List[Any]
    warnings: List[Any]
    info: List[Any]
    error_count: int
    warning_count: int
    summary: str
    def to_dict(self) -> Dict[str, Any]: ...

def validate_cv_data(cv_data: Dict[str, Any], strict: bool = False) -> ValidationResult: ...
def sanitize_for_export(cv_data: Dict[str, Any]) -> Dict[str, Any]: ...
def validate_batch(cv_data_list: List[Dict[str, Any]]) -> List[ValidationResult]: ...
def validate_email(value: str) -> Optional[ValidationError]: ...
def validate_phone(value: str, country: str = "auto") -> Optional[ValidationError]: ...
def validate_date_format(value: str, field_path: str = "period") -> Optional[ValidationError]: ...
def validate_year_of_birth(value: str) -> Optional[ValidationError]: ...
def validate_required_string(value: Any, field_name: str) -> Optional[ValidationError]: ...

# batch module
class JobStatus: ...  # type: ignore

class BatchJob:  # type: ignore
    id: str
    batch_id: str
    original_filename: str
    file_path: str
    file_type: str
    file_size: int
    status: str
    extraction_mode: str
    progress: float
    message: str
    result: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    error: Optional[str]
    retry_count: int
    max_retries: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    def to_dict(self) -> Dict[str, Any]: ...

class Batch:  # type: ignore
    id: str
    name: str
    owner_id: str
    job_count: int
    completed: int
    failed: int
    status: str
    created_at: str
    completed_at: Optional[str]
    def to_dict(self) -> Dict[str, Any]: ...

class BatchProcessor:  # type: ignore
    max_workers: int
    max_retries: int
    def submit_batch(self, batch: Batch, jobs: List[BatchJob]) -> Batch: ...
    def get_batch_status(self, batch_id: str) -> Optional[Batch]: ...
    def get_all_jobs(self, batch_id: str) -> List[BatchJob]: ...
    def cancel_batch(self, batch_id: str) -> Optional[Batch]: ...
    def shutdown(self, wait: bool = True) -> None: ...

def get_processor() -> BatchProcessor: ...
def save_batch(batch: Batch) -> None: ...
def load_batch(batch_id: str) -> Optional[Batch]: ...
def save_job(job: BatchJob) -> None: ...
def load_job(batch_id: str, job_id: str) -> Optional[BatchJob]: ...
def list_batches() -> List[Batch]: ...

# offline_engine module
def extract_offline(cv_text: str) -> Dict[str, Any]: ...
def build_suggested_name_offline(cv_data: Dict[str, Any]) -> str: ...
def fill_template_offline(template_path: str, output_path: str, cv_data: Dict[str, Any]) -> Dict[str, Any]: ...
def learn_mapping(placeholder: str, canonical_field: str) -> None: ...
def learn_from_training_pair(raw_text: str, done_text: str) -> Dict[str, Any]: ...
def load_learning_store() -> Dict[str, Any]: ...
def reset_learning_store() -> Dict[str, Any]: ...
