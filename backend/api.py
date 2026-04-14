"""FastAPI routes for runs, model_execution, detections, models, and image file serving.

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
import sqlite3

from fastapi import APIRouter
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from backend.app_settings import get_app_settings
from backend.app_settings import update_app_settings
from backend.database import build_model_file_path_for_version
from backend.database import get_database_connection
from backend.database import create_dataset_record
from backend.database import create_detection_for_run_image
from backend.database import delete_model_family
from backend.database import delete_model_version
from backend.database import finalize_run_into_replay_buffer
from backend.database import get_next_version_number_for_family
from backend.database import get_or_create_dataset_record
from backend.database import get_image_file_metadata_from_database
from backend.database import get_model_version_by_id
from backend.database import get_replay_buffer_detections_for_images
from backend.database import get_run_info_from_detection_id
from backend.database import get_run_from_database
from backend.database import is_run_image_locked_for_editing
from backend.database import list_consumed_replay_buffer_images_through_version
from backend.database import list_model_options
from backend.database import list_model_registry
from backend.database import list_pending_replay_buffer_images_for_model
from backend.database import list_runs_from_database
from backend.database import list_test_datasets
from backend.database import list_training_datasets
from backend.database import mark_replay_buffer_images_consumed
from backend.database import recalculate_run_image_mussel_counts_from_detections
from backend.database import recalculate_run_mussel_counts_from_detections
from backend.database import remove_replay_buffer_entry_for_run_image
from backend.database import register_baseline_model
from backend.database import register_finetuned_model_version
from backend.database import run_exists
from backend.database import unlink_image_from_run
from backend.database import update_detection_fields
from backend.database import update_run_mussel_count
from backend.database import update_run_threshold
from backend.image_ingest import ingest_image_into_database
from backend.run_jobs import get_run_job
from backend.predict_service import PredictServiceError
from backend.predict_service import PredictServiceInput
from backend.predict_service import execute_predict_request
from backend.model_evaluation import evaluate_model_file
from backend.model_evaluation import store_model_evaluation
from backend.model_finetuning import FineTuneConfig
from backend.model_finetuning import run_fine_tuning
from backend.model_jobs import complete_model_job
from backend.model_jobs import cancel_model_job
from backend.model_jobs import create_model_job
from backend.model_jobs import fail_model_job
from backend.model_jobs import get_model_job
from backend.model_jobs import is_model_job_cancel_requested
from backend.model_jobs import request_model_job_cancel
from backend.model_jobs import update_model_job_progress
from backend.model_jobs import update_model_job_stage
from backend.model_documents import build_model_report_data
from backend.model_documents import create_model_export_zip
from backend.model_documents import render_model_report_html

router = APIRouter()


class PredictRequest(BaseModel):
    """Request body for creating/updating a run and starting model_execution."""

    run_id: int | None = None
    image_ids: list[int] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    model_version_id: int | None = None
    model_file_name: str = ""
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


class DetectionCreateRequest(BaseModel):
    """Create one new detection box on a run image."""

    class_name: Literal["live", "dead"]
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float
    confidence_score: float | None = None


class DatasetCreateRequest(BaseModel):
    """Request body for registering one training/test dataset directory pair."""

    name: str
    images_dir: str
    labels_dir: str
    description: str | None = None


class ModelRegisterRequest(BaseModel):
    """Register a baseline model and immediately evaluate it on a test set."""

    source_model_path: str
    family_name: str | None = None
    description: str
    training_images_dir: str
    training_labels_dir: str
    test_images_dir: str
    test_labels_dir: str
    architecture: str = "fasterrcnn_resnet50_fpn_v2"
    num_classes: int = 3
    notes: str | None = None


class ModelEvaluateRequest(BaseModel):
    """Run one stored model version against a selected test dataset."""

    test_dataset_id: int
    score_threshold: float = 0.5


class AppSettingsUpdateRequest(BaseModel):
    """Supported application settings for the desktop app."""

    fine_tune_min_new_images: int
    fine_tune_num_epochs: int


def _evaluate_model_version_on_assigned_test_set(model_job_id: str, model_version_id: int) -> None:
    """Background worker for evaluating one stored model version on its assigned test set."""
    try:
        with get_database_connection() as database_connection:
            version = get_model_version_by_id(database_connection, model_version_id)
            if version is None:
                raise ValueError("Model version not found")
            if version.get("test_dataset_id") is None:
                raise ValueError("This model version does not have an assigned test dataset")

            existing_evaluation = version.get("latest_evaluation")
            if existing_evaluation and int(existing_evaluation.get("test_dataset_id") or 0) == int(version["test_dataset_id"]):
                raise ValueError("This model version has already been evaluated on its assigned test set")

            test_dataset = next(
                (
                    dataset
                    for dataset in list_test_datasets(database_connection)
                    if int(dataset["id"]) == int(version["test_dataset_id"])
                ),
                None,
            )
            if test_dataset is None:
                raise ValueError(f"Test dataset not found: {version['test_dataset_id']}")

            evaluation_result = evaluate_model_file(
                model_file_name=str(version["model_file_name"]),
                images_dir=str(test_dataset["images_dir"]),
                labels_dir=str(test_dataset["labels_dir"]),
                class_mapping=dict(version["class_mapping"]),
                progress_callback=lambda processed, total: update_model_job_progress(
                    model_job_id, processed, total
                ),
                stage_callback=lambda stage: update_model_job_stage(model_job_id, stage),
                should_cancel_callback=lambda: is_model_job_cancel_requested(model_job_id),
            )
            evaluation = store_model_evaluation(
                database_connection=database_connection,
                model_version_id=int(version["id"]),
                test_dataset_id=int(version["test_dataset_id"]),
                evaluation_result=evaluation_result,
            )
            database_connection.commit()

            refreshed_version = get_model_version_by_id(database_connection, int(version["id"]))
            if refreshed_version is None:
                raise RuntimeError("Failed to reload the saved model version after evaluation")

        complete_model_job(
            model_job_id=model_job_id,
            model_version=refreshed_version,
            evaluation=evaluation,
        )
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.IntegrityError) as error:
        if "cancelled by user" in str(error).lower():
            cancel_model_job(model_job_id, "Evaluation cancelled")
            return
        fail_model_job(model_job_id, str(error))


def _fine_tune_latest_model_version(model_job_id: str, model_version_id: int) -> None:
    """Background worker for fine-tuning the latest version in one family."""
    try:
        with get_database_connection() as database_connection:
            settings = get_app_settings(database_connection)
            version = get_model_version_by_id(database_connection, model_version_id)
            if version is None:
                raise ValueError("Model version not found")
            if not bool(version.get("is_latest_version")):
                raise ValueError("Only the newest version in a model family can be fine-tuned.")
            if version.get("training_images_dir") in (None, "") or version.get("training_labels_dir") in (None, ""):
                raise ValueError("This model version does not have a valid training dataset.")

            pending_limit = int(settings["fine_tune_min_new_images"])
            pending_replay_images = list_pending_replay_buffer_images_for_model(
                database_connection=database_connection,
                model_version_id=int(version["id"]),
                limit=pending_limit,
            )
            if len(pending_replay_images) < pending_limit:
                raise ValueError(
                    f"Fine-tuning requires {pending_limit} new replay-buffer images for this model."
                )

            replay_history_images = list_consumed_replay_buffer_images_through_version(
                database_connection=database_connection,
                family_id=int(version["family_id"]),
                max_version_number=int(version["version_number"]),
            )
            replay_history_detections = get_replay_buffer_detections_for_images(
                database_connection=database_connection,
                replay_buffer_image_ids=[int(row["id"]) for row in replay_history_images],
            )
            new_replay_detections = get_replay_buffer_detections_for_images(
                database_connection=database_connection,
                replay_buffer_image_ids=[int(row["id"]) for row in pending_replay_images],
            )
            next_version_number = get_next_version_number_for_family(
                database_connection,
                int(version["family_id"]),
            )
            output_model_path = build_model_file_path_for_version(
                family_name=str(version["family_name"]),
                version_number=int(next_version_number),
                original_file_name=str(version["original_file_name"]),
            )

        fine_tune_result = run_fine_tuning(
            FineTuneConfig(
                parent_model_path=str(version["model_file_name"]),
                output_model_path=str(output_model_path),
                architecture=str(version["architecture"]),
                num_classes=int(version["num_classes"]),
                class_mapping=dict(version["class_mapping"]),
                base_train_images_dir=str(version["training_images_dir"]),
                base_train_labels_dir=str(version["training_labels_dir"]),
                replay_history_images=replay_history_images,
                replay_history_detections=replay_history_detections,
                new_replay_images=pending_replay_images,
                new_replay_detections=new_replay_detections,
                num_epochs=int(settings["fine_tune_num_epochs"]),
            ),
            progress_callback=lambda processed, total: update_model_job_progress(
                model_job_id, processed, total
            ),
            stage_callback=lambda stage: update_model_job_stage(model_job_id, stage),
            should_cancel_callback=lambda: is_model_job_cancel_requested(model_job_id),
        )
        if is_model_job_cancel_requested(model_job_id):
            raise RuntimeError("Fine-tuning cancelled by user.")

        with get_database_connection() as database_connection:
            new_version = register_finetuned_model_version(
                database_connection=database_connection,
                parent_version_id=int(version["id"]),
                model_file_path=str(output_model_path),
            )
            mark_replay_buffer_images_consumed(
                database_connection=database_connection,
                replay_buffer_image_ids=[int(row["id"]) for row in pending_replay_images],
                model_version_id=int(new_version["id"]),
            )
            database_connection.commit()
            refreshed_version = get_model_version_by_id(database_connection, int(new_version["id"]))
            if refreshed_version is None:
                raise RuntimeError("Failed to reload the fine-tuned model version.")

        complete_model_job(
            model_job_id=model_job_id,
            model_version=refreshed_version,
            fine_tune_result=fine_tune_result,
        )
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.IntegrityError) as error:
        if "cancelled by user" in str(error).lower():
            output_model_path = fine_tune_result["output_model_path"] if "fine_tune_result" in locals() and fine_tune_result else None
            if output_model_path:
                Path(output_model_path).expanduser().resolve().unlink(missing_ok=True)
            cancel_model_job(model_job_id, "Fine-tuning cancelled")
            return
        fail_model_job(model_job_id, str(error))


@router.post("/predict")
def create_or_update_run_and_do_model_execution(
    request: PredictRequest,
) -> dict[str, Any]:
    """Thin route: delegate `/predict` workflow to service layer."""
    try:
        return execute_predict_request(
            PredictServiceInput(
                run_id=request.run_id,
                image_ids=list(request.image_ids),
                image_paths=list(request.image_paths),
                model_version_id=request.model_version_id,
                model_file_name=request.model_file_name,
                threshold_score=request.threshold_score,
            )
        )
    except PredictServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


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
        if is_run_image_locked_for_editing(database_connection, int(run_information["run_image_id"])):
            raise HTTPException(
                status_code=400,
                detail="This image has already been used for fine-tuning and can no longer be edited.",
            )

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
        if is_run_image_locked_for_editing(database_connection, int(run_image_id)):
            raise HTTPException(
                status_code=400,
                detail="This image has already been used for fine-tuning and can no longer be removed.",
            )

        remove_replay_buffer_entry_for_run_image(database_connection, run_image_id)
        deleted = unlink_image_from_run(database_connection, run_id, run_image_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Image not found in run")

        update_run_mussel_count(database_connection, run_id)
        database_connection.commit()
        run_data = get_run_from_database(database_connection, run_id)

    if run_data is None:
        raise HTTPException(status_code=500, detail="Failed to load run")

    return {"run": run_data}


@router.post("/run-images/{run_image_id}/detections")
def create_detection_for_image(run_image_id: int, request: DetectionCreateRequest) -> dict[str, Any]:
    """Create one new detection on a run image and refresh counts."""
    with get_database_connection() as database_connection:
        run_information = database_connection.execute(
            """
            SELECT
                run_images.id AS run_image_id,
                run_images.run_id,
                runs.threshold_score
            FROM run_images
            JOIN runs ON runs.id = run_images.run_id
            WHERE run_images.id = ?
            """,
            (run_image_id,),
        ).fetchone()
        if run_information is None:
            raise HTTPException(status_code=404, detail="Run image not found")
        if is_run_image_locked_for_editing(database_connection, int(run_image_id)):
            raise HTTPException(
                status_code=400,
                detail="This image has already been used for fine-tuning and can no longer be edited.",
            )

        try:
            create_detection_for_run_image(
                database_connection=database_connection,
                run_image_id=run_image_id,
                class_name=request.class_name,
                bbox_x1=request.bbox_x1,
                bbox_y1=request.bbox_y1,
                bbox_x2=request.bbox_x2,
                bbox_y2=request.bbox_y2,
                confidence_score=request.confidence_score,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        recalculate_run_image_mussel_counts_from_detections(
            database_connection,
            run_image_id=run_image_id,
            threshold_score=float(run_information["threshold_score"]),
        )
        update_run_mussel_count(database_connection, int(run_information["run_id"]))
        database_connection.commit()
        run_data = get_run_from_database(database_connection, int(run_information["run_id"]))

    if run_data is None:
        raise HTTPException(status_code=500, detail="Failed to load run")
    return {"run": run_data}


@router.post("/runs/{run_id}/finalize-review")
def finalize_reviewed_run(run_id: int) -> dict[str, Any]:
    """Finalize the current reviewed run into the replay buffer for future fine-tuning."""
    with get_database_connection() as database_connection:
        if not run_exists(database_connection, run_id):
            raise HTTPException(status_code=404, detail="Run not found")
        run_data = get_run_from_database(database_connection, run_id)
        if run_data is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run_data.get("model_version_id") is None:
            raise HTTPException(
                status_code=400,
                detail="This run is not linked to a registered model version, so it cannot be finalized into the replay buffer.",
            )

        try:
            replay_buffer_summary = finalize_run_into_replay_buffer(database_connection, run_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        database_connection.commit()
        run_data = get_run_from_database(database_connection, run_id)

    if run_data is None:
        raise HTTPException(status_code=500, detail="Failed to load run")

    return {
        "run": run_data,
        "replay_buffer_summary": replay_buffer_summary,
    }


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
    """Return model versions available for the run selector."""
    with get_database_connection() as database_connection:
        return list_model_options(database_connection)


@router.get("/models/registry")
def list_models_registry() -> dict[str, Any]:
    """Return model families, versions, and their latest evaluation."""
    with get_database_connection() as database_connection:
        return {"families": list_model_registry(database_connection)}


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    """Return persisted application settings."""
    with get_database_connection() as database_connection:
        return {"settings": get_app_settings(database_connection)}


@router.patch("/settings")
def patch_settings(request: AppSettingsUpdateRequest) -> dict[str, Any]:
    """Update persisted application settings."""
    with get_database_connection() as database_connection:
        settings = update_app_settings(
            database_connection,
            request.model_dump(),
        )
        database_connection.commit()
        return {"settings": settings}


@router.get("/datasets/training")
def get_training_datasets() -> dict[str, Any]:
    """Return registered training datasets."""
    with get_database_connection() as database_connection:
        return {"datasets": list_training_datasets(database_connection)}


@router.post("/datasets/training")
def create_training_dataset(request: DatasetCreateRequest) -> dict[str, Any]:
    """Register one training dataset by folder path pointers."""
    try:
        with get_database_connection() as database_connection:
            dataset = create_dataset_record(
                database_connection,
                "training_datasets",
                name=request.name,
                images_dir=request.images_dir,
                labels_dir=request.labels_dir,
                description=request.description,
            )
            database_connection.commit()
        return {"dataset": dataset}
    except (FileNotFoundError, ValueError, sqlite3.IntegrityError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/datasets/test")
def get_test_datasets() -> dict[str, Any]:
    """Return registered test datasets."""
    with get_database_connection() as database_connection:
        return {"datasets": list_test_datasets(database_connection)}


@router.post("/datasets/test")
def create_test_dataset(request: DatasetCreateRequest) -> dict[str, Any]:
    """Register one test dataset by folder path pointers."""
    try:
        with get_database_connection() as database_connection:
            dataset = create_dataset_record(
                database_connection,
                "test_datasets",
                name=request.name,
                images_dir=request.images_dir,
                labels_dir=request.labels_dir,
                description=request.description,
            )
            database_connection.commit()
        return {"dataset": dataset}
    except (FileNotFoundError, ValueError, sqlite3.IntegrityError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/models/register")
def register_model(request: ModelRegisterRequest) -> dict[str, Any]:
    """Register a baseline model and its datasets without evaluating it yet."""
    try:
        source_path = Path(request.source_model_path).expanduser().resolve()
        if not str(request.description or "").strip():
            raise RuntimeError("Model description is required.")
        required_paths = {
            "training_images_dir": request.training_images_dir,
            "training_labels_dir": request.training_labels_dir,
            "test_images_dir": request.test_images_dir,
            "test_labels_dir": request.test_labels_dir,
        }
        for field_name, raw_value in required_paths.items():
            if not str(raw_value or "").strip():
                raise RuntimeError(f"{field_name} is required.")

        with get_database_connection() as database_connection:
            inferred_family_name = (request.family_name or source_path.stem).strip()
            training_dataset = get_or_create_dataset_record(
                database_connection=database_connection,
                table_name="training_datasets",
                name=f"{inferred_family_name}_train",
                images_dir=request.training_images_dir,
                labels_dir=request.training_labels_dir,
                description=f"Training dataset for {inferred_family_name}",
            )
            test_dataset = get_or_create_dataset_record(
                database_connection=database_connection,
                table_name="test_datasets",
                name=f"{inferred_family_name}_test",
                images_dir=request.test_images_dir,
                labels_dir=request.test_labels_dir,
                description=f"Test dataset for {inferred_family_name}",
            )
            version = register_baseline_model(
                database_connection=database_connection,
                source_model_path=request.source_model_path,
                family_name=request.family_name,
                training_dataset_id=int(training_dataset["id"]),
                test_dataset_id=int(test_dataset["id"]),
                architecture=request.architecture,
                num_classes=request.num_classes,
                description=request.description,
                notes=request.notes,
            )
            database_connection.commit()
            refreshed_version = get_model_version_by_id(database_connection, int(version["id"]))
        return {"model_version": refreshed_version}
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.IntegrityError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/models/jobs/{model_job_id}")
def get_model_job_status(model_job_id: str) -> dict[str, Any]:
    """Return one model-evaluation job snapshot."""
    model_job = get_model_job(model_job_id)
    if model_job is None:
        raise HTTPException(status_code=404, detail="Model job not found")
    return model_job


@router.post("/models/jobs/{model_job_id}/cancel")
def cancel_model_job_status(model_job_id: str) -> dict[str, Any]:
    """Request cancellation for one running model evaluation job."""
    cancelled = request_model_job_cancel(model_job_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Model job cannot be cancelled")
    model_job = get_model_job(model_job_id)
    if model_job is None:
        raise HTTPException(status_code=404, detail="Model job not found")
    return model_job


@router.post("/models/versions/{model_version_id}/evaluate")
def evaluate_registered_model(model_version_id: int, request: ModelEvaluateRequest) -> dict[str, Any]:
    """Re-run evaluation for one stored model version on a selected test dataset."""
    try:
        with get_database_connection() as database_connection:
            model_version = get_model_version_by_id(database_connection, model_version_id)
            if model_version is None:
                raise HTTPException(status_code=404, detail="Model version not found")

            test_dataset = next(
                (
                    dataset
                    for dataset in list_test_datasets(database_connection)
                    if int(dataset["id"]) == int(request.test_dataset_id)
                ),
                None,
            )
            if test_dataset is None:
                raise HTTPException(status_code=404, detail="Test dataset not found")

            evaluation_result = evaluate_model_file(
                model_file_name=str(model_version["model_file_name"]),
                images_dir=str(test_dataset["images_dir"]),
                labels_dir=str(test_dataset["labels_dir"]),
                class_mapping=dict(model_version["class_mapping"]),
                score_threshold=float(request.score_threshold),
            )
            evaluation = store_model_evaluation(
                database_connection=database_connection,
                model_version_id=model_version_id,
                test_dataset_id=int(request.test_dataset_id),
                evaluation_result=evaluation_result,
                score_threshold=float(request.score_threshold),
            )
            database_connection.commit()

            refreshed_version = get_model_version_by_id(database_connection, model_version_id)
        return {"model_version": refreshed_version, "evaluation": evaluation}
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.IntegrityError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/models/versions/{model_version_id}/evaluate-default")
def evaluate_registered_model_on_assigned_test_set(model_version_id: int) -> dict[str, Any]:
    """Evaluate one stored model version on its assigned test set exactly once."""
    try:
        with get_database_connection() as database_connection:
            model_version = get_model_version_by_id(database_connection, model_version_id)
            if model_version is None:
                raise HTTPException(status_code=404, detail="Model version not found")
            if model_version.get("test_dataset_id") is None:
                raise HTTPException(status_code=400, detail="Model version has no assigned test dataset")

            latest_evaluation = model_version.get("latest_evaluation")
            if latest_evaluation and int(latest_evaluation.get("test_dataset_id") or 0) == int(model_version["test_dataset_id"]):
                return {
                    "already_evaluated": True,
                    "message": "Evaluation already occurred for this model version on its assigned test set.",
                    "model_version": model_version,
                }

            display_name = f"{model_version.get('family_name', 'model')} {model_version.get('version_tag', '')}".strip()
            model_job = create_model_job(display_name=display_name)

        worker = Thread(
            target=_evaluate_model_version_on_assigned_test_set,
            args=(str(model_job["model_job_id"]), int(model_version_id)),
            daemon=True,
        )
        worker.start()
        return model_job
    except HTTPException:
        raise
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/models/versions/{model_version_id}/fine-tune")
def fine_tune_registered_model_version(model_version_id: int) -> dict[str, Any]:
    """Fine-tune the latest model version using pending replay-buffer images."""
    try:
        with get_database_connection() as database_connection:
            settings = get_app_settings(database_connection)
            model_version = get_model_version_by_id(database_connection, model_version_id)
            if model_version is None:
                raise HTTPException(status_code=404, detail="Model version not found")
            if not bool(model_version.get("is_latest_version")):
                raise HTTPException(status_code=400, detail="Only the newest version in a model family can be fine-tuned.")

            pending_image_count = len(
                list_pending_replay_buffer_images_for_model(
                    database_connection=database_connection,
                    model_version_id=model_version_id,
                )
            )
            required_image_count = int(settings["fine_tune_min_new_images"])
            if pending_image_count < required_image_count:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Fine-tuning is not available yet. "
                        f"{required_image_count} new replay-buffer images are required, and only {pending_image_count} are ready."
                    ),
                )

            display_name = f"{model_version.get('family_name', 'model')} {model_version.get('version_tag', '')}".strip()
            model_job = create_model_job(display_name=display_name, job_type="fine_tuning")

        worker = Thread(
            target=_fine_tune_latest_model_version,
            args=(str(model_job["model_job_id"]), int(model_version_id)),
            daemon=True,
        )
        worker.start()
        return model_job
    except HTTPException:
        raise
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/models/versions/{model_version_id}/report")
def get_model_version_report(model_version_id: int) -> dict[str, Any]:
    """Return structured and rendered report content for one model version."""
    with get_database_connection() as database_connection:
        version = get_model_version_by_id(database_connection, model_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Model version not found")

    report = build_model_report_data(version)
    return {
        "report": report,
        "document_html": render_model_report_html(report),
    }


@router.get("/models/versions/{model_version_id}/export", response_class=FileResponse)
def export_model_version(model_version_id: int) -> FileResponse:
    """Build and return a zip export for one model version."""
    with get_database_connection() as database_connection:
        version = get_model_version_by_id(database_connection, model_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Model version not found")

    report = build_model_report_data(version)
    zip_path = create_model_export_zip(
        report=report,
        model_file_path=str(version["model_file_name"]),
    )
    return FileResponse(
        path=str(zip_path),
        filename=zip_path.name,
        media_type="application/zip",
    )


@router.delete("/models/versions/{model_version_id}")
def remove_model_version(model_version_id: int) -> dict[str, Any]:
    """Delete one stored model version from the registry and disk."""
    try:
        with get_database_connection() as database_connection:
            deleted = delete_model_version(database_connection, model_version_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Model version not found")
            database_connection.commit()
            return {"families": list_model_registry(database_connection)}
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/models/families/{family_id}")
def remove_model_family(family_id: int) -> dict[str, Any]:
    """Delete every version in one stored model family."""
    try:
        with get_database_connection() as database_connection:
            deleted = delete_model_family(database_connection, family_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Model family not found")
            database_connection.commit()
            return {"families": list_model_registry(database_connection)}
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


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
