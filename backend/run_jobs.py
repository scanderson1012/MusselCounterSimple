"""In-memory run-job state used by `/predict` progress polling.

This module tracks exactly one active model_execution run at a time. A "run job"
represents the current background model execution and stores:
- Progress counters (`processed_images`, `total_images`)
- Lifecycle status (`running`, `completed`, `failed`)
- Metadata used by frontend status messaging
- Final run payload (when completed)
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone
from threading import Lock
from typing import Any
from uuid import uuid4


# Single active run-job record (or `None` when idle).
_RUN_JOB_DATA: dict[str, Any] | None = None
# Global lock for all run-job reads/writes.
_RUN_JOB_LOCK = Lock()


def curr_time_in_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def get_current_run_job() -> dict[str, Any] | None:
    """Return the active run job only when its status is `running`.

    Returns a deep copy so callers cannot mutate shared in-memory state.
    """
    with _RUN_JOB_LOCK:
        if _RUN_JOB_DATA is None:
            return None
        if _RUN_JOB_DATA["status"] != "running":
            return None
        return deepcopy(_RUN_JOB_DATA)


def is_a_run_job_already_running() -> bool:
    """Return whether a run job is currently active."""
    return get_current_run_job() is not None


def create_run_job(
    run_id: int,
    total_images: int,
    skipped_images: list[str],
    skipped_image_ids: list[int],
    invalid_image_ids: list[int],
    using_new_model: bool,
    processed_run_image_ids: list[int],
) -> dict[str, Any]:
    """Create a new run job and set it as the current active job.

    Raises:
    - `RuntimeError` when another run job is already running.
    """
    global _RUN_JOB_DATA

    # Generate a stable opaque ID for frontend polling.
    # Polling means the frontend repeatedly calls the status endpoint
    # (every few seconds) until this background run finishes.
    run_job_id = uuid4().hex
    run_job_data: dict[str, Any] = {
        "run_job_id": run_job_id,
        "status": "running",
        "run_id": run_id,
        "processed_images": 0,
        "total_images": int(total_images),
        "estimated_remaining_seconds": None,
        "skipped_images": list(skipped_images),
        "skipped_image_ids": list(skipped_image_ids),
        "invalid_image_ids": list(invalid_image_ids),
        "using_new_model": using_new_model,
        "processed_run_image_ids": list(processed_run_image_ids),
        "error_message": None,
        "run": None,
        "created_at": curr_time_in_iso(),
        "updated_at": curr_time_in_iso(),
    }

    with _RUN_JOB_LOCK:
        # Keep backend behavior simple: only one concurrent model_execution job.
        if _RUN_JOB_DATA is not None and _RUN_JOB_DATA["status"] == "running":
            raise RuntimeError("A run job is already running.")
        _RUN_JOB_DATA = run_job_data
        # Return copy so external callers do not mutate shared state.
        return deepcopy(_RUN_JOB_DATA)


def get_run_job(run_job_id: str) -> dict[str, Any] | None:
    """Return run-job data for a specific run-job ID, or `None` if not found."""
    with _RUN_JOB_LOCK:
        if _RUN_JOB_DATA is None:
            return None
        if _RUN_JOB_DATA["run_job_id"] != run_job_id:
            return None
        return deepcopy(_RUN_JOB_DATA)


def update_run_job_progress(
    run_job_id: str, processed_images: int, total_images: int
) -> None:
    """Update progress counters for the current run job.

    Values are clamped to valid non-negative ranges and `processed_images` is
    bounded by `total_images` when total is known.
    """
    with _RUN_JOB_LOCK:
        if _RUN_JOB_DATA is None:
            return
        if _RUN_JOB_DATA["run_job_id"] != run_job_id:
            return

        # Normalize values so callers can pass loosely typed numbers safely.
        bounded_total_images = max(0, int(total_images))
        bounded_processed_images = max(0, int(processed_images))
        if bounded_total_images > 0:
            bounded_processed_images = min(bounded_processed_images, bounded_total_images)

        created_at = datetime.fromisoformat(str(_RUN_JOB_DATA["created_at"]))
        elapsed_seconds = max((datetime.now(timezone.utc) - created_at).total_seconds(), 0.0)
        estimated_remaining_seconds = None
        if bounded_processed_images > 0 and bounded_total_images > bounded_processed_images:
            seconds_per_image = elapsed_seconds / bounded_processed_images
            estimated_remaining_seconds = max(
                0,
                int(round(seconds_per_image * (bounded_total_images - bounded_processed_images))),
            )

        _RUN_JOB_DATA["processed_images"] = bounded_processed_images
        _RUN_JOB_DATA["total_images"] = bounded_total_images
        _RUN_JOB_DATA["estimated_remaining_seconds"] = estimated_remaining_seconds
        _RUN_JOB_DATA["updated_at"] = curr_time_in_iso()


def complete_run_job(run_job_id: str, run_data: dict[str, Any]) -> None:
    """Mark a run job as completed and attach the final run payload."""
    with _RUN_JOB_LOCK:
        if _RUN_JOB_DATA is None:
            return
        if _RUN_JOB_DATA["run_job_id"] != run_job_id:
            return

        _RUN_JOB_DATA["status"] = "completed"
        # Completed jobs should always report full progress.
        _RUN_JOB_DATA["processed_images"] = int(
            _RUN_JOB_DATA["total_images"]
        )
        _RUN_JOB_DATA["estimated_remaining_seconds"] = 0
        _RUN_JOB_DATA["run"] = deepcopy(run_data)
        _RUN_JOB_DATA["updated_at"] = curr_time_in_iso()


def fail_run_job(run_job_id: str, error_message: str) -> None:
    """Mark a run job as failed and store a user-visible error message."""
    with _RUN_JOB_LOCK:
        if _RUN_JOB_DATA is None:
            return
        if _RUN_JOB_DATA["run_job_id"] != run_job_id:
            return

        _RUN_JOB_DATA["status"] = "failed"
        _RUN_JOB_DATA["error_message"] = error_message
        _RUN_JOB_DATA["estimated_remaining_seconds"] = None
        _RUN_JOB_DATA["updated_at"] = curr_time_in_iso()
