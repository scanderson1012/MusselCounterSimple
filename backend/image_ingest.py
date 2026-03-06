from pathlib import Path
from typing import Any
import hashlib
import shutil
import sqlite3

from backend.init_db import IMAGES_DIRECTORY


def compute_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 hash for a file."""
    # Initialize an incremental SHA-256 hasher.
    hasher = hashlib.sha256()

    # Read in chunks so large files do not load fully into memory.
    with file_path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(chunk_size)
            if not chunk:
                break
            # Feed each chunk into the hasher.
            hasher.update(chunk)

    # Return the final hex digest used as the dedup key.
    return hasher.hexdigest()


def _image_record_to_dict(
    image_from_database: sqlite3.Row, was_deduplicated: bool
) -> dict[str, Any]:
    """Build the common image data returned by ingest helpers."""
    image_data = {
        "image_id": image_from_database["id"],
        "displayed_file_name": image_from_database["displayed_file_name"],
        "stored_path": image_from_database["stored_path"],
        "sha_256_file_hash": image_from_database["sha_256_file_hash"],
        "created_at": image_from_database["created_at"],
    }
    image_data["was_deduplicated"] = was_deduplicated
    return image_data


def ingest_image_into_database(
    database_connection: sqlite3.Connection,
    image_path: str | Path | None = None,
    displayed_file_name: str | None = None,
    file_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Ingest one image into app storage and deduplicate by file hash."""
    database_connection.row_factory = sqlite3.Row

    # Support two input modes:
    # 1) file path from local disk, or
    # 2) uploaded bytes + displayed file name.
    if image_path is not None:
        source_path = Path(image_path).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Image file not found: {source_path}")
        displayed_file_name_value = source_path.name
        sha_256_file_hash = compute_sha256(source_path)
    else:
        if displayed_file_name is None or file_bytes is None:
            raise ValueError("Provide image_path or displayed_file_name + file_bytes.")
        if not file_bytes:
            raise ValueError("file_bytes cannot be empty.")
        displayed_file_name_value = displayed_file_name
        sha_256_file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Deduplicate globally by file content hash.
    existing_image_from_database = database_connection.execute(
        """
        SELECT id, displayed_file_name, stored_path, sha_256_file_hash, created_at
        FROM images
        WHERE sha_256_file_hash = ?
        """,
        (sha_256_file_hash,),
    ).fetchone()
    if existing_image_from_database is not None:
        return _image_record_to_dict(existing_image_from_database, was_deduplicated=True)

    # First time seeing this image hash: store bytes under a hash-based filename.
    IMAGES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    suffix = (
        Path(displayed_file_name_value).suffix.lower()
        if Path(displayed_file_name_value).suffix
        else ".bin"
    )
    stored_path = (IMAGES_DIRECTORY / f"{sha_256_file_hash}{suffix}").resolve()
    if not stored_path.exists():
        if image_path is not None:
            shutil.copy2(source_path, stored_path)
        else:
            stored_path.write_bytes(file_bytes)

    # Insert image metadata row and return standardized API data.
    inserted_image_from_database = database_connection.execute(
        """
        INSERT INTO images (displayed_file_name, stored_path, sha_256_file_hash)
        VALUES (?, ?, ?)
        RETURNING id, displayed_file_name, stored_path, sha_256_file_hash, created_at
        """,
        (displayed_file_name_value, str(stored_path), sha_256_file_hash),
    ).fetchone()
    if inserted_image_from_database is None:
        raise RuntimeError("Failed to insert image row")

    return _image_record_to_dict(inserted_image_from_database, was_deduplicated=False)
