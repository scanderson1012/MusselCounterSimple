"""Read-only database helpers for runs, images, and nested response payloads."""

from typing import Any

import sqlite3


def get_image_file_metadata_from_database(
    database_connection: sqlite3.Connection, image_id: int
) -> dict[str, Any] | None:
    """Return stored file metadata for one image ID, or `None` if missing."""
    image_file_metadata = database_connection.execute(
        """
        SELECT
            id,
            displayed_file_name,
            stored_path
        FROM images
        WHERE id = ?
        """,
        (image_id,),
    ).fetchone()
    if image_file_metadata is None:
        return None
    return dict(image_file_metadata)


def get_run_from_database(database_connection: sqlite3.Connection, run_id: int) -> dict[str, Any] | None:
    """Return one full run payload (run + images + detections).

    This is the detailed shape used by the run-detail frontend page.
    """
    run_from_database = database_connection.execute(
        """
        SELECT
            id,
            created_at,
            updated_at,
            model_file_name,
            model_version_id,
            threshold_score,
            image_count,
            live_mussel_count,
            dead_mussel_count
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if run_from_database is None:
        return None

    run_data = dict(run_from_database)
    run_data["total_mussels"] = (
        run_data["live_mussel_count"] + run_data["dead_mussel_count"]
    )

    # Load all images linked to this run, in stable insertion order.
    images_from_database = database_connection.execute(
        """
        SELECT
            run_images.id AS run_image_id,
            run_images.image_id,
            images.displayed_file_name,
            images.stored_path,
            run_images.live_mussel_count,
            run_images.dead_mussel_count,
            run_images.created_at,
            EXISTS(
                SELECT 1
                FROM replay_buffer_images
                WHERE replay_buffer_images.run_image_id = run_images.id
                  AND replay_buffer_images.consumed_in_model_version_id IS NOT NULL
            ) AS is_locked_for_editing
        FROM run_images
        JOIN images ON images.id = run_images.image_id
        WHERE run_images.run_id = ?
        ORDER BY run_images.id ASC
        """,
        (run_id,),
    ).fetchall()

    images: list[dict[str, Any]] = []
    for image_from_database in images_from_database:
        image_data = dict(image_from_database)
        image_data["image_url"] = f"/images/{image_data['image_id']}"
        image_data["total_mussels"] = (
            image_data["live_mussel_count"] + image_data["dead_mussel_count"]
        )
        # Attach detections for each run-image row.
        detections_from_database = database_connection.execute(
            """
            SELECT
                id,
                run_image_id,
                class_name,
                confidence_score,
                bbox_x1,
                bbox_y1,
                bbox_x2,
                bbox_y2,
                is_edited,
                is_deleted
            FROM detections
            WHERE run_image_id = ?
            ORDER BY id ASC
            """,
            (image_data["run_image_id"],),
        ).fetchall()
        image_data["detections"] = [
            dict(detection_from_database) for detection_from_database in detections_from_database
        ]
        images.append(image_data)

    run_data["images"] = images
    run_data["preview_image_url"] = images[0]["image_url"] if images else None
    replay_buffer_summary = database_connection.execute(
        """
        SELECT
            id,
            image_count,
            detection_count,
            finalized_at
        FROM replay_buffer_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    run_data["replay_buffer_summary"] = (
        dict(replay_buffer_summary) if replay_buffer_summary is not None else None
    )
    return run_data


def list_runs_from_database(database_connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return run summary rows for the history/collections view."""
    run_summaries_from_database = database_connection.execute(
        """
        SELECT
            runs.id,
            runs.created_at,
            runs.updated_at,
            runs.model_file_name,
            runs.model_version_id,
            runs.threshold_score,
            runs.image_count,
            runs.live_mussel_count,
            runs.dead_mussel_count,
            (
                SELECT run_images.image_id
                FROM run_images
                WHERE run_images.run_id = runs.id
                ORDER BY run_images.id ASC
                LIMIT 1
            ) AS preview_image_id,
            (
                SELECT images.stored_path
                FROM run_images
                JOIN images ON images.id = run_images.image_id
                WHERE run_images.run_id = runs.id
                ORDER BY run_images.id ASC
                LIMIT 1
            ) AS preview_image_path
        FROM runs
        WHERE runs.image_count > 0
        ORDER BY runs.created_at DESC, runs.id DESC
        """
    ).fetchall()

    runs_data = [
        dict(run_summary_from_database) for run_summary_from_database in run_summaries_from_database
    ]
    for run in runs_data:
        run["total_mussels"] = run["live_mussel_count"] + run["dead_mussel_count"]
        preview_image_id = run["preview_image_id"]
        # Frontend serves previews through the backend image endpoint.
        run["preview_image_url"] = (
            f"/images/{preview_image_id}" if preview_image_id is not None else None
        )
    return runs_data
