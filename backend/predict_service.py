"""Predict workflow service.

This module contains the full `/predict` workflow so the FastAPI route can stay thin.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Thread
from typing import Any
import sqlite3

from backend.database import create_run
from backend.database import get_database_connection
from backend.database import get_image_file_metadata_from_database
from backend.database import get_model_file_name_for_run
from backend.database import get_model_name_from_run_id
from backend.database import get_model_version_id_from_run_id
from backend.database import get_run_from_database
from backend.database import link_image_to_run
from backend.database import list_run_image_ids
from backend.database import run_exists
from backend.database import update_this_runs_model
from backend.database import update_run_mussel_count
from backend.database import update_run_threshold
from backend.image_ingest import ingest_image_into_database
from backend.model_execution import run_rcnn_model_execution_for_run_images
from backend.run_jobs import complete_run_job
from backend.run_jobs import create_run_job
from backend.run_jobs import fail_run_job
from backend.run_jobs import get_current_run_job
from backend.run_jobs import get_run_job
from backend.run_jobs import is_a_run_job_already_running
from backend.run_jobs import update_run_job_progress


class PredictServiceError(Exception):
    """Service-layer error with HTTP-mappable status and detail."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)


@dataclass(frozen=True)
class PredictServiceInput:
    """Inputs required to execute the `/predict` workflow."""

    run_id: int | None
    image_ids: list[int]
    image_paths: list[str]
    model_version_id: int | None
    model_file_name: str
    threshold_score: float


def _start_model_execution_in_background(
    run_job_id: str,
    run_id: int,
    run_image_ids_to_process: list[int],
    requested_model: str,
    threshold_score: float,
) -> None:
    """Run model_execution for one run job and finalize its status."""
    try:
        with get_database_connection() as database_connection:
            run_rcnn_model_execution_for_run_images(
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
            raise RuntimeError("Failed to load run after model_execution completion")

        complete_run_job(run_job_id, run_data)
    except Exception as error:
        fail_run_job(run_job_id, str(error))


def _stop_if_another_model_is_currently_executing() -> None:
    """Block `/predict` when another model run job is active."""
    if is_a_run_job_already_running():
        current_run_job_data = get_current_run_job()
        raise PredictServiceError(
            409,
            "A model is already running. "
            f"run_job_id={current_run_job_data['run_job_id'] if current_run_job_data else 'unknown'}",
        )


def _validate_new_run_has_images(request: PredictServiceInput) -> None:
    """Validate that new runs include at least one image path or image ID."""
    if not request.image_paths and not request.image_ids:
        raise PredictServiceError(400, "image_paths or image_ids cannot be empty for new runs")


def _resolve_run_id_for_predict_request(
    database_connection: sqlite3.Connection,
    request: PredictServiceInput,
    creating_new_run: bool,
    requested_model: str,
    requested_model_version_id: int | None,
) -> int:
    """Resolve run target for this `/predict` call."""
    if creating_new_run:
        return create_run(
            database_connection,
            requested_model,
            request.threshold_score,
            model_version_id=requested_model_version_id,
        )

    run_id = request.run_id
    if run_id is None or not run_exists(database_connection, run_id):
        raise PredictServiceError(404, "Run not found")
    return run_id


def _is_new_model(current_model: str | None, requested_model: str) -> bool:
    """Return whether the requested model differs from the current run model."""
    return current_model != requested_model


def _link_request_images_to_run(
    database_connection: sqlite3.Connection,
    run_id: int,
    image_paths: list[str],
    image_ids: list[int],
) -> tuple[list[str], list[int], list[int], list[int]]:
    """Link requested images to a run and return link results."""
    skipped_images: list[str] = []
    skipped_image_ids: list[int] = []
    invalid_image_ids: list[int] = []
    new_images_for_this_run: list[int] = []

    for image_path in image_paths:
        try:
            image = ingest_image_into_database(database_connection, image_path)
        except FileNotFoundError as error:
            raise PredictServiceError(400, str(error)) from error

        run_image_id, inserted_without_error = link_image_to_run(
            database_connection, run_id, image["image_id"]
        )
        if not inserted_without_error:
            skipped_images.append(image_path)
            continue
        new_images_for_this_run.append(run_image_id)

    for image_id in image_ids:
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

    return (
        new_images_for_this_run,
        skipped_images,
        skipped_image_ids,
        invalid_image_ids,
    )


def _select_images_to_process(
    database_connection: sqlite3.Connection,
    run_id: int,
    creating_new_run: bool,
    current_model: str | None,
    requested_model: str,
    requested_model_version_id: int | None,
    new_images_for_this_run: list[int],
) -> tuple[list[int], bool]:
    """Choose model_execution scope for this request."""
    if creating_new_run:
        return new_images_for_this_run, False

    using_new_model = _is_new_model(current_model, requested_model)
    if using_new_model:
        update_this_runs_model(
            database_connection,
            run_id,
            requested_model,
            model_version_id=requested_model_version_id,
        )
        images_to_process = list_run_image_ids(database_connection, run_id)
    else:
        images_to_process = new_images_for_this_run
    return images_to_process, using_new_model


def _commit_run_updates_and_load_if_no_work(
    database_connection: sqlite3.Connection,
    run_id: int,
    images_to_process: list[int],
) -> dict[str, Any] | None:
    """Persist run totals and return run data when no model_execution work remains."""
    update_run_mussel_count(database_connection, run_id)
    database_connection.commit()
    if not images_to_process:
        return get_run_from_database(database_connection, run_id)
    return None


def _start_model_execution(
    run_job_id: str,
    run_id: int,
    images_to_process: list[int],
    requested_model: str,
    threshold_score: float,
) -> None:
    """Start background model_execution for one run job."""
    run_job_thread = Thread(
        target=_start_model_execution_in_background,
        args=(
            run_job_id,
            run_id,
            images_to_process,
            requested_model,
            threshold_score,
        ),
        daemon=True,
    )
    run_job_thread.start()


def _complete_and_return_run_job_if_no_images_to_process(
    run_job_id: str,
    run_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Finalize and return run-job response when no model_execution work is needed."""
    if run_data is None:
        raise PredictServiceError(500, "Failed to load run")
    complete_run_job(run_job_id, run_data)
    completed_run_job_data = get_run_job(run_job_id)
    if completed_run_job_data is None:
        raise PredictServiceError(500, "Failed to load run job")
    return completed_run_job_data


def execute_predict_request(request: PredictServiceInput) -> dict[str, Any]:
    """Execute the full `/predict` workflow and return run-job response."""
    creating_new_run = request.run_id is None
    requested_model = ""
    requested_model_version_id = request.model_version_id

    _stop_if_another_model_is_currently_executing()
    if creating_new_run:
        _validate_new_run_has_images(request)

    run_data: dict[str, Any] | None = None

    with get_database_connection() as database_connection:
        try:
            requested_model = get_model_file_name_for_run(
                database_connection=database_connection,
                model_version_id=requested_model_version_id,
                model_file_name=request.model_file_name,
            )
        except ValueError as error:
            raise PredictServiceError(400, str(error)) from error

        run_id = _resolve_run_id_for_predict_request(
            database_connection=database_connection,
            request=request,
            creating_new_run=creating_new_run,
            requested_model=requested_model,
            requested_model_version_id=requested_model_version_id,
        )
        if creating_new_run:
            current_model = requested_model
        else:
            current_model = get_model_name_from_run_id(database_connection, run_id)
            if requested_model_version_id is None:
                requested_model_version_id = get_model_version_id_from_run_id(database_connection, run_id)

        update_run_threshold(database_connection, run_id, request.threshold_score)

        (
            new_images_for_this_run,
            skipped_images,
            skipped_image_ids,
            invalid_image_ids,
        ) = _link_request_images_to_run(
            database_connection=database_connection,
            run_id=run_id,
            image_paths=request.image_paths,
            image_ids=request.image_ids,
        )

        images_to_process, using_new_model = _select_images_to_process(
            database_connection=database_connection,
            run_id=run_id,
            creating_new_run=creating_new_run,
            current_model=current_model,
            requested_model=requested_model,
            requested_model_version_id=requested_model_version_id,
            new_images_for_this_run=new_images_for_this_run,
        )

        run_data = _commit_run_updates_and_load_if_no_work(
            database_connection=database_connection,
            run_id=run_id,
            images_to_process=images_to_process,
        )

    try:
        run_job_data = create_run_job(
            run_id=run_id,
            total_images=len(images_to_process),
            skipped_images=skipped_images,
            skipped_image_ids=skipped_image_ids,
            invalid_image_ids=invalid_image_ids,
            using_new_model=using_new_model,
            processed_run_image_ids=images_to_process,
        )
    except RuntimeError as error:
        raise PredictServiceError(409, str(error)) from error

    if not images_to_process:
        return _complete_and_return_run_job_if_no_images_to_process(
            run_job_id=run_job_data["run_job_id"],
            run_data=run_data,
        )

    _start_model_execution(
        run_job_id=run_job_data["run_job_id"],
        run_id=run_id,
        images_to_process=images_to_process,
        requested_model=requested_model,
        threshold_score=request.threshold_score,
    )
    return run_job_data
