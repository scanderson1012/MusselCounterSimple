from pathlib import Path
import json
import os
import sqlite3


BACKEND_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIRECTORY.parent
APP_DATA = Path(os.getenv("MUSSEL_APP_DATA_DIR", str(PROJECT_ROOT / "app_data"))).expanduser().resolve()
DB_PATH = APP_DATA / "app.db"
IMAGES_DIRECTORY = APP_DATA / "images"
MODELS_DIRECTORY = APP_DATA / "models"
EXPORTS_DIRECTORY = APP_DATA / "exports"
SCHEMA_PATH = BACKEND_DIRECTORY / "schema.sql"
BASELINE_MODEL_FAMILY_NAME = os.getenv("MUSSEL_BASELINE_MODEL_NAME", "fasterrcnn_baseline")
BASELINE_MODEL_PATH = Path(
    os.getenv("MUSSEL_BASELINE_MODEL_PATH", str(PROJECT_ROOT / "fasterrcnn_baseline.pth"))
).expanduser().resolve()
BASELINE_TRAIN_IMAGES_DIR = Path(
    os.getenv(
        "MUSSEL_BASELINE_TRAIN_IMAGES_DIR",
        r"C:\Users\scand\Downloads\Capstone baseline datasets\train\images",
    )
).expanduser().resolve()
BASELINE_TRAIN_LABELS_DIR = Path(
    os.getenv(
        "MUSSEL_BASELINE_TRAIN_LABELS_DIR",
        r"C:\Users\scand\Downloads\Capstone baseline datasets\train\labels",
    )
).expanduser().resolve()
BASELINE_TEST_IMAGES_DIR = Path(
    os.getenv(
        "MUSSEL_BASELINE_TEST_IMAGES_DIR",
        r"C:\Users\scand\Downloads\Capstone baseline datasets\test\images",
    )
).expanduser().resolve()
BASELINE_TEST_LABELS_DIR = Path(
    os.getenv(
        "MUSSEL_BASELINE_TEST_LABELS_DIR",
        r"C:\Users\scand\Downloads\Capstone baseline datasets\test\labels",
    )
).expanduser().resolve()
BASELINE_TRAIN_DATASET_NAME = os.getenv("MUSSEL_BASELINE_TRAIN_DATASET_NAME", "baseline_train")
BASELINE_TEST_DATASET_NAME = os.getenv("MUSSEL_BASELINE_TEST_DATASET_NAME", "baseline_test")
BASELINE_MODEL_DESCRIPTION = (
    "The is the baseline object detection model created by the Spring 2026 CMDA Capstone Mussel Milk team. "
    "It is trained on images containing dead and live, juvenile Lampsilis cardium (Pocketbook mussels). "
    "This model is meant to detect and classify this specific species. The model cannot be trusted to "
    "accurately detect and classify other mussels species or ages."
)
DEFAULT_APP_SETTINGS = {
    "fine_tune_min_new_images": "10",
    "fine_tune_num_epochs": "5",
}


def init_db() -> None:
    """Create app storage folders and apply the SQLite schema."""
    APP_DATA.mkdir(parents=True, exist_ok=True)
    IMAGES_DIRECTORY.mkdir(exist_ok=True)
    MODELS_DIRECTORY.mkdir(exist_ok=True)
    EXPORTS_DIRECTORY.mkdir(exist_ok=True)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        conn.executescript(schema_sql)
        _apply_migrations(conn)
        _seed_bundled_baseline(conn)
        conn.commit()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply lightweight schema migrations for older local DBs."""
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()
    }
    if "model_version_id" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN model_version_id INTEGER")

    replay_buffer_image_columns = set()
    if _table_exists(conn, "replay_buffer_images"):
        replay_buffer_image_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(replay_buffer_images)").fetchall()
        }
    if replay_buffer_image_columns and "model_version_id" not in replay_buffer_image_columns:
        conn.execute("ALTER TABLE replay_buffer_images ADD COLUMN model_version_id INTEGER")
    if replay_buffer_image_columns and "consumed_in_model_version_id" not in replay_buffer_image_columns:
        conn.execute("ALTER TABLE replay_buffer_images ADD COLUMN consumed_in_model_version_id INTEGER")
    if replay_buffer_image_columns and "consumed_at" not in replay_buffer_image_columns:
        conn.execute("ALTER TABLE replay_buffer_images ADD COLUMN consumed_at TEXT")

    model_version_columns = set()
    if _table_exists(conn, "model_versions"):
        model_version_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(model_versions)").fetchall()
        }
    if model_version_columns and "description" not in model_version_columns:
        conn.execute("ALTER TABLE model_versions ADD COLUMN description TEXT")

    # Backfill legacy disk models into the registry so existing installs still work.
    if _table_exists(conn, "model_versions"):
        _seed_legacy_models(conn)
        _backfill_bundled_baseline_description(conn)
    _seed_default_app_settings(conn)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    result = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return result is not None


def _seed_legacy_models(conn: sqlite3.Connection) -> None:
    """Register loose model files from the models directory as v1 families."""
    MODELS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for model_path in MODELS_DIRECTORY.iterdir():
        if not model_path.is_file():
            continue
        existing = conn.execute(
            """
            SELECT id
            FROM model_versions
            WHERE model_file_name = ?
            """,
            (str(model_path.resolve()),),
        ).fetchone()
        if existing is not None:
            continue

        family_name = model_path.stem
        family_row = conn.execute(
            """
            SELECT id
            FROM model_families
            WHERE name = ?
            """,
            (family_name,),
        ).fetchone()
        if family_row is None:
            cursor = conn.execute(
                """
                INSERT INTO model_families (name)
                VALUES (?)
                """,
                (family_name,),
            )
            family_id = int(cursor.lastrowid)
        else:
            family_id = int(family_row[0])

        conn.execute(
            """
            INSERT INTO model_versions (
                family_id,
                version_number,
                version_tag,
                original_file_name,
                model_file_name,
                file_size_bytes,
                class_mapping_json
            )
            VALUES (?, 1, 'v1', ?, ?, ?, ?)
            """,
            (
                family_id,
                model_path.name,
                str(model_path.resolve()),
                int(model_path.stat().st_size),
                json.dumps({"1": "live", "2": "dead"}),
            ),
        )


def _seed_bundled_baseline(conn: sqlite3.Connection) -> None:
    """Auto-register the bundled baseline model, datasets, and evaluation once."""
    if not _table_exists(conn, "model_versions"):
        return

    if not BASELINE_MODEL_PATH.is_file():
        return
    if not BASELINE_TRAIN_IMAGES_DIR.is_dir() or not BASELINE_TRAIN_LABELS_DIR.is_dir():
        return
    if not BASELINE_TEST_IMAGES_DIR.is_dir() or not BASELINE_TEST_LABELS_DIR.is_dir():
        return

    baseline_exists = conn.execute(
        """
        SELECT model_versions.id
        FROM model_versions
        JOIN model_families ON model_families.id = model_versions.family_id
        WHERE model_families.name = ? AND model_versions.version_number = 1
        """,
        (BASELINE_MODEL_FAMILY_NAME,),
    ).fetchone()
    if baseline_exists is not None:
        return

    from backend.model_registry import create_dataset_record
    from backend.model_registry import register_baseline_model

    training_dataset = _get_or_create_seed_dataset(
        conn=conn,
        table_name="training_datasets",
        name=BASELINE_TRAIN_DATASET_NAME,
        images_dir=str(BASELINE_TRAIN_IMAGES_DIR),
        labels_dir=str(BASELINE_TRAIN_LABELS_DIR),
        description="Bundled baseline training dataset",
        create_dataset_record=create_dataset_record,
    )
    test_dataset = _get_or_create_seed_dataset(
        conn=conn,
        table_name="test_datasets",
        name=BASELINE_TEST_DATASET_NAME,
        images_dir=str(BASELINE_TEST_IMAGES_DIR),
        labels_dir=str(BASELINE_TEST_LABELS_DIR),
        description="Bundled baseline test dataset",
        create_dataset_record=create_dataset_record,
    )

    model_version = register_baseline_model(
        database_connection=conn,
        source_model_path=str(BASELINE_MODEL_PATH),
        family_name=BASELINE_MODEL_FAMILY_NAME,
        training_dataset_id=int(training_dataset["id"]),
        test_dataset_id=int(test_dataset["id"]),
        description=BASELINE_MODEL_DESCRIPTION,
        notes="Bundled baseline model auto-registered on first launch.",
    )
    # The bundled baseline should be registered automatically, but users trigger
    # evaluation manually from the Models page.


def _backfill_bundled_baseline_description(conn: sqlite3.Connection) -> None:
    """Populate the bundled baseline description for older local databases."""
    conn.execute(
        """
        UPDATE model_versions
        SET description = ?
        WHERE id IN (
            SELECT model_versions.id
            FROM model_versions
            JOIN model_families ON model_families.id = model_versions.family_id
            WHERE model_families.name = ?
              AND model_versions.version_number = 1
              AND (model_versions.description IS NULL OR TRIM(model_versions.description) = '')
        )
        """,
        (BASELINE_MODEL_DESCRIPTION, BASELINE_MODEL_FAMILY_NAME),
    )


def _get_or_create_seed_dataset(
    conn: sqlite3.Connection,
    table_name: str,
    name: str,
    images_dir: str,
    labels_dir: str,
    description: str,
    create_dataset_record,
) -> dict[str, object]:
    existing_row = conn.execute(
        f"""
        SELECT
            id,
            name,
            images_dir,
            labels_dir,
            description,
            created_at
        FROM {table_name}
        WHERE name = ?
        """,
        (name,),
    ).fetchone()
    if existing_row is not None:
        return dict(existing_row)
    return create_dataset_record(
        database_connection=conn,
        table_name=table_name,
        name=name,
        images_dir=images_dir,
        labels_dir=labels_dir,
        description=description,
    )


def _seed_default_app_settings(conn: sqlite3.Connection) -> None:
    for setting_key, setting_value in DEFAULT_APP_SETTINGS.items():
        conn.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key) DO NOTHING
            """,
            (setting_key, setting_value),
        )


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB: {DB_PATH}")
