"""Model, version, and dataset registry helpers."""

from __future__ import annotations

from pathlib import Path
import json
import shutil
import sqlite3
from typing import Any

from backend.dataset_sources import DATASET_FORMAT_FOLDER_PAIRS
from backend.dataset_sources import DATASET_FORMAT_ROBOFLOW_ZIP
from backend.dataset_sources import create_dataset_source
from backend.init_db import BASELINE_MODEL_FAMILY_NAME
from backend.init_db import MODELS_DIRECTORY
from backend.replay_buffer import list_replay_buffer_counts_by_model
from backend.replay_buffer import restore_replay_buffer_images_to_model

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
                "is_bundled_baseline": _is_protected_baseline_family(str(version["family_name"])),
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
            zip_file_path,
            split_name,
            dataset_format,
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
            zip_file_path,
            split_name,
            dataset_format,
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
    images_dir: str | None = None,
    labels_dir: str | None = None,
    zip_file_path: str | None = None,
    split_name: str | None = None,
    dataset_format: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Create one train/test dataset record after validating its directories."""
    if table_name not in {"training_datasets", "test_datasets"}:
        raise ValueError(f"Unsupported dataset table: {table_name}")
    dataset_source = create_dataset_source(
        images_dir=images_dir,
        labels_dir=labels_dir,
        zip_file_path=zip_file_path,
        split_name=split_name,
        dataset_format=dataset_format,
    )
    validated_images_dir = (
        str(dataset_source.images_dir)
        if dataset_source.images_dir is not None
        else ""
    )
    validated_labels_dir = (
        str(dataset_source.labels_dir)
        if dataset_source.labels_dir is not None
        else ""
    )
    validated_zip_file_path = (
        str(dataset_source.zip_file_path)
        if dataset_source.zip_file_path is not None
        else None
    )
    normalized_split_name = (
        str(dataset_source.split_name)
        if dataset_source.split_name is not None
        else None
    )

    cursor = database_connection.execute(
        f"""
        INSERT INTO {table_name} (
            name,
            images_dir,
            labels_dir,
            zip_file_path,
            split_name,
            dataset_format,
            description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name.strip(),
            validated_images_dir,
            validated_labels_dir,
            validated_zip_file_path,
            normalized_split_name,
            dataset_source.dataset_format,
            _normalize_text(description),
        ),
    )
    dataset_id = int(cursor.lastrowid)
    row = database_connection.execute(
        f"""
        SELECT
            id,
            name,
            images_dir,
            labels_dir,
            zip_file_path,
            split_name,
            dataset_format,
            description,
            created_at
        FROM {table_name}
        WHERE id = ?
        """,
        (dataset_id,),
    ).fetchone()
    return dict(row) if row is not None else {"id": dataset_id}


def get_or_create_dataset_record(
    database_connection: sqlite3.Connection,
    table_name: str,
    name: str,
    images_dir: str | None = None,
    labels_dir: str | None = None,
    zip_file_path: str | None = None,
    split_name: str | None = None,
    dataset_format: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Return an existing dataset with matching paths or create a new one."""
    if table_name not in {"training_datasets", "test_datasets"}:
        raise ValueError(f"Unsupported dataset table: {table_name}")
    dataset_source = create_dataset_source(
        images_dir=images_dir,
        labels_dir=labels_dir,
        zip_file_path=zip_file_path,
        split_name=split_name,
        dataset_format=dataset_format,
    )
    if dataset_source.dataset_format == DATASET_FORMAT_ROBOFLOW_ZIP:
        row = database_connection.execute(
            f"""
            SELECT
                id,
                name,
                images_dir,
                labels_dir,
                zip_file_path,
                split_name,
                dataset_format,
                description,
                created_at
            FROM {table_name}
            WHERE dataset_format = ? AND zip_file_path = ? AND split_name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                DATASET_FORMAT_ROBOFLOW_ZIP,
                str(dataset_source.zip_file_path),
                str(dataset_source.split_name),
            ),
        ).fetchone()
    else:
        row = database_connection.execute(
            f"""
            SELECT
                id,
                name,
                images_dir,
                labels_dir,
                zip_file_path,
                split_name,
                dataset_format,
                description,
                created_at
            FROM {table_name}
            WHERE dataset_format = ? AND images_dir = ? AND labels_dir = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                DATASET_FORMAT_FOLDER_PAIRS,
                str(dataset_source.images_dir),
                str(dataset_source.labels_dir),
            ),
        ).fetchone()
    if row is not None:
        return dict(row)

    resolved_name = _make_unique_dataset_name(database_connection, table_name, name)
    return create_dataset_record(
        database_connection=database_connection,
        table_name=table_name,
        name=resolved_name,
        images_dir=str(dataset_source.images_dir) if dataset_source.images_dir is not None else None,
        labels_dir=str(dataset_source.labels_dir) if dataset_source.labels_dir is not None else None,
        zip_file_path=str(dataset_source.zip_file_path) if dataset_source.zip_file_path is not None else None,
        split_name=str(dataset_source.split_name) if dataset_source.split_name is not None else None,
        dataset_format=dataset_source.dataset_format,
        description=description,
    )


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
        family_data["is_bundled_baseline"] = _is_protected_baseline_family(str(family_data["name"]))
        versions = database_connection.execute(
            """
            SELECT
                model_versions.id,
                model_versions.family_id,
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
                model_versions.description,
                model_versions.notes,
                model_versions.created_at,
                model_versions.updated_at,
                training_datasets.name AS training_dataset_name,
                training_datasets.images_dir AS training_images_dir,
                training_datasets.labels_dir AS training_labels_dir,
                training_datasets.zip_file_path AS training_dataset_zip_file_path,
                training_datasets.split_name AS training_dataset_split_name,
                training_datasets.dataset_format AS training_dataset_format,
                training_datasets.description AS training_dataset_description,
                test_datasets.name AS test_dataset_name,
                test_datasets.images_dir AS test_images_dir,
                test_datasets.labels_dir AS test_labels_dir,
                test_datasets.zip_file_path AS test_dataset_zip_file_path,
                test_datasets.split_name AS test_dataset_split_name,
                test_datasets.dataset_format AS test_dataset_format,
                test_datasets.description AS test_dataset_description
            FROM model_versions
            LEFT JOIN training_datasets ON training_datasets.id = model_versions.training_dataset_id
            LEFT JOIN test_datasets ON test_datasets.id = model_versions.test_dataset_id
            WHERE model_versions.family_id = ? AND model_versions.is_deleted = 0
            ORDER BY model_versions.version_number DESC
            """,
            (family_data["id"],),
        ).fetchall()

        family_data["versions"] = []
        latest_version_number = max((int(version_row["version_number"]) for version_row in versions), default=0)
        for version_row in versions:
            version_data = dict(version_row)
            version_data["class_mapping"] = _parse_json(version_data.pop("class_mapping_json"), DEFAULT_CLASS_MAPPING)
            version_data["is_bundled_baseline"] = bool(family_data["is_bundled_baseline"])
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
            version_data["is_latest_version"] = int(version_data["version_number"]) == latest_version_number
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
    description: str | None = None,
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
            description,
            notes
        )
        VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            _normalize_text(description),
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
    """Permanently delete one version and all later versions in its family."""
    row = database_connection.execute(
        """
        SELECT
            model_versions.id,
            model_versions.family_id,
            model_families.name AS family_name,
            model_versions.version_number,
            model_versions.model_file_name,
            model_versions.is_deleted
        FROM model_versions
        JOIN model_families ON model_families.id = model_versions.family_id
        WHERE model_versions.id = ?
        """,
        (model_version_id,),
    ).fetchone()
    if row is None:
        return False
    if _is_protected_baseline_family(str(row["family_name"])) and int(row["version_number"]) <= 1:
        raise ValueError("The bundled baseline model v1 cannot be deleted.")

    rows_to_delete = database_connection.execute(
        """
        SELECT
            id,
            family_id,
            version_number,
            model_file_name
        FROM model_versions
        WHERE family_id = ? AND version_number >= ?
        ORDER BY version_number DESC
        """,
        (int(row["family_id"]), int(row["version_number"])),
    ).fetchall()
    deleted_version_ids = [int(version_row["id"]) for version_row in rows_to_delete]
    surviving_latest_row = database_connection.execute(
        """
        SELECT id
        FROM model_versions
        WHERE family_id = ? AND version_number < ?
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (int(row["family_id"]), int(row["version_number"])),
    ).fetchone()
    restored_model_version_id = (
        None if surviving_latest_row is None else int(surviving_latest_row["id"])
    )
    restore_replay_buffer_images_to_model(
        database_connection=database_connection,
        deleted_version_ids=deleted_version_ids,
        restored_model_version_id=restored_model_version_id,
    )
    for version_row in rows_to_delete:
        model_path = Path(str(version_row["model_file_name"])).expanduser().resolve()
        if model_path.is_file():
            model_path.unlink(missing_ok=True)
        _delete_empty_parent_directories(model_path)

    database_connection.execute(
        """
        DELETE FROM model_versions
        WHERE family_id = ? AND version_number >= ?
        """,
        (int(row["family_id"]), int(row["version_number"])),
    )
    remaining_versions = database_connection.execute(
        """
        SELECT id
        FROM model_versions
        WHERE family_id = ?
        LIMIT 1
        """,
        (int(row["family_id"]),),
    ).fetchone()
    if remaining_versions is None:
        database_connection.execute(
            """
            DELETE FROM model_families
            WHERE id = ?
            """,
            (int(row["family_id"]),),
        )
    else:
        database_connection.execute(
            """
            UPDATE model_families
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(row["family_id"]),),
        )
    return True


def delete_model_family(
    database_connection: sqlite3.Connection,
    family_id: int,
) -> bool:
    """Permanently delete every version in one family."""
    family_row = database_connection.execute(
        """
        SELECT id, name
        FROM model_families
        WHERE id = ?
        """,
        (family_id,),
    ).fetchone()
    if family_row is None:
        return False
    if _is_protected_baseline_family(str(family_row["name"])):
        raise ValueError("The bundled baseline model cannot be deleted.")

    rows = database_connection.execute(
        """
        SELECT
            id
        FROM model_versions
        WHERE family_id = ?
        ORDER BY version_number DESC
        """,
        (family_id,),
    ).fetchall()
    if not rows:
        return True

    restore_replay_buffer_images_to_model(
        database_connection=database_connection,
        deleted_version_ids=[int(row["id"]) for row in rows],
        restored_model_version_id=None,
    )

    version_rows = database_connection.execute(
        """
        SELECT
            id,
            model_file_name
        FROM model_versions
        WHERE family_id = ?
        ORDER BY version_number DESC
        """,
        (family_id,),
    ).fetchall()
    for version_row in version_rows:
        model_path = Path(str(version_row["model_file_name"])).expanduser().resolve()
        if model_path.is_file():
            model_path.unlink(missing_ok=True)
        _delete_empty_parent_directories(model_path)
    database_connection.execute(
        """
        DELETE FROM model_versions
        WHERE family_id = ?
        """,
        (family_id,),
    )
    database_connection.execute(
        """
        DELETE FROM model_families
        WHERE id = ?
        """,
        (family_id,),
    )
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


def get_next_version_number_for_family(database_connection: sqlite3.Connection, family_id: int) -> int:
    """Public helper for next available version number within one family."""
    return _get_next_version_number(database_connection, family_id)


def register_finetuned_model_version(
    database_connection: sqlite3.Connection,
    parent_version_id: int,
    model_file_path: str,
) -> dict[str, Any]:
    """Register one saved fine-tuned checkpoint as the next version in a family."""
    parent_row = database_connection.execute(
        """
        SELECT
            model_versions.id,
            model_versions.family_id,
            model_versions.version_number,
            model_versions.original_file_name,
            model_versions.architecture,
            model_versions.num_classes,
            model_versions.class_mapping_json,
            model_versions.training_dataset_id,
            model_versions.test_dataset_id,
            model_versions.description,
            model_versions.notes
        FROM model_versions
        WHERE model_versions.id = ?
        """,
        (int(parent_version_id),),
    ).fetchone()
    if parent_row is None:
        raise ValueError("Parent model version not found.")

    model_path = Path(model_file_path).expanduser().resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"Fine-tuned model file not found: {model_path}")

    next_version_number = _get_next_version_number(database_connection, int(parent_row["family_id"]))
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
            description,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(parent_row["family_id"]),
            next_version_number,
            f"v{next_version_number}",
            int(parent_row["id"]),
            str(parent_row["original_file_name"]),
            str(model_path),
            int(model_path.stat().st_size),
            str(parent_row["architecture"]),
            int(parent_row["num_classes"]),
            str(parent_row["class_mapping_json"]),
            parent_row["training_dataset_id"],
            parent_row["test_dataset_id"],
            _normalize_text(parent_row["description"]),
            _normalize_text(parent_row["notes"]),
        ),
    )
    version_id = int(cursor.lastrowid)
    database_connection.execute(
        """
        UPDATE model_families
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (int(parent_row["family_id"]),),
    )
    return get_model_version_by_id(database_connection, version_id)


def build_model_file_path_for_version(
    family_name: str,
    version_number: int,
    original_file_name: str,
) -> Path:
    """Return the managed checkpoint path for one version without copying any file."""
    safe_family_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in family_name)
    destination_directory = MODELS_DIRECTORY / safe_family_name / f"v{version_number}"
    destination_directory.mkdir(parents=True, exist_ok=True)
    return (destination_directory / original_file_name).resolve()


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
def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _make_unique_dataset_name(
    database_connection: sqlite3.Connection,
    table_name: str,
    preferred_name: str,
) -> str:
    base_name = preferred_name.strip() or "dataset"
    candidate_name = base_name
    suffix = 2
    while True:
        existing = database_connection.execute(
            f"""
            SELECT id
            FROM {table_name}
            WHERE name = ?
            """,
            (candidate_name,),
        ).fetchone()
        if existing is None:
            return candidate_name
        candidate_name = f"{base_name}_{suffix}"
        suffix += 1


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


def _is_protected_baseline_family(family_name: str) -> bool:
    return family_name.strip().lower() == BASELINE_MODEL_FAMILY_NAME.strip().lower()
