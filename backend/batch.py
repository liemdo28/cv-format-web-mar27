"""
CV Format Tool — Batch Processing Engine
Async job queue with worker pool for 50+ CV/day scale.
Uses threading + SQLite for local, easily swappable to Celery+Redis for production.
"""

import os
import json
import uuid
import time
import threading
import queue
import tempfile
import shutil
from datetime import datetime
from typing import Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
import traceback


# ── Job status ───────────────────────────────────────────────────
class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PARSED = "parsed"
    VALIDATED = "validated"
    REVIEW = "review"
    APPROVED = "approved"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchJob:
    """Represents a single CV processing job within a batch."""
    id: str
    batch_id: str
    original_filename: str
    file_path: str        # Temp path to uploaded file
    file_type: str        # pdf | docx
    file_size: int        # bytes
    status: str = JobStatus.QUEUED
    extraction_mode: str = "auto"
    progress: float = 0.0  # 0.0 - 1.0
    message: str = ""
    result: dict | None = None
    validation_result: dict | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 2
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "validation_result": self.validation_result,
            "error": self.error,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class Batch:
    """A batch = collection of jobs uploaded together."""
    id: str
    name: str
    owner_id: str
    job_count: int = 0
    completed: int = 0
    failed: int = 0
    status: str = "running"  # running | completed | cancelled
    created_at: str = ""
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "job_count": self.job_count,
            "completed": self.completed,
            "failed": self.failed,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ── Storage (JSON file-based for local, swap to Redis/DB in prod) ──
BATCH_DIR = os.path.join(tempfile.gettempdir(), "cvformat_batches")
os.makedirs(BATCH_DIR, exist_ok=True)


def _job_path(batch_id: str, job_id: str) -> str:
    d = os.path.join(BATCH_DIR, batch_id)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{job_id}.json")


def _batch_path(batch_id: str) -> str:
    return os.path.join(BATCH_DIR, f"batch_{batch_id}.json")


def save_job(job: BatchJob):
    with open(_job_path(job.batch_id, job.id), "w", encoding="utf-8") as f:
        json.dump(job.to_dict(), f, ensure_ascii=False, indent=2)


def load_job(batch_id: str, job_id: str) -> BatchJob | None:
    path = _job_path(batch_id, job_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return BatchJob(**d)


def save_batch(batch: Batch):
    with open(_batch_path(batch.id), "w", encoding="utf-8") as f:
        json.dump(batch.to_dict(), f, ensure_ascii=False, indent=2)


def load_batch(batch_id: str) -> Batch | None:
    path = _batch_path(batch_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return Batch(**d)


def list_batches() -> list[Batch]:
    batches = []
    for fname in os.listdir(BATCH_DIR):
        if fname.startswith("batch_") and fname.endswith(".json"):
            path = os.path.join(BATCH_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                batches.append(Batch(**json.load(f)))
    return sorted(batches, key=lambda b: b.created_at, reverse=True)


# ── Progress callbacks ──────────────────────────────────────────
ProgressCallback = Callable[[BatchJob], None]


# ── Batch Processor ──────────────────────────────────────────────

class BatchProcessor:
    """
    Manages parallel CV processing with:
    - Thread pool (configurable worker count)
    - Per-job retry logic
    - Progress tracking
    - Phase-based status updates (queued → processing → parsed → validated → completed)
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_retries: int = 2,
        progress_callback: ProgressCallback | None = None,
    ):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.progress_callback = progress_callback

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_jobs: dict[str, Future] = {}
        self._lock = threading.Lock()

        # Import CV processing functions lazily
        self._processor = None

    def _get_processor(self):
        """Lazy import to avoid circular deps."""
        if self._processor is None:
            # Import main app's processing logic
            from main import (
                extract_text_from_pdf, extract_text_from_docx,
                detect_language_from_text, extract_cv_data,
                fill_template, build_suggested_name,
                TEMPLATE_EN, TEMPLATE_VN, OUTPUT_DIR,
            )
            self._processor = {
                "extract_text_from_pdf": extract_text_from_pdf,
                "extract_text_from_docx": extract_text_from_docx,
                "detect_language_from_text": detect_language_from_text,
                "extract_cv_data": extract_cv_data,
                "fill_template": fill_template,
                "build_suggested_name": build_suggested_name,
                "TEMPLATE_EN": TEMPLATE_EN,
                "TEMPLATE_VN": TEMPLATE_VN,
                "OUTPUT_DIR": OUTPUT_DIR,
            }
        return self._processor

    def _process_single_job(self, job: BatchJob) -> BatchJob:
        """Process one CV job through the full pipeline."""
        proc = self._get_processor()
        now = datetime.utcnow().isoformat()

        try:
            # Phase 1: Extract text
            job.status = JobStatus.PROCESSING
            job.started_at = now
            job.progress = 0.1
            job.message = "Đang trích xuất text..."
            save_job(job)
            self._notify(job)

            ext = job.file_type.lower()
            if ext == "pdf":
                cv_text = proc["extract_text_from_pdf"](job.file_path)
            else:
                cv_text = proc["extract_text_from_docx"](job.file_path)

            if not cv_text.strip():
                raise ValueError("Could not extract text from CV (possibly image-based PDF)")

            # Phase 2: Detect language + select template
            job.progress = 0.2
            job.message = "Đang phát hiện ngôn ngữ..."
            save_job(job)
            self._notify(job)

            lang = proc["detect_language_from_text"](cv_text)
            template_path = proc["TEMPLATE_VN"] if lang == "vi" else proc["TEMPLATE_EN"]

            # Phase 3: AI extraction
            job.progress = 0.3
            job.message = "Đang trích xuất dữ liệu bằng AI..."
            save_job(job)
            self._notify(job)

            cv_data = proc["extract_cv_data"](
                cv_text=cv_text,
                api_key="",
                model="claude-sonnet-4-20250514",
                mode=job.extraction_mode,
                openai_key="",
                openai_model="gpt-4o-mini",
            )

            job.status = JobStatus.PARSED
            job.progress = 0.5
            job.message = "Đã parse xong"
            save_job(job)
            self._notify(job)

            # Phase 4: Validate
            job.progress = 0.6
            job.message = "Đang kiểm tra dữ liệu..."
            save_job(job)
            self._notify(job)

            from validation import validate_cv_data
            val_result = validate_cv_data(cv_data)
            job.validation_result = val_result.to_dict()
            job.status = JobStatus.VALIDATED
            job.progress = 0.7
            job.message = f"Validation: {val_result.summary}"
            save_job(job)
            self._notify(job)

            # Phase 5: Fill template
            job.progress = 0.8
            job.message = "Đang điền template..."
            save_job(job)
            self._notify(job)

            suggested_name = proc["build_suggested_name"](cv_data)
            safe_name = "".join(c if c.isalnum() or c in " -._" else "_" for c in (suggested_name or job.original_filename))
            safe_name = safe_name.replace(" ", "_")[:100]

            download_id = job.id[:8]
            output_dir = os.path.join(proc["OUTPUT_DIR"], download_id)
            os.makedirs(output_dir, exist_ok=True)
            output_docx = os.path.join(output_dir, f"{safe_name}.docx")

            proc["fill_template"](template_path, cv_data, "CLIENT", "POSITION", output_docx)

            # Phase 6: Done
            job.progress = 1.0
            job.status = JobStatus.COMPLETED if val_result.is_exportable else JobStatus.REVIEW
            job.completed_at = datetime.utcnow().isoformat()
            job.message = f"Hoàn thành — {val_result.summary}"
            job.result = {
                "download_id": download_id,
                "output_filename": f"{safe_name}.docx",
                "output_path": output_docx,
                "suggested_name": suggested_name,
                "language": lang,
                "cv_data": cv_data,
                "validation": val_result.to_dict(),
            }
            save_job(job)
            self._notify(job)

        except Exception as e:
            tb = traceback.format_exc()
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow().isoformat()
            job.message = f"Lỗi: {str(e)[:100]}"
            save_job(job)
            self._notify(job)
            print(f"[BATCH] Job {job.id} failed: {e}\n{tb}")

        return job

    def _notify(self, job: BatchJob):
        if self.progress_callback:
            try:
                self.progress_callback(job)
            except Exception as e:
                print(f"[BATCH] Callback error: {e}")

    def submit_batch(self, batch: Batch, jobs: list[BatchJob]) -> Batch:
        """Submit a batch of jobs for parallel processing."""
        save_batch(batch)

        for job in jobs:
            job.created_at = datetime.utcnow().isoformat()
            save_job(job)

        with self._lock:
            for job in jobs:
                future = self._executor.submit(self._process_single_job, job)
                self._active_jobs[job.id] = future

        return batch

    def get_job_status(self, batch_id: str, job_id: str) -> BatchJob | None:
        with self._lock:
            if job_id in self._active_jobs:
                fut = self._active_jobs[job_id]
                if fut.done():
                    # Already processed — return saved version
                    pass
        return load_job(batch_id, job_id)

    def get_batch_status(self, batch_id: str) -> Batch | None:
        batch = load_batch(batch_id)
        if not batch:
            return None

        # Recompute counts from jobs
        batch_dir = os.path.join(BATCH_DIR, batch_id)
        if os.path.exists(batch_dir):
            completed = 0
            failed = 0
            for fname in os.listdir(batch_dir):
                if fname.endswith(".json"):
                    with open(os.path.join(batch_dir, fname), "r", encoding="utf-8") as f:
                        j = json.load(f)
                    if j["status"] in (JobStatus.COMPLETED, JobStatus.APPROVED, JobStatus.EXPORTING):
                        completed += 1
                    elif j["status"] == JobStatus.FAILED:
                        failed += 1
            batch.completed = completed
            batch.failed = failed

            # Update batch status
            all_jobs = [
                json.load(open(os.path.join(batch_dir, f), "r", encoding="utf-8"))
                for f in os.listdir(batch_dir) if f.endswith(".json")
            ]
            still_running = any(
                j["status"] in (JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.PARSED,
                                JobStatus.VALIDATED, JobStatus.EXPORTING)
                for j in all_jobs
            )
            if not still_running:
                batch.status = "completed" if batch.failed == 0 else "completed_with_errors"
                batch.completed_at = datetime.utcnow().isoformat()

        save_batch(batch)
        return batch

    def get_all_jobs(self, batch_id: str) -> list[BatchJob]:
        batch_dir = os.path.join(BATCH_DIR, batch_id)
        if not os.path.exists(batch_dir):
            return []
        jobs = []
        for fname in os.listdir(batch_dir):
            if fname.endswith(".json"):
                with open(os.path.join(batch_dir, fname), "r", encoding="utf-8") as f:
                    jobs.append(BatchJob(**json.load(f)))
        return sorted(jobs, key=lambda j: j.created_at)

    def cancel_batch(self, batch_id: str) -> Batch | None:
        batch = load_batch(batch_id)
        if not batch:
            return None
        batch.status = "cancelled"
        batch.completed_at = datetime.utcnow().isoformat()
        save_batch(batch)

        # Cancel pending jobs
        for job in self.get_all_jobs(batch_id):
            if job.status in (JobStatus.QUEUED, JobStatus.PROCESSING):
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.utcnow().isoformat()
                job.message = "Cancelled by user"
                save_job(job)
        return batch

    def shutdown(self, wait: bool = True):
        self._executor.shutdown(wait=wait)


# ── Global processor instance ───────────────────────────────────
_processor: BatchProcessor | None = None
_processor_lock = threading.Lock()


def get_processor() -> BatchProcessor:
    global _processor
    with _processor_lock:
        if _processor is None:
            max_workers = int(os.environ.get("CVFORMAT_MAX_WORKERS", "4"))
            _processor = BatchProcessor(max_workers=max_workers)
        return _processor
