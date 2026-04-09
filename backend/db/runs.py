"""Run-write helpers: create/update runs and manage run-image links."""

import sqlite3


def create_run(
    database_connection: sqlite3.Connection,
    model_file_name: str,
    threshold_score: float,
    model_version_id: int | None = None,
) -> int:
    """Insert a new run row and return its numeric ID."""
    cursor = database_connection.execute(
        """
        INSERT INTO runs (model_file_name, model_version_id, threshold_score)
        VALUES (?, ?, ?)
        """,
        (model_file_name, model_version_id, threshold_score),
    )
    return int(cursor.lastrowid)


def run_exists(database_connection: sqlite3.Connection, run_id: int) -> bool:
    """Return `True` when a run with the provided ID exists."""
    run_from_database = database_connection.execute(
        """
        SELECT id
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    return run_from_database is not None


def link_image_to_run(database_connection: sqlite3.Connection, run_id: int, image_id: int) -> tuple[int, bool]:
    """Link an image to a run and return `(run_image_id, was_inserted)`.

    If the link already exists, returns the existing `run_images.id` and `False`.
    """
    existing_run_image_from_database = database_connection.execute(
        """
        SELECT id
        FROM run_images
        WHERE run_id = ? AND image_id = ?
        """,
        (run_id, image_id),
    ).fetchone()
    if existing_run_image_from_database is not None:
        return int(existing_run_image_from_database["id"]), False

    cursor = database_connection.execute(
        """
        INSERT INTO run_images (run_id, image_id)
        VALUES (?, ?)
        """,
        (run_id, image_id),
    )
    return int(cursor.lastrowid), True


def update_run_mussel_count(database_connection: sqlite3.Connection, run_id: int) -> None:
    """Recalculate and persist run-level cached counts from `run_images`."""
    # Aggregate per-image counts into one run-level totals row.
    run_totals_from_database = database_connection.execute(
        """
        SELECT
            COUNT(*) AS image_count,
            COALESCE(SUM(live_mussel_count), 0) AS live_mussel_count,
            COALESCE(SUM(dead_mussel_count), 0) AS dead_mussel_count
        FROM run_images
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()

    database_connection.execute(
        """
        UPDATE runs
        SET
            image_count = ?,
            live_mussel_count = ?,
            dead_mussel_count = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            run_totals_from_database["image_count"],
            run_totals_from_database["live_mussel_count"],
            run_totals_from_database["dead_mussel_count"],
            run_id,
        ),
    )


def get_model_name_from_run_id(database_connection: sqlite3.Connection, run_id: int) -> str | None:
    """Return the run's current `model_file_name`, or `None` if run is missing."""
    model_file_name_from_database = database_connection.execute(
        """
        SELECT model_file_name
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if model_file_name_from_database is None:
        return None
    return model_file_name_from_database["model_file_name"]


def get_model_version_id_from_run_id(database_connection: sqlite3.Connection, run_id: int) -> int | None:
    """Return the run's current model version ID, or `None` if missing/unset."""
    row = database_connection.execute(
        """
        SELECT model_version_id
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None or row["model_version_id"] is None:
        return None
    return int(row["model_version_id"])


def update_this_runs_model(
    database_connection: sqlite3.Connection,
    run_id: int,
    model_file_name: str,
    model_version_id: int | None = None,
) -> None:
    """Set `model_file_name` for one run and touch `updated_at`."""
    database_connection.execute(
        """
        UPDATE runs
        SET model_file_name = ?, model_version_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (model_file_name, model_version_id, run_id),
    )


def update_run_threshold(database_connection: sqlite3.Connection, run_id: int, threshold_score: float) -> None:
    """Set `threshold_score` for one run and touch `updated_at`."""
    database_connection.execute(
        """
        UPDATE runs
        SET threshold_score = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (threshold_score, run_id),
    )


def unlink_image_from_run(database_connection: sqlite3.Connection, run_id: int, run_image_id: int) -> bool:
    """Delete one run-image link and return whether a row was removed."""
    cursor = database_connection.execute(
        """
        DELETE FROM run_images
        WHERE id = ? AND run_id = ?
        """,
        (run_image_id, run_id),
    )
    return cursor.rowcount > 0


def list_run_image_ids(database_connection: sqlite3.Connection, run_id: int) -> list[int]:
    """Return all `run_images.id` values for one run, ordered ascending."""
    run_images_from_database = database_connection.execute(
        """
        SELECT id
        FROM run_images
        WHERE run_id = ?
        ORDER BY id ASC
        """,
        (run_id,),
    ).fetchall()
    return [int(run_image_from_database["id"]) for run_image_from_database in run_images_from_database]
