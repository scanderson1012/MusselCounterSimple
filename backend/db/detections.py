"""Detection update/recalculation helpers built on stored detection rows."""

from typing import Any

import sqlite3

from backend.db.runs import update_run_mussel_count


def recalculate_run_mussel_counts_from_detections(
    database_connection: sqlite3.Connection, run_id: int, threshold_score: float
) -> None:
    """Recompute all run-image counts for one run, then refresh run totals."""
    run_images_from_database = database_connection.execute(
        """
        SELECT id
        FROM run_images
        WHERE run_id = ?
        ORDER BY id ASC
        """,
        (run_id,),
    ).fetchall()

    for run_image_from_database in run_images_from_database:
        run_image_id = int(run_image_from_database["id"])
        # Recompute each run-image row independently from persisted detections.
        recalculate_run_image_mussel_counts_from_detections(
            database_connection, run_image_id, threshold_score
        )

    update_run_mussel_count(database_connection, run_id)


def recalculate_run_image_mussel_counts_from_detections(
    database_connection: sqlite3.Connection, run_image_id: int, threshold_score: float
) -> None:
    """Recompute one run-image live/dead counts from stored detections.

    Rules:
    - Ignore `is_deleted = 1` rows.
    - Count only detections with `confidence_score >= threshold_score`.
    """
    mussel_counts_from_database = database_connection.execute(
        """
        SELECT
            SUM(
                CASE
                    WHEN class_name = 'live' AND is_deleted = 0 AND (
                        confidence_score IS NULL OR COALESCE(confidence_score, 0) >= ?
                    )
                    THEN 1 ELSE 0
                END
            ) AS live_mussel_count,
            SUM(
                CASE
                    WHEN class_name = 'dead' AND is_deleted = 0 AND (
                        confidence_score IS NULL OR COALESCE(confidence_score, 0) >= ?
                    )
                    THEN 1 ELSE 0
                END
            ) AS dead_mussel_count
        FROM detections
        WHERE run_image_id = ?
        """,
        (threshold_score, threshold_score, run_image_id),
    ).fetchone()

    live_mussel_count = int(mussel_counts_from_database["live_mussel_count"] or 0)
    dead_mussel_count = int(mussel_counts_from_database["dead_mussel_count"] or 0)
    database_connection.execute(
        """
        UPDATE run_images
        SET
            live_mussel_count = ?,
            dead_mussel_count = ?
        WHERE id = ?
        """,
        (live_mussel_count, dead_mussel_count, run_image_id),
    )


def get_run_info_from_detection_id(
    database_connection: sqlite3.Connection, detection_id: int
) -> dict[str, Any] | None:
    """Return run context for one detection ID, or `None` if not found."""
    run_information_from_database = database_connection.execute(
        """
        SELECT
            detections.id AS detection_id,
            detections.run_image_id,
            run_images.run_id,
            runs.threshold_score
        FROM detections
        JOIN run_images ON run_images.id = detections.run_image_id
        JOIN runs ON runs.id = run_images.run_id
        WHERE detections.id = ?
        """,
        (detection_id,),
    ).fetchone()
    if run_information_from_database is None:
        return None
    return dict(run_information_from_database)


def update_detection_fields(
    database_connection: sqlite3.Connection, detection_id: int, fields_to_update: dict[str, Any]
) -> None:
    """Update one detection using a validated field subset.

    Allowed fields are limited so API callers cannot mutate unsupported columns.
    """
    allowed_fields = {
        "class_name",
        "is_edited",
        "is_deleted",
    }
    unknown_fields = set(fields_to_update.keys()) - allowed_fields
    if unknown_fields:
        raise ValueError(f"Unsupported detection fields: {sorted(unknown_fields)}")

    if not fields_to_update:
        return

    # Build dynamic assignment list from validated field names.
    assignments = ", ".join(f"{field_name} = ?" for field_name in fields_to_update.keys())
    values = list(fields_to_update.values()) + [detection_id]
    database_connection.execute(
        f"""
        UPDATE detections
        SET {assignments}
        WHERE id = ?
        """,
        values,
    )


def create_detection_for_run_image(
    database_connection: sqlite3.Connection,
    run_image_id: int,
    class_name: str,
    bbox_x1: float,
    bbox_y1: float,
    bbox_x2: float,
    bbox_y2: float,
    confidence_score: float | None = None,
    is_edited: int = 1,
) -> int:
    """Insert one new detection row for a run image and return its ID."""
    if class_name not in {"live", "dead"}:
        raise ValueError(f"Unsupported class_name: {class_name}")
    if bbox_x2 <= bbox_x1 or bbox_y2 <= bbox_y1:
        raise ValueError("Bounding box must have positive width and height")

    cursor = database_connection.execute(
        """
        INSERT INTO detections (
            run_image_id,
            class_name,
            confidence_score,
            bbox_x1,
            bbox_y1,
            bbox_x2,
            bbox_y2,
            is_edited,
            is_deleted
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            run_image_id,
            class_name,
            confidence_score,
            bbox_x1,
            bbox_y1,
            bbox_x2,
            bbox_y2,
            is_edited,
        ),
    )
    return int(cursor.lastrowid)
