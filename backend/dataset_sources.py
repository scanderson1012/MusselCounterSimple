"""Dataset source helpers for folder-pair and Roboflow zip inputs.

These helpers normalize the two dataset shapes the app supports:
- legacy folder pairs (`images_dir` + `labels_dir`)
- Roboflow export zip files containing `train`, `test`, and `valid/val`
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from backend.init_db import APP_DATA
from backend.training_config import VALID_IMAGE_EXTENSIONS

DATASET_CACHE_DIRECTORY = APP_DATA / "dataset_cache"
DATASET_FORMAT_FOLDER_PAIRS = "folder_pairs"
DATASET_FORMAT_ROBOFLOW_ZIP = "roboflow_zip"


@dataclass(slots=True)
class DatasetSource:
    """Resolved dataset pointer used by training, fine-tuning, and evaluation."""

    dataset_format: str
    images_dir: Path | None = None
    labels_dir: Path | None = None
    zip_file_path: Path | None = None
    split_name: str | None = None
    split_dir: Path | None = None


def create_dataset_source(
    *,
    images_dir: str | None = None,
    labels_dir: str | None = None,
    zip_file_path: str | None = None,
    split_name: str | None = None,
    dataset_format: str | None = None,
) -> DatasetSource:
    """Validate input dataset metadata and return a normalized source object."""
    resolved_format = str(dataset_format or "").strip().lower()
    if zip_file_path:
        resolved_format = resolved_format or DATASET_FORMAT_ROBOFLOW_ZIP
    else:
        resolved_format = resolved_format or DATASET_FORMAT_FOLDER_PAIRS

    if resolved_format == DATASET_FORMAT_ROBOFLOW_ZIP:
        if not str(zip_file_path or "").strip():
            raise FileNotFoundError("dataset zip file path is required for Roboflow zip datasets")
        if not str(split_name or "").strip():
            raise ValueError("split_name is required for Roboflow zip datasets")
        split_dir = resolve_roboflow_split_directory(zip_file_path=str(zip_file_path), split_name=str(split_name))
        return DatasetSource(
            dataset_format=DATASET_FORMAT_ROBOFLOW_ZIP,
            zip_file_path=Path(str(zip_file_path)).expanduser().resolve(),
            split_name=str(split_name).strip().lower(),
            split_dir=split_dir,
        )

    validated_images_dir = _validate_directory(images_dir, "images_dir")
    validated_labels_dir = _validate_directory(labels_dir, "labels_dir")
    return DatasetSource(
        dataset_format=DATASET_FORMAT_FOLDER_PAIRS,
        images_dir=validated_images_dir,
        labels_dir=validated_labels_dir,
    )


def resolve_roboflow_split_directory(zip_file_path: str, split_name: str) -> Path:
    """Extract a Roboflow zip to cache and return the requested split directory."""
    zip_path = Path(zip_file_path).expanduser().resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(f"Dataset zip file not found: {zip_path}")
    if zip_path.suffix.lower() != ".zip":
        raise ValueError(f"Dataset file must be a .zip file: {zip_path}")

    normalized_split_name = str(split_name).strip().lower()
    if normalized_split_name not in {"train", "test", "valid", "val"}:
        raise ValueError(f"Unsupported dataset split: {split_name}")

    extraction_root = _extract_zip_to_cache(zip_path)
    dataset_root = _discover_dataset_root(extraction_root)
    candidate_names = [normalized_split_name]
    if normalized_split_name == "val":
        candidate_names.append("valid")
    if normalized_split_name == "valid":
        candidate_names.append("val")
    for candidate_name in candidate_names:
        split_dir = dataset_root / candidate_name
        if split_dir.is_dir():
            return split_dir.resolve()
    raise FileNotFoundError(
        f'Could not find a "{normalized_split_name}" folder inside {zip_path}'
    )


def list_pascal_voc_samples(dataset_source: DatasetSource) -> list[tuple[Path, Path]]:
    """Return matching image/XML pairs for one dataset source."""
    if dataset_source.dataset_format == DATASET_FORMAT_ROBOFLOW_ZIP:
        assert dataset_source.split_dir is not None
        split_dir = dataset_source.split_dir
        image_paths = sorted(
            path for path in split_dir.iterdir()
            if path.is_file() and path.suffix.lower() in VALID_IMAGE_EXTENSIONS
        )
        samples = []
        for image_path in image_paths:
            label_path = split_dir / f"{image_path.stem}.xml"
            if label_path.is_file():
                samples.append((image_path.resolve(), label_path.resolve()))
        if not samples:
            raise ValueError(f"No valid image/XML pairs were found in {split_dir}")
        return samples

    assert dataset_source.images_dir is not None
    assert dataset_source.labels_dir is not None
    image_paths = sorted(
        path for path in dataset_source.images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VALID_IMAGE_EXTENSIONS
    )
    samples = []
    for image_path in image_paths:
        label_path = dataset_source.labels_dir / f"{image_path.stem}.xml"
        if label_path.is_file():
            samples.append((image_path.resolve(), label_path.resolve()))
    if not samples:
        raise ValueError(
            f"No valid image/XML pairs were found in {dataset_source.images_dir}"
        )
    return samples


def dataset_record_to_source(dataset_record: dict) -> DatasetSource:
    """Convert a DB dataset row into a validated `DatasetSource`."""
    return create_dataset_source(
        images_dir=str(dataset_record.get("images_dir") or ""),
        labels_dir=str(dataset_record.get("labels_dir") or ""),
        zip_file_path=str(dataset_record.get("zip_file_path") or ""),
        split_name=str(dataset_record.get("split_name") or ""),
        dataset_format=str(dataset_record.get("dataset_format") or ""),
    )


def _validate_directory(raw_path: str | None, field_name: str) -> Path:
    path = Path(str(raw_path or "")).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"{field_name} directory not found: {path}")
    return path


def _extract_zip_to_cache(zip_path: Path) -> Path:
    """Extract one zip into a deterministic cache directory."""
    DATASET_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stat = zip_path.stat()
    cache_key = sha256(
        f"{zip_path}|{stat.st_size}|{stat.st_mtime}".encode("utf-8")
    ).hexdigest()[:16]
    extraction_root = DATASET_CACHE_DIRECTORY / cache_key
    marker_path = extraction_root / ".extracted"
    if marker_path.is_file():
        return extraction_root.resolve()

    if extraction_root.exists():
        _clear_directory(extraction_root)
    extraction_root.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "r") as zip_file:
        zip_file.extractall(extraction_root)
    marker_path.write_text("ok", encoding="utf-8")
    return extraction_root.resolve()


def _discover_dataset_root(extraction_root: Path) -> Path:
    """Prefer a single extracted top-level folder when the zip contains one."""
    extracted_dirs = [path for path in extraction_root.iterdir() if path.is_dir()]
    extracted_files = [path for path in extraction_root.iterdir() if path.is_file() and path.name != ".extracted"]
    if len(extracted_dirs) == 1 and not extracted_files:
        return extracted_dirs[0].resolve()
    return extraction_root.resolve()


def _clear_directory(directory: Path) -> None:
    """Remove all children inside a cache directory while keeping the root folder."""
    for child in directory.iterdir():
        if child.is_dir():
            for nested in sorted(child.rglob("*"), reverse=True):
                if nested.is_file():
                    nested.unlink(missing_ok=True)
                elif nested.is_dir():
                    nested.rmdir()
            child.rmdir()
        else:
            child.unlink(missing_ok=True)
