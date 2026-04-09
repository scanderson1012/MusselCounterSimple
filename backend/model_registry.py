"""Model, version, and dataset registry helpers."""

from __future__ import annotations

from pathlib import Path
import json
import shutil
import sqlite3
from typing import Any

from backend.init_db import MODELS_DIRECTORY
from backend.replay_buffer import list_replay_buffer_counts_by_model

DEFAULT_CLASS_MAPPING = {
    "1": "live",
    "2": "dead",
}


def list_model_options(database_connection: sqlite3.Connection) -> dict[str, Any]:
    """Return all active model versions for run selection."""
    sync_registry_with_disk(database_connection)
    versions = database_connection.execute(
        """
        SELECT
            model_versions.id,
            model_versions.family_id,
            model_families.name AS family_name,
            model_versions.version_number,
            model_versions.version_tag,
            model_versions.original_file_name,
            model_versions.model_file_name,
            model_versions.file_size_bytes,
            model_versions.created_at
        FROM model_versions
        JOIN model_families ON model_families.id = model_versions.family_id
        WHERE model_versions.is_deleted = 0
        ORDER BY model_families.name COLLATE NOCASE ASC, model_versions.version_number DESC
        """
    ).fetchall()
    return {
        "models_dir": str(MODELS_DIRECTORY.resolve()),
        "models": [
            {
                "id": int(version["id"]),
                "family_id": int(version["family_id"]),
                "family_name": str(version["family_name"]),
                "version_number": int(version["version_number"]),
                "version_tag": str(version["version_tag"]),
                "file_name": f"{version['family_name']} {version['version_tag']}",
                "original_file_name": str(version["original_file_name"]),
                "model_file_name": str(version["model_file_name"]),
                "size_bytes": int(version["file_size_bytes"] or 0),
                "created_at": str(version["created_at"]),
            }
            for version in versions
        ],
    }


def list_training_datasets(database_connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = database_connection.execute(
        """
        SELECT
            id,
            name,
            images_dir,
            labels_dir,
            description,
            created_at
        FROM training_datasets
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def list_test_datasets(database_connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = database_connection.execute(
        """
        SELECT
            id,
            name,
            images_dir,
            labels_dir,
            description,
            created_at
        FROM test_datasets
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def create_dataset_record(
    database_connection: sqlite3.Connection,
    table_name: str,
    name: str,
    images_dir: str,
    labels_dir: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Create one train/test dataset record after validating its directories."""
    if table_name not in {"training_datasets", "test_datasets"}:
        raise ValueError(f"Unsupported dataset table: {table_name}")

    validated_images_dir = _validate_dataset_directory(images_dir, "images_dir")
    validated_labels_dir = _validate_dataset_directory(labels_dir, "labels_dir")

    cursor = database_connection.execute(
        f"""
        INSERT INTO {table_name} (name, images_dir, labels_dir, description)
        VALUES (?, ?, ?, ?)
        """,
        (name.strip(), validated_images_dir, validated_labels_dir, _normalize_text(description)),
    )
    dataset_id = int(cursor.lastrowid)
    row = database_connection.execute(
        f"""
        SELECT
            id,
            name,
            images_dir,
            labels_dir,
            description,
            created_at
        FROM {table_name}
        WHERE id = ?
        """,
        (dataset_id,),
    ).fetchone()
    return dict(row) if row is not None else {"id": dataset_id}


def list_model_registry(database_connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return nested model families with versions and latest stored evaluation."""
    sync_registry_with_disk(database_connection)
    replay_buffer_counts = list_replay_buffer_counts_by_model(database_connection)
    family_rows = database_connection.execute(
        """
        SELECT
            id,
            name,
            created_at,
            updated_at
        FROM model_families
        ORDER BY name COLLATE NOCASE ASC, id ASC
        """
    ).fetchall()

    families: list[dict[str, Any]] = []
    for family_row in family_rows:
        family_data = dict(family_row)
        versions = database_connection.execute(
            """
            SELECT
                model_versions.id,
                model_versions.version_number,
                model_versions.version_tag,
                model_versions.parent_version_id,
                model_versions.original_file_name,
                model_versions.model_file_name,
                model_versions.file_size_bytes,
                model_versions.architecture,
                model_versions.num_classes,
                model_versions.class_mapping_json,
                model_versions.training_dataset_id,
                model_versions.test_dataset_id,
                model_versions.notes,
                model_versions.created_at,
                model_versions.updated_at,
                training_datasets.name AS training_dataset_name,
                test_datasets.name AS test_dataset_name
            FROM model_versions
            LEFT JOIN training_datasets ON training_datasets.id = model_versions.training_dataset_id
            LEFT JOIN test_datasets ON test_datasets.id = model_versions.test_dataset_id
            WHERE model_versions.family_id = ? AND model_versions.is_deleted = 0
            ORDER BY model_versions.version_number DESC
            """,
            (family_data["id"],),
        ).fetchall()

        family_data["versions"] = []
        for version_row in versions:
            version_data = dict(version_row)
            version_data["class_mapping"] = _parse_json(version_data.pop("class_mapping_json"), DEFAULT_CLASS_MAPPING)
            latest_evaluation = database_connection.execute(
                """
                SELECT
                    id,
                    test_dataset_id,
                    created_at,
                    score_threshold,
                    overall_metrics_json,
                    per_class_metrics_json,
                    summary_text
                FROM model_evaluations
                WHERE model_version_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (version_data["id"],),
            ).fetchone()
            version_data["latest_evaluation"] = None
            if latest_evaluation is not None:
                evaluation_data = dict(latest_evaluation)
                evaluation_data["overall_metrics"] = _parse_json(
                    evaluation_data.pop("overall_metrics_json"),
                    {},
                )
                evaluation_data["per_class_metrics"] = _parse_json(
                    evaluation_data.pop("per_class_metrics_json"),
                    [],
                )
                version_data["latest_evaluation"] = evaluation_data
            version_data["replay_buffer_counts"] = replay_buffer_counts.get(
                int(version_data["id"]),
                {"image_count": 0, "detection_count": 0},
            )
            family_data["versions"].append(version_data)

        families.append(family_data)

    return families


def register_baseline_model(
    database_connection: sqlite3.Connection,
    source_model_path: str,
    training_dataset_id: int,
    test_dataset_id: int,
    family_name: str | None = None,
    architecture: str = "fasterrcnn_resnet50_fpn_v2",
    num_classes: int = 3,
    class_mapping: dict[str, Any] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Register a baseline model as version v1 in managed storage."""
    source_path = Path(source_model_path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Model file not found: {source_model_path}")

    _require_dataset(database_connection, "training_datasets", training_dataset_id)
    _require_dataset(database_connection, "test_datasets", test_dataset_id)

    resolved_family_name = (family_name or source_path.stem).strip()
    if not resolved_family_name:
        raise ValueError("family_name cannot be empty")

    family_id = _get_or_create_family(database_connection, resolved_family_name)
    next_version_number = _get_next_version_number(database_connection, family_id)
    if next_version_number != 1:
        raise ValueError(
            f'Family "{resolved_family_name}" already exists. '
            "Use the future fine-tune flow to create v2+ versions."
        )

    managed_model_path = _copy_model_to_version_directory(
        source_path=source_path,
        family_name=resolved_family_name,
        version_number=next_version_number,
    )
    cursor = database_connection.execute(
        """
        INSERT INTO model_versions (
            family_id,
            version_number,
            version_tag,
            parent_version_id,
            original_file_name,
            model_file_name,
            file_size_bytes,
            architecture,
            num_classes,
            class_mapping_json,
            training_dataset_id,
            test_dataset_id,
            notes
        )
        VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            family_id,
            next_version_number,
            f"v{next_version_number}",
            source_path.name,
            str(managed_model_path),
            int(managed_model_path.stat().st_size),
            architecture,
            int(num_classes),
            json.dumps(class_mapping or DEFAULT_CLASS_MAPPING),
            training_dataset_id,
            test_dataset_id,
            _normalize_text(notes),
        ),
    )
    version_id = int(cursor.lastrowid)
    database_connection.execute(
        """
        UPDATE model_families
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (family_id,),
    )
    return get_model_version_by_id(database_connection, version_id)


def sync_registry_with_disk(database_connection: sqlite3.Connection) -> None:
    """Register loose model files from disk so legacy Add Model keeps working."""
    MODELS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for model_path in MODELS_DIRECTORY.rglob("*"):
        if not model_path.is_file():
            continue
        existing = database_connection.execute(
            """
            SELECT id
            FROM model_versions
            WHERE model_file_name = ?
            """,
            (str(model_path.resolve()),),
        ).fetchone()
        if existing is not None:
            continue

        family_id = _get_or_create_family(database_connection, model_path.stem)
        version_number = _get_next_version_number(database_connection, family_id)
        parent_version_id = None
        if version_number > 1:
            parent_row = database_connection.execute(
                """
                SELECT id
                FROM model_versions
                WHERE family_id = ? AND version_number = ?
                """,
                (family_id, version_number - 1),
            ).fetchone()
            if parent_row is not None:
                parent_version_id = int(parent_row["id"])

        database_connection.execute(
            """
            INSERT INTO model_versions (
                family_id,
                version_number,
                version_tag,
                parent_version_id,
                original_file_name,
                model_file_name,
                file_size_bytes,
                class_mapping_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                family_id,
                version_number,
                f"v{version_number}",
                parent_version_id,
                model_path.name,
                str(model_path.resolve()),
                int(model_path.stat().st_size),
                json.dumps(DEFAULT_CLASS_MAPPING),
            ),
        )


def get_model_version_by_id(
    database_connection: sqlite3.Connection,
    model_version_id: int,
) -> dict[str, Any] | None:
    rows = list_model_registry(database_connection)
    for family in rows:
        for version in family["versions"]:
            if int(version["id"]) == int(model_version_id):
                version_copy = dict(version)
                version_copy["family_name"] = family["name"]
                return version_copy
    return None


def get_model_file_name_for_run(
    database_connection: sqlite3.Connection,
    model_version_id: int | None,
    model_file_name: str | None = None,
) -> str:
    """Resolve the model file path from either version ID or direct path."""
    if model_version_id is not None:
        row = database_connection.execute(
            """
            SELECT model_file_name
            FROM model_versions
            WHERE id = ? AND is_deleted = 0
            """,
            (model_version_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Model version not found: {model_version_id}")
        return str(row["model_file_name"])

    if not model_file_name:
        raise ValueError("A model version or model file path is required")
    return str(model_file_name)


def delete_model_version(
    database_connection: sqlite3.Connection,
    model_version_id: int,
) -> bool:
    """Soft-delete one model version and remove its stored file when possible."""
    row = database_connection.execute(
        """
        SELECT
            model_versions.id,
            model_versions.family_id,
            model_versions.model_file_name,
            model_versions.is_deleted
        FROM model_versions
        WHERE model_versions.id = ?
        """,
        (model_version_id,),
    ).fetchone()
    if row is None:
        return False
    if int(row["is_deleted"] or 0) == 1:
        return True

    database_connection.execute(
        """
        UPDATE model_versions
        SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (model_version_id,),
    )
    database_connection.execute(
        """
        UPDATE model_families
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (int(row["family_id"]),),
    )

    model_path = Path(str(row["model_file_name"])).expanduser().resolve()
    if model_path.is_file():
        model_path.unlink(missing_ok=True)

    _delete_empty_parent_directories(model_path)
    return True


def _get_or_create_family(database_connection: sqlite3.Connection, family_name: str) -> int:
    row = database_connection.execute(
        """
        SELECT id
        FROM model_families
        WHERE name = ?
        """,
        (family_name,),
    ).fetchone()
    if row is not None:
        return int(row["id"])

    cursor = database_connection.execute(
        """
        INSERT INTO model_families (name)
        VALUES (?)
        """,
        (family_name,),
    )
    return int(cursor.lastrowid)


def _get_next_version_number(database_connection: sqlite3.Connection, family_id: int) -> int:
    existing_rows = database_connection.execute(
        """
        SELECT version_number
        FROM model_versions
        WHERE family_id = ?
        ORDER BY version_number ASC
        """,
        (family_id,),
    ).fetchall()
    existing_numbers = {int(row["version_number"]) for row in existing_rows}
    version_number = 1
    while version_number in existing_numbers:
        version_number += 1
    return version_number


def _copy_model_to_version_directory(
    source_path: Path,
    family_name: str,
    version_number: int,
) -> Path:
    safe_family_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in family_name)
    destination_directory = MODELS_DIRECTORY / safe_family_name / f"v{version_number}"
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination_path = destination_directory / source_path.name
    if source_path.resolve() != destination_path.resolve():
        shutil.copy2(source_path, destination_path)
    return destination_path.resolve()


def _parse_json(raw_value: Any, default_value: Any) -> Any:
    if raw_value in (None, ""):
        return default_value
    try:
        return json.loads(str(raw_value))
    except json.JSONDecodeError:
        return default_value


def _require_dataset(database_connection: sqlite3.Connection, table_name: str, dataset_id: int) -> None:
    row = database_connection.execute(
        f"""
        SELECT id
        FROM {table_name}
        WHERE id = ?
        """,
        (dataset_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"{table_name[:-1].replace('_', ' ')} not found: {dataset_id}")


def _validate_dataset_directory(raw_path: str, field_name: str) -> str:
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"{field_name} directory not found: {path}")
    return str(path)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _delete_empty_parent_directories(model_path: Path) -> None:
    """Best-effort cleanup for empty version/family folders under models storage."""
    try:
        models_root = MODELS_DIRECTORY.resolve()
    except FileNotFoundError:
        return

    current = model_path.parent
    while current != models_root and models_root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
