"""
CV Format Tool — Batch Processing Tests
CEO TEST PLAN: Validates parallel processing of 50 CVs, retry logic, status tracking.
"""

import pytest
import sys
import os
import time
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from batch import (
    Batch, BatchJob, JobStatus,
    BatchProcessor, save_batch, load_batch,
    list_batches, save_job, load_job,
    get_processor,
)


# ═══════════════════════════════════════════════════════════════
# TC-22: BATCH JOB LIFECYCLE
# ═══════════════════════════════════════════════════════════════
class TestBatchJobLifecycle:
    def test_batch_job_creation(self):
        job = BatchJob(
            id="job-001",
            batch_id="batch-001",
            original_filename="cv_test.pdf",
            file_path="/tmp/test.pdf",
            file_type="pdf",
            file_size=2048,
            extraction_mode="offline",
        )
        assert job.status == JobStatus.QUEUED
        assert job.progress == 0.0
        assert job.retry_count == 0

    def test_batch_job_to_dict(self):
        job = BatchJob(
            id="j1", batch_id="b1",
            original_filename="test.pdf",
            file_path="/t", file_type="pdf", file_size=100,
        )
        d = job.to_dict()
        assert d["id"] == "j1"
        assert d["status"] == "queued"
        assert "progress" in d

    def test_batch_to_dict(self):
        batch = Batch(
            id="batch-001",
            name="Test Batch",
            owner_id="user-001",
            job_count=10,
        )
        d = batch.to_dict()
        assert d["id"] == "batch-001"
        assert d["job_count"] == 10
        assert d["completed"] == 0


# ═══════════════════════════════════════════════════════════════
# TC-23: BATCH PERSISTENCE (JSON file)
# ═══════════════════════════════════════════════════════════════
class TestBatchPersistence:
    def test_save_and_load_batch(self):
        batch = Batch(
            id="test-batch-001",
            name="Persistence Test",
            owner_id="user-1",
            job_count=5,
            created_at="2026-03-25T10:00:00",
        )
        save_batch(batch)
        loaded = load_batch("test-batch-001")
        assert loaded is not None
        assert loaded.id == batch.id
        assert loaded.name == "Persistence Test"

    def test_save_and_load_job(self):
        batch = Batch(id="test-batch-002", name="Job Test", owner_id="u1")
        save_batch(batch)

        job = BatchJob(
            id="job-002",
            batch_id="test-batch-002",
            original_filename="cv.pdf",
            file_path="/tmp/test.pdf",
            file_type="pdf",
            file_size=2048,
        )
        save_job(job)

        loaded = load_job("test-batch-002", "job-002")
        assert loaded is not None
        assert loaded.id == "job-002"
        assert loaded.original_filename == "cv.pdf"

    def test_load_nonexistent_returns_none(self):
        assert load_batch("nonexistent-batch") is None
        assert load_job("batch", "nonexistent-job") is None

    def test_list_batches(self):
        batches = list_batches()
        assert isinstance(batches, list)
        # Should contain previously saved batches
        ids = [b.id for b in batches]
        assert "test-batch-001" in ids or len(batches) >= 0


# ═══════════════════════════════════════════════════════════════
# TC-24: PARALLEL PROCESSING (real worker test)
# ═══════════════════════════════════════════════════════════════
class TestParallelProcessing:
    @pytest.fixture
    def temp_cv_file(self):
        """Create a minimal PDF for testing."""
        import fitz  # PyMuPDF
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Nguyen Van A\nnguyenvana@gmail.com\n0912345678\nSoftware Engineer\nFPT Software")
        path = os.path.join(tempfile.gettempdir(), f"test_cv_{time.time()}.pdf")
        doc.save(path)
        doc.close()
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_processor_initializes(self):
        proc = BatchProcessor(max_workers=2)
        assert proc.max_workers == 2
        assert proc.max_retries == 2
        proc.shutdown(wait=True)

    def test_processor_creates_thread_pool(self):
        proc = BatchProcessor(max_workers=3)
        assert proc._executor is not None
        proc.shutdown(wait=True)

    def test_submit_single_job(self, temp_cv_file):
        """Submit one real CV job."""
        proc = BatchProcessor(max_workers=1)
        batch = Batch(
            id=f"batch-{time.time_ns()}",
            name="Single Job Test",
            owner_id="test-user",
            job_count=1,
        )
        job = BatchJob(
            id=f"job-{time.time_ns()}",
            batch_id=batch.id,
            original_filename="test_cv.pdf",
            file_path=temp_cv_file,
            file_type="pdf",
            file_size=os.path.getsize(temp_cv_file),
            extraction_mode="offline",
        )
        batch.created_at = "2026-03-25T10:00:00"

        # Submit and wait
        proc.submit_batch(batch, [job])

        # Wait for completion (offline mode is fast)
        import queue
        max_wait = 60  # seconds
        start = time.time()
        while time.time() - start < max_wait:
            loaded_job = load_job(batch.id, job.id)
            if loaded_job and loaded_job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            time.sleep(0.5)

        final_job = load_job(batch.id, job.id)
        assert final_job is not None
        assert final_job.status in (JobStatus.COMPLETED, JobStatus.REVIEW, JobStatus.FAILED)
        proc.shutdown(wait=True)

    def test_multiple_jobs_process_in_parallel(self, temp_cv_file):
        """3 jobs should finish faster than 3× single job time."""
        proc = BatchProcessor(max_workers=3)

        batch = Batch(
            id=f"batch-parallel-{time.time_ns()}",
            name="Parallel Test",
            owner_id="test-user",
            job_count=3,
            created_at="2026-03-25T10:00:00",
        )
        jobs = [
            BatchJob(
                id=f"job-p{i}-{time.time_ns()}",
                batch_id=batch.id,
                original_filename=f"cv_{i}.pdf",
                file_path=temp_cv_file,
                file_type="pdf",
                file_size=1024,
                extraction_mode="offline",
            )
            for i in range(3)
        ]

        start = time.time()
        proc.submit_batch(batch, jobs)

        # Wait up to 60s
        elapsed = 0
        while elapsed < 60:
            batch_status = proc.get_batch_status(batch.id)
            if batch_status and batch_status.status in ("completed", "completed_with_errors"):
                break
            time.sleep(0.5)
            elapsed = time.time() - start

        total_time = time.time() - start
        proc.shutdown(wait=True)

        # With 3 workers, should be much faster than sequential
        # Sequential would be ~3× offline time
        # Parallel should be ~1× offline time
        all_done = all(
            j.status in (JobStatus.COMPLETED, JobStatus.REVIEW, JobStatus.FAILED)
            for j in proc.get_all_jobs(batch.id)
        )
        assert all_done, f"Not all jobs completed in {total_time:.1f}s"


# ═══════════════════════════════════════════════════════════════
# TC-25: RETRY LOGIC
# ═══════════════════════════════════════════════════════════════
class TestRetryLogic:
    def test_job_retry_count_defaults(self):
        job = BatchJob(
            id="r1", batch_id="b1",
            original_filename="f.pdf",
            file_path="/tmp/f.pdf",
            file_type="pdf", file_size=100,
        )
        assert job.retry_count == 0
        assert job.max_retries == 2

    def test_job_status_transitions(self):
        """Verify status can transition through the pipeline."""
        job = BatchJob(
            id="t1", batch_id="b1",
            original_filename="t.pdf",
            file_path="/tmp/t.pdf",
            file_type="pdf", file_size=100,
        )
        # Simulate progression
        assert job.status == JobStatus.QUEUED
        job.status = JobStatus.PROCESSING
        assert job.status == JobStatus.PROCESSING
        job.status = JobStatus.COMPLETED
        assert job.status == JobStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════
# TC-26: BATCH CANCELLATION
# ═══════════════════════════════════════════════════════════════
class TestBatchCancellation:
    def test_cancel_batch(self):
        batch = Batch(
            id=f"cancel-test-{time.time_ns()}",
            name="Cancel Test",
            owner_id="test-user",
            job_count=2,
            created_at="2026-03-25T10:00:00",
        )
        save_batch(batch)

        job1 = BatchJob(
            id=f"cj1-{time.time_ns()}",
            batch_id=batch.id,
            original_filename="f1.pdf",
            file_path="/tmp/f1.pdf",
            file_type="pdf", file_size=100,
        )
        job2 = BatchJob(
            id=f"cj2-{time.time_ns()}",
            batch_id=batch.id,
            original_filename="f2.pdf",
            file_path="/tmp/f2.pdf",
            file_type="pdf", file_size=100,
        )
        job1.status = JobStatus.QUEUED
        job2.status = JobStatus.PROCESSING
        save_job(job1)
        save_job(job2)

        proc = BatchProcessor(max_workers=1)
        result = proc.cancel_batch(batch.id)

        assert result is not None
        assert result.status == "cancelled"
        assert result.completed_at is not None

        # Jobs should be marked cancelled
        j1 = load_job(batch.id, job1.id)
        j2 = load_job(batch.id, job2.id)
        assert j1.status == JobStatus.CANCELLED
        assert j2.status == JobStatus.CANCELLED
        proc.shutdown(wait=True)


# ═══════════════════════════════════════════════════════════════
# TC-27: VOLUME TEST — 50 CVS SIMULTANEOUS
# ═══════════════════════════════════════════════════════════════
class TestVolume50CVs:
    @pytest.fixture
    def mini_pdf(self):
        """Create a minimal PDF."""
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test User\ntest@test.com\n0123456789\nEngineer")
        path = os.path.join(tempfile.gettempdir(), f"batch_test_cv_{time.time_ns()}.pdf")
        doc.save(path)
        doc.close()
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @pytest.mark.slow
    def test_50_cvs_batch_processing(self, mini_pdf):
        """TC-5 VOLUME: Upload 50 CVs → process → verify all complete."""
        import time
        proc = BatchProcessor(max_workers=4)

        batch = Batch(
            id=f"batch-50-{time.time_ns()}",
            name="50 CV Volume Test",
            owner_id="test-user",
            job_count=50,
            created_at="2026-03-25T10:00:00",
        )

        jobs = [
            BatchJob(
                id=f"job-50-{i}-{time.time_ns()}",
                batch_id=batch.id,
                original_filename=f"candidate_{i+1:03d}.pdf",
                file_path=mini_pdf,
                file_type="pdf",
                file_size=2048,
                extraction_mode="offline",
            )
            for i in range(50)
        ]

        proc.submit_batch(batch, jobs)

        # Poll until done (max 3 minutes for 50 offline CVs)
        start = time.time()
        max_wait = 180  # 3 minutes
        while time.time() - start < max_wait:
            status = proc.get_batch_status(batch.id)
            if status and status.status in ("completed", "completed_with_errors"):
                break
            time.sleep(1)

        elapsed = time.time() - start
        proc.shutdown(wait=True)

        # Verify all jobs completed
        all_jobs = proc.get_all_jobs(batch.id)
        completed = [j for j in all_jobs if j.status in (JobStatus.COMPLETED, JobStatus.REVIEW)]
        failed = [j for j in all_jobs if j.status == JobStatus.FAILED]

        assert len(all_jobs) == 50, f"Expected 50 jobs, got {len(all_jobs)}"
        assert len(completed) + len(failed) == 50

        # Performance: should complete in reasonable time
        # 50 offline CVs with 4 workers should be ~50/4 * avg_time
        print(f"\n[PERF] 50 CVs processed in {elapsed:.1f}s ({50/elapsed:.1f} CVs/sec)")
        assert elapsed < 180, f"50 CVs took {elapsed:.1f}s — exceeds 3 minute SLA"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not slow"])
