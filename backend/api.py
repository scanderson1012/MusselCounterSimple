"""FastAPI routes for runs, inference, detections, models, and image file serving.

This module is the backend API surface used by the Electron frontend. It coordinates:
- Run lifecycle (/predict, /runs, /runs/{run_id})
- Background model execution and progress polling (`/predict/run-jobs/{run_job_id}`)
- Detection edits and run count recalculation
- Model discovery from disk (`/models`)
- Image ingest and image byte serving (`/images/upload`, `/images/{image_id}`)
"""

from pathlib import Path
from threading import Thread
from typing import Any
from typing import Literal

from fastapi import APIRouter
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from backend.database import create_run
from backend.database import get_database_connection
from backend.database import get_image_file_metadata_from_database
from backend.database import get_model_name_from_run_id
from backend.database import get_run_info_from_detection_id
from backend.database import get_run_from_database
from backend.database import link_image_to_run
from backend.database import list_run_image_ids
from backend.database import list_runs_from_database
from backend.database import recalculate_run_image_mussel_counts_from_detections
from backend.database import recalculate_run_mussel_counts_from_detections
from backend.database import run_exists
from backend.database import unlink_image_from_run
from backend.database import update_detection_fields
from backend.database import update_this_runs_model
from backend.database import update_run_mussel_count
from backend.database import update_run_threshold
from backend.image_ingest import ingest_image_into_database
from backend.inference import run_rcnn_inference_for_run_images
from backend.run_jobs import complete_run_job
from backend.run_jobs import create_run_job
from backend.run_jobs import fail_run_job
from backend.run_jobs import get_current_run_job
from backend.run_jobs import get_run_job
from backend.run_jobs import update_run_job_progress
from backend.model_store import list_models_from_disk

router = APIRouter()


class PredictRequest(BaseModel):
    """Request body for creating/updating a run and starting inference."""

    run_id: int | None = None
    image_ids: list[int] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    model_file_name: str
    threshold_score: float = 0.5


class RecalculateRequest(BaseModel):
    """Request body for recomputing counts on one existing run."""

    run_id: int
    threshold_score: float


class DetectionPatchRequest(BaseModel):
    """Allowed editable fields for one detection."""

    model_config = ConfigDict(extra="forbid")
    class_name: Literal["live", "dead"] | None = None
    is_deleted: bool | None = None


def _run_job_in_background(
    run_job_id: str,
    run_id: int,
    run_image_ids_to_process: list[int],
    requested_model: str,
    threshold_score: float,
) -> None:
    """Run inference for one run job and finalize its status.

    This function runs on a background thread so `/predict` can return immediately.
    It executes inference on the selected run images, updates run-job progress
    counters, refreshes run-level mussel totals, and marks the run job as either
    `completed` or `failed`.
    """
    try:
        with get_database_connection() as database_connection:
            run_rcnn_inference_for_run_images(
                database_connection=database_connection,
                run_image_ids=run_image_ids_to_process,
                model_file_name=requested_model,
                threshold_score=threshold_score,
                on_run_image_processed=lambda processed_images, total_images: update_run_job_progress(
                    run_job_id,
                    processed_images,
                    total_images,
                ),
            )
            update_run_mussel_count(database_connection, run_id)
            database_connection.commit()
            run_data = get_run_from_database(database_connection, run_id)

        if run_data is None:
            raise RuntimeError("Failed to load run after inference completion")

        complete_run_job(run_job_id, run_data)
    except Exception as error:
        fail_run_job(run_job_id, str(error))


@router.post("/predict")
def create_or_update_run_and_do_inference(
    request: PredictRequest,
) -> dict[str, Any]:
    """Create/update a run, queue inference, and return run-job metadata.

    Behavior:
    - Creates a run when `run_id` is missing.
    - Updates an existing run when `run_id` is provided.
    - Ingests images from `image_paths` and links images from `image_ids`.
    - If model file changes on an existing run, inference re-runs on all run images.
    - If model file is unchanged, inference runs only on newly linked images.
    - Starts a background thread and returns a trackable run-job object.
    """
    # Enforce one active inference at a time for simpler frontend/backend coordination.
    current_run_job_data = get_current_run_job()
    if current_run_job_data is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "A model is already running. "
                f"run_job_id={current_run_job_data['run_job_id']}"
            ),
        )

    if request.run_id is None and not request.image_paths and not request.image_ids:
        raise HTTPException(
            status_code=400,
            detail="image_paths or image_ids cannot be empty for new runs",
        )

    skipped_images: list[str] = []
    skipped_image_ids: list[int] = []
    invalid_image_ids: list[int] = []
    new_images_for_this_run: list[int] = []
    is_running_on_new_images_only = True
    run_data: dict[str, Any] | None = None
    requested_model = request.model_file_name

    with get_database_connection() as database_connection:
        # Step 1: create a run or load/update existing run metadata.
        if request.run_id is None:
            run_id = create_run(database_connection, requested_model, request.threshold_score)
            using_new_model = False
        else:
            run_id = request.run_id
            current_model = get_model_name_from_run_id(database_connection, run_id)
            using_new_model = current_model != requested_model
            if using_new_model:
                update_this_runs_model(database_connection, run_id, requested_model)
                is_running_on_new_images_only = False

        update_run_threshold(database_connection, run_id, request.threshold_score)

        # Step 2: ingest image paths and link uploaded image IDs to this run.
        for image_path in request.image_paths:
            try:
                image = ingest_image_into_database(database_connection, image_path)
            except FileNotFoundError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

            run_image_id, inserted_without_error = link_image_to_run(
                database_connection, run_id, image["image_id"]
            )
            if not inserted_without_error:
                skipped_images.append(image_path)
                continue

            new_images_for_this_run.append(run_image_id)

        for image_id in request.image_ids:
            image_file_metadata = get_image_file_metadata_from_database(database_connection, image_id)
            if image_file_metadata is None:
                invalid_image_ids.append(image_id)
                continue

            run_image_id, inserted_without_error = link_image_to_run(
                database_connection,
                run_id,
                int(image_file_metadata["id"]),
            )
            if not inserted_without_error:
                skipped_image_ids.append(image_id)
                continue

            new_images_for_this_run.append(run_image_id)

        # Step 3: decide inference scope based on model change vs newly added images.
        if using_new_model:
            run_image_ids_to_process = list_run_image_ids(database_connection, run_id)
        else:
            run_image_ids_to_process = new_images_for_this_run

        update_run_mussel_count(database_connection, run_id)
        database_connection.commit()
        if not run_image_ids_to_process:
            run_data = get_run_from_database(database_connection, run_id)

    # Step 4: create run-job tracking data returned to frontend for progress polling.
    try:
        run_job_data = create_run_job(
            run_id=run_id,
            total_images=len(run_image_ids_to_process),
            skipped_images=skipped_images,
            skipped_image_ids=skipped_image_ids,
            invalid_image_ids=invalid_image_ids,
            model_changed=using_new_model,
            is_running_on_new_images_only=is_running_on_new_images_only,
            processed_run_image_ids=run_image_ids_to_process,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    if not run_image_ids_to_process:
        if run_data is None:
            raise HTTPException(status_code=500, detail="Failed to load run")
        complete_run_job(run_job_data["run_job_id"], run_data)
        completed_run_job_data = get_run_job(
            run_job_data["run_job_id"]
        )
        if completed_run_job_data is None:
            raise HTTPException(status_code=500, detail="Failed to load run job")
        return completed_run_job_data

    run_job_thread = Thread(
        target=_run_job_in_background,
        args=(
            run_job_data["run_job_id"],
            run_id,
            run_image_ids_to_process,
            requested_model,
            request.threshold_score,
        ),
        daemon=True,
    )
    run_job_thread.start()
    return run_job_data


@router.get("/predict/run-jobs/{run_job_id}")
def get_predict_task(run_job_id: str) -> dict[str, Any]:
    """Return one run job state for frontend progress polling.

    The response includes status (`running`, `completed`, or `failed`), counters
    (`processed_images`, `total_images`), and final run data when completed.
    """
    run_job_data = get_run_job(run_job_id)
    if run_job_data is None:
        raise HTTPException(status_code=404, detail="Run job not found")
    return run_job_data


@router.post("/recalculate")
def recalculate_mussel_counts(request: RecalculateRequest) -> dict[str, Any]:
    """Recompute run totals from already-stored detections.

    This endpoint does not run the model. It re-applies the provided threshold to
    existing detections and refreshes run-level totals in the database.
    """
    with get_database_connection() as database_connection:
        if not run_exists(database_connection, request.run_id):
            raise HTTPException(status_code=404, detail="Run not found")

        update_run_threshold(database_connection, request.run_id, request.threshold_score)
        recalculate_run_mussel_counts_from_detections(
            database_connection, request.run_id, request.threshold_score
        )
        database_connection.commit()
        run_data = get_run_from_database(database_connection, request.run_id)

    if run_data is None:
        raise HTTPException(status_code=500, detail="Failed to load run")

    return {"run": run_data}


@router.patch("/detections/{detection_id}")
def edit_detection_in_database(detection_id: int, request: DetectionPatchRequest) -> dict[str, Any]:
    """Edit one detection (`class_name` and/or `is_deleted`) and refresh counts.

    Allowed edits are intentionally narrow:
    - Re-label detection class (`live` or `dead`)
    - Soft-delete/restore detection (`is_deleted`)
    """
    fields_to_update = request.model_dump(exclude_unset=True)
    if not fields_to_update:
        raise HTTPException(status_code=400, detail="No detection fields provided")

    with get_database_connection() as database_connection:
        run_information = get_run_info_from_detection_id(database_connection, detection_id)
        if run_information is None:
            raise HTTPException(status_code=404, detail="Detection not found")

        if "is_deleted" in fields_to_update:
            fields_to_update["is_deleted"] = 1 if fields_to_update["is_deleted"] else 0
        fields_to_update["is_edited"] = 1

        update_detection_fields(database_connection, detection_id, fields_to_update)
        recalculate_run_image_mussel_counts_from_detections(
            database_connection,
            run_image_id=int(run_information["run_image_id"]),
            threshold_score=float(run_information["threshold_score"]),
        )
        update_run_mussel_count(database_connection, int(run_information["run_id"]))
        database_connection.commit()
        run_data = get_run_from_database(database_connection, int(run_information["run_id"]))

    if run_data is None:
        raise HTTPException(status_code=500, detail="Failed to load run")

    return {"run": run_data}


@router.delete("/runs/{run_id}/images/{run_image_id}")
def remove_image_from_run(run_id: int, run_image_id: int) -> dict[str, Any]:
    """Remove one image link from a run and recompute run totals."""
    with get_database_connection() as database_connection:
        if not run_exists(database_connection, run_id):
            raise HTTPException(status_code=404, detail="Run not found")

        deleted = unlink_image_from_run(database_connection, run_id, run_image_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Image not found in run")

        update_run_mussel_count(database_connection, run_id)
        database_connection.commit()
        run_data = get_run_from_database(database_connection, run_id)

    if run_data is None:
        raise HTTPException(status_code=500, detail="Failed to load run")

    return {"run": run_data}


@router.get("/runs")
def list_runs() -> list[dict[str, Any]]:
    """Return all runs for the history view, newest first."""
    with get_database_connection() as database_connection:
        return list_runs_from_database(database_connection)


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> dict[str, Any]:
    """Return one run with nested run images and detections."""
    with get_database_connection() as database_connection:
        run_data = get_run_from_database(database_connection, run_id)
    if run_data is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_data


@router.get("/models")
def list_models() -> dict[str, Any]:
    """Return model files discovered in the on-disk models directory."""
    return list_models_from_disk()


@router.post("/images/upload")
def upload_images(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Upload images into storage/database without linking them to any run yet.

    This endpoint is used by the frontend image picker flow so images can be
    uploaded once and later attached to one or more runs.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded_images: list[dict[str, Any]] = []
    with get_database_connection() as database_connection:
        for uploaded_file in files:
            displayed_file_name = uploaded_file.filename or "uploaded_image"
            file_bytes = uploaded_file.file.read()
            uploaded_file.file.close()
            if not file_bytes:
                raise HTTPException(status_code=400, detail=f"Empty file: {displayed_file_name}")

            uploaded_image = ingest_image_into_database(
                database_connection,
                displayed_file_name=displayed_file_name,
                file_bytes=file_bytes,
            )
            uploaded_images.append(uploaded_image)

        database_connection.commit()

    return {"images": uploaded_images}


@router.get("/images/{image_id}", response_class=FileResponse)
def get_image(image_id: int) -> FileResponse:
    """Serve image bytes for one stored image ID."""
    with get_database_connection() as database_connection:
        image_file_metadata = get_image_file_metadata_from_database(database_connection, image_id)

    if image_file_metadata is None:
        raise HTTPException(status_code=404, detail="Image not found")

    image_path = Path(image_file_metadata["stored_path"]).resolve()
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    return FileResponse(
        path=str(image_path),
        filename=image_file_metadata["displayed_file_name"],
    )
