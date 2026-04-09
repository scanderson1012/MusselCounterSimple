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
            model_version_id
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if run_row is None:
        raise ValueError("Run not found")

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
            (run_row["model_version_id"], replay_buffer_run_id),
        )
        database_connection.execute(
            """
            DELETE FROM replay_buffer_images
            WHERE replay_buffer_run_id = ?
            """,
            (replay_buffer_run_id,),
        )

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
        replay_image_cursor = database_connection.execute(
            """
            INSERT INTO replay_buffer_images (
                replay_buffer_run_id,
                run_image_id,
                image_id,
                displayed_file_name,
                stored_path
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                replay_buffer_run_id,
                int(run_image["run_image_id"]),
                int(run_image["image_id"]),
                str(run_image["displayed_file_name"]),
                str(run_image["stored_path"]),
            ),
        )
        replay_buffer_image_id = int(replay_image_cursor.lastrowid)
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
            WHERE run_image_id = ? AND is_deleted = 0
            ORDER BY id ASC
            """,
            (int(run_image["run_image_id"]),),
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
        SELECT
            replay_buffer_runs.model_version_id,
            COALESCE(SUM(replay_buffer_runs.image_count), 0) AS image_count,
            COALESCE(SUM(replay_buffer_runs.detection_count), 0) AS detection_count
        FROM replay_buffer_runs
        WHERE replay_buffer_runs.model_version_id IS NOT NULL
        GROUP BY replay_buffer_runs.model_version_id
        """
    ).fetchall()
    return {
        int(row["model_version_id"]): {
            "image_count": int(row["image_count"] or 0),
            "detection_count": int(row["detection_count"] or 0),
        }
        for row in rows
    }
