"""Helpers for finalizing reviewed run labels into a replay buffer."""

from __future__ import annotations

from typing import Any
import sqlite3


def finalize_run_into_replay_buffer(
    database_connection: sqlite3.Connection,
    run_id: int,
) -> dict[str, Any]:
    """Snapshot one run's current reviewed labels into replay-buffer tables."""
    run_row = database_connection.execute(
        """
        SELECT
            id,
            model_version_id,
            threshold_score
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if run_row is None:
        raise ValueError("Run not found")
    model_version_id = None if run_row["model_version_id"] is None else int(run_row["model_version_id"])
    threshold_score = float(run_row["threshold_score"])

    existing_buffer_row = database_connection.execute(
        """
        SELECT id
        FROM replay_buffer_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if existing_buffer_row is None:
        cursor = database_connection.execute(
            """
            INSERT INTO replay_buffer_runs (run_id, model_version_id)
            VALUES (?, ?)
            """,
            (run_id, run_row["model_version_id"]),
        )
        replay_buffer_run_id = int(cursor.lastrowid)
    else:
        replay_buffer_run_id = int(existing_buffer_row["id"])
        database_connection.execute(
            """
            UPDATE replay_buffer_runs
            SET model_version_id = ?, finalized_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (model_version_id, replay_buffer_run_id),
        )
        _delete_run_owned_replay_entries(database_connection, replay_buffer_run_id)

    run_images = database_connection.execute(
        """
        SELECT
            run_images.id AS run_image_id,
            run_images.image_id,
            images.displayed_file_name,
            images.stored_path
        FROM run_images
        JOIN images ON images.id = run_images.image_id
        WHERE run_images.run_id = ?
        ORDER BY run_images.id ASC
        """,
        (run_id,),
    ).fetchall()

    finalized_image_count = 0
    finalized_detection_count = 0
    for run_image in run_images:
        existing_replay_image_rows = database_connection.execute(
            """
            SELECT id
            FROM replay_buffer_images
            WHERE model_version_id IS ? AND image_id = ?
            ORDER BY id ASC
            """,
            (model_version_id, int(run_image["image_id"])),
        ).fetchall()
        if not existing_replay_image_rows:
            inserted_cursor = database_connection.execute(
                """
                INSERT INTO replay_buffer_images (
                    replay_buffer_run_id,
                    model_version_id,
                    run_image_id,
                    image_id,
                    displayed_file_name,
                    stored_path
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    replay_buffer_run_id,
                    model_version_id,
                    int(run_image["run_image_id"]),
                    int(run_image["image_id"]),
                    str(run_image["displayed_file_name"]),
                    str(run_image["stored_path"]),
                ),
            )
            replay_buffer_image_id = int(inserted_cursor.lastrowid)
        else:
            replay_buffer_image_id = int(existing_replay_image_rows[0]["id"])
            database_connection.execute(
                """
                UPDATE replay_buffer_images
                SET
                    replay_buffer_run_id = ?,
                    model_version_id = ?,
                    run_image_id = ?,
                    displayed_file_name = ?,
                    stored_path = ?,
                    created_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    replay_buffer_run_id,
                    model_version_id,
                    int(run_image["run_image_id"]),
                    str(run_image["displayed_file_name"]),
                    str(run_image["stored_path"]),
                    replay_buffer_image_id,
                ),
            )
            database_connection.execute(
                """
                DELETE FROM replay_buffer_detections
                WHERE replay_buffer_image_id = ?
                """,
                (replay_buffer_image_id,),
            )
            duplicate_replay_image_ids = [
                int(row["id"]) for row in existing_replay_image_rows[1:]
            ]
            for duplicate_replay_image_id in duplicate_replay_image_ids:
                database_connection.execute(
                    """
                    DELETE FROM replay_buffer_detections
                    WHERE replay_buffer_image_id = ?
                    """,
                    (duplicate_replay_image_id,),
                )
                database_connection.execute(
                    """
                    DELETE FROM replay_buffer_images
                    WHERE id = ?
                    """,
                    (duplicate_replay_image_id,),
                )
        finalized_image_count += 1

        detections = database_connection.execute(
            """
            SELECT
                id,
                class_name,
                bbox_x1,
                bbox_y1,
                bbox_x2,
                bbox_y2,
                confidence_score,
                is_edited
            FROM detections
            WHERE run_image_id = ?
              AND is_deleted = 0
              AND (
                  confidence_score IS NULL OR COALESCE(confidence_score, 0) >= ?
              )
            ORDER BY id ASC
            """,
            (int(run_image["run_image_id"]), threshold_score),
        ).fetchall()

        for detection in detections:
            database_connection.execute(
                """
                INSERT INTO replay_buffer_detections (
                    replay_buffer_image_id,
                    class_name,
                    bbox_x1,
                    bbox_y1,
                    bbox_x2,
                    bbox_y2,
                    source_detection_id,
                    confidence_score,
                    was_edited
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    replay_buffer_image_id,
                    str(detection["class_name"]),
                    float(detection["bbox_x1"]),
                    float(detection["bbox_y1"]),
                    float(detection["bbox_x2"]),
                    float(detection["bbox_y2"]),
                    int(detection["id"]),
                    None if detection["confidence_score"] is None else float(detection["confidence_score"]),
                    int(detection["is_edited"] or 0),
                ),
            )
            finalized_detection_count += 1

    database_connection.execute(
        """
        UPDATE replay_buffer_runs
        SET
            image_count = ?,
            detection_count = ?,
            finalized_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (finalized_image_count, finalized_detection_count, replay_buffer_run_id),
    )

    return get_replay_buffer_summary_for_run(database_connection, run_id)


def get_replay_buffer_summary_for_run(
    database_connection: sqlite3.Connection,
    run_id: int,
) -> dict[str, Any] | None:
    row = database_connection.execute(
        """
        SELECT
            replay_buffer_runs.id,
            replay_buffer_runs.run_id,
            replay_buffer_runs.model_version_id,
            replay_buffer_runs.image_count,
            replay_buffer_runs.detection_count,
            replay_buffer_runs.finalized_at
        FROM replay_buffer_runs
        WHERE replay_buffer_runs.run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_replay_buffer_counts_by_model(database_connection: sqlite3.Connection) -> dict[int, dict[str, int]]:
    rows = database_connection.execute(
        """
        WITH canonical_replay_images AS (
            SELECT
                MAX(id) AS replay_buffer_image_id,
                model_version_id,
                image_id
            FROM replay_buffer_images
            WHERE model_version_id IS NOT NULL
            GROUP BY model_version_id, image_id
        )
        SELECT
            canonical_replay_images.model_version_id,
            COUNT(DISTINCT canonical_replay_images.replay_buffer_image_id) AS image_count,
            COUNT(replay_buffer_detections.id) AS detection_count
        FROM canonical_replay_images
        LEFT JOIN replay_buffer_detections
            ON replay_buffer_detections.replay_buffer_image_id = canonical_replay_images.replay_buffer_image_id
        GROUP BY canonical_replay_images.model_version_id
        """
    ).fetchall()
    return {
        int(row["model_version_id"]): {
            "image_count": int(row["image_count"] or 0),
            "detection_count": int(row["detection_count"] or 0),
        }
        for row in rows
    }


def _delete_run_owned_replay_entries(
    database_connection: sqlite3.Connection,
    replay_buffer_run_id: int,
) -> None:
    """Delete replay images/detections currently owned by one finalized run snapshot."""
    database_connection.execute(
        """
        DELETE FROM replay_buffer_detections
        WHERE replay_buffer_image_id IN (
            SELECT id
            FROM replay_buffer_images
            WHERE replay_buffer_run_id = ?
        )
        """,
        (replay_buffer_run_id,),
    )
    database_connection.execute(
        """
        DELETE FROM replay_buffer_images
        WHERE replay_buffer_run_id = ?
        """,
        (replay_buffer_run_id,),
    )


def remove_replay_buffer_entry_for_run_image(
    database_connection: sqlite3.Connection,
    run_image_id: int,
) -> None:
    """Remove replay-buffer data owned by one run image and refresh its run summary."""
    replay_image_rows = database_connection.execute(
        """
        SELECT
            id,
            replay_buffer_run_id
        FROM replay_buffer_images
        WHERE run_image_id = ?
        """,
        (run_image_id,),
    ).fetchall()
    if not replay_image_rows:
        return

    affected_run_ids = {int(row["replay_buffer_run_id"]) for row in replay_image_rows}
    for row in replay_image_rows:
        database_connection.execute(
            """
            DELETE FROM replay_buffer_detections
            WHERE replay_buffer_image_id = ?
            """,
            (int(row["id"]),),
        )
    database_connection.execute(
        """
        DELETE FROM replay_buffer_images
        WHERE run_image_id = ?
        """,
        (run_image_id,),
    )

    for replay_buffer_run_id in affected_run_ids:
        _refresh_replay_buffer_run_summary(database_connection, replay_buffer_run_id)


def _refresh_replay_buffer_run_summary(
    database_connection: sqlite3.Connection,
    replay_buffer_run_id: int,
) -> None:
    summary = database_connection.execute(
        """
        SELECT
            COUNT(*) AS image_count,
            (
                SELECT COUNT(*)
                FROM replay_buffer_detections
                WHERE replay_buffer_image_id IN (
                    SELECT id
                    FROM replay_buffer_images
                    WHERE replay_buffer_run_id = ?
                )
            ) AS detection_count
        FROM replay_buffer_images
        WHERE replay_buffer_run_id = ?
        """,
        (replay_buffer_run_id, replay_buffer_run_id),
    ).fetchone()
    image_count = int(summary["image_count"] or 0)
    detection_count = int(summary["detection_count"] or 0)
    if image_count == 0:
        database_connection.execute(
            """
            DELETE FROM replay_buffer_runs
            WHERE id = ?
            """,
            (replay_buffer_run_id,),
        )
        return

    database_connection.execute(
        """
        UPDATE replay_buffer_runs
        SET
            image_count = ?,
            detection_count = ?,
            finalized_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (image_count, detection_count, replay_buffer_run_id),
    )
