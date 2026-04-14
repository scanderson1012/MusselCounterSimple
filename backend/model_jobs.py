"""In-memory background job state for model registration and evaluation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone
from threading import Lock
from typing import Any
from uuid import uuid4


_MODEL_JOB_DATA: dict[str, Any] | None = None
_MODEL_JOB_LOCK = Lock()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_model_job(display_name: str) -> dict[str, Any]:
    """Create one active model job and return its initial state."""
    global _MODEL_JOB_DATA

    model_job_id = uuid4().hex
    model_job_data = {
        "model_job_id": model_job_id,
        "status": "running",
        "display_name": display_name,
        "stage": "Preparing model registration",
        "processed_images": 0,
        "total_images": 0,
        "estimated_remaining_seconds": None,
        "error_message": None,
        "cancel_requested": False,
        "model_version": None,
        "evaluation": None,
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
    }

    with _MODEL_JOB_LOCK:
        if _MODEL_JOB_DATA is not None and _MODEL_JOB_DATA["status"] == "running":
            raise RuntimeError("A model registration job is already running.")
        _MODEL_JOB_DATA = model_job_data
        return deepcopy(_MODEL_JOB_DATA)


def get_model_job(model_job_id: str) -> dict[str, Any] | None:
    """Return one model job snapshot by ID."""
    with _MODEL_JOB_LOCK:
        if _MODEL_JOB_DATA is None:
            return None
        if _MODEL_JOB_DATA["model_job_id"] != model_job_id:
            return None
        return deepcopy(_MODEL_JOB_DATA)


def update_model_job_stage(model_job_id: str, stage: str) -> None:
    with _MODEL_JOB_LOCK:
        if _MODEL_JOB_DATA is None or _MODEL_JOB_DATA["model_job_id"] != model_job_id:
            return
        _MODEL_JOB_DATA["stage"] = str(stage)
        _MODEL_JOB_DATA["updated_at"] = _iso_now()


def update_model_job_progress(model_job_id: str, processed_images: int, total_images: int) -> None:
    with _MODEL_JOB_LOCK:
        if _MODEL_JOB_DATA is None or _MODEL_JOB_DATA["model_job_id"] != model_job_id:
            return

        processed = max(0, int(processed_images))
        total = max(0, int(total_images))
        if total > 0:
            processed = min(processed, total)

        created_at = datetime.fromisoformat(str(_MODEL_JOB_DATA["created_at"]))
        elapsed_seconds = max((datetime.now(timezone.utc) - created_at).total_seconds(), 0.0)
        estimated_remaining_seconds = None
        if processed > 0 and total > processed:
            seconds_per_image = elapsed_seconds / processed
            estimated_remaining_seconds = max(0, int(round(seconds_per_image * (total - processed))))

        _MODEL_JOB_DATA["processed_images"] = processed
        _MODEL_JOB_DATA["total_images"] = total
        _MODEL_JOB_DATA["estimated_remaining_seconds"] = estimated_remaining_seconds
        _MODEL_JOB_DATA["updated_at"] = _iso_now()


def request_model_job_cancel(model_job_id: str) -> bool:
    """Mark one running model job as cancellation-requested."""
    with _MODEL_JOB_LOCK:
        if _MODEL_JOB_DATA is None or _MODEL_JOB_DATA["model_job_id"] != model_job_id:
            return False
        if _MODEL_JOB_DATA["status"] != "running":
            return False
        _MODEL_JOB_DATA["cancel_requested"] = True
        _MODEL_JOB_DATA["status"] = "cancelled"
        _MODEL_JOB_DATA["stage"] = "Evaluation cancelled"
        _MODEL_JOB_DATA["estimated_remaining_seconds"] = 0
        _MODEL_JOB_DATA["updated_at"] = _iso_now()
        return True


def is_model_job_cancel_requested(model_job_id: str) -> bool:
    """Return whether cancellation has been requested for one job."""
    with _MODEL_JOB_LOCK:
        if _MODEL_JOB_DATA is None or _MODEL_JOB_DATA["model_job_id"] != model_job_id:
            return False
        return bool(_MODEL_JOB_DATA["cancel_requested"])


def complete_model_job(
    model_job_id: str,
    model_version: dict[str, Any],
    evaluation: dict[str, Any],
) -> None:
    with _MODEL_JOB_LOCK:
        if _MODEL_JOB_DATA is None or _MODEL_JOB_DATA["model_job_id"] != model_job_id:
            return
        if _MODEL_JOB_DATA["status"] != "running":
            return
        _MODEL_JOB_DATA["status"] = "completed"
        _MODEL_JOB_DATA["stage"] = "Evaluation complete"
        _MODEL_JOB_DATA["processed_images"] = int(_MODEL_JOB_DATA["total_images"])
        _MODEL_JOB_DATA["estimated_remaining_seconds"] = 0
        _MODEL_JOB_DATA["model_version"] = deepcopy(model_version)
        _MODEL_JOB_DATA["evaluation"] = deepcopy(evaluation)
        _MODEL_JOB_DATA["updated_at"] = _iso_now()


def fail_model_job(model_job_id: str, error_message: str) -> None:
    with _MODEL_JOB_LOCK:
        if _MODEL_JOB_DATA is None or _MODEL_JOB_DATA["model_job_id"] != model_job_id:
            return
        if _MODEL_JOB_DATA["status"] == "cancelled":
            _MODEL_JOB_DATA["error_message"] = str(error_message)
            _MODEL_JOB_DATA["updated_at"] = _iso_now()
            return
        _MODEL_JOB_DATA["status"] = "failed"
        _MODEL_JOB_DATA["error_message"] = str(error_message)
        _MODEL_JOB_DATA["updated_at"] = _iso_now()
