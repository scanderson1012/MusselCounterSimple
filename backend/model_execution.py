"""Faster R-CNN inference + database writeback helpers.

This module handles the full backend model_execution path:
- Resolve and validate the requested model file path.
- Load and cache the RCNN model by file modified-time.
- Run per-image model_execution and normalize detections into DB-friendly fields.
- Replace detections/counts for each `run_images` row being processed.
"""

from pathlib import Path
from typing import Callable
from typing import Any
import sqlite3

from PIL import Image
import torch
import torchvision

from backend.compute import resolve_torch_device
from backend.training_config import CLASS_ID_TO_NAME
from backend.training_config import MODEL_ARCHITECTURE
from backend.training_config import NUM_CLASSES
from backend.training_config import invert_replay_boxes
from backend.training_config import normalize_loaded_state_dict
from backend.training_config import replay_transform_image

RCNN_LABELS = CLASS_ID_TO_NAME

# Whitelisted TorchVision Faster R-CNN builders.
_SUPPORTED_ARCHS: dict[str, Any] = {
    "fasterrcnn_resnet50_fpn": torchvision.models.detection.fasterrcnn_resnet50_fpn,
    "fasterrcnn_resnet50_fpn_v2": torchvision.models.detection.fasterrcnn_resnet50_fpn_v2,
    "fasterrcnn_mobilenet_v3_large_fpn": torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn,
}

# Override arch/num_classes to match the checkpoint being loaded.
# arch must be a key in _SUPPORTED_ARCHS.
# num_classes must include the background class (e.g. 3 = background + live + dead).
MODEL_CONFIG: dict[str, Any] = {
    "arch": MODEL_ARCHITECTURE,
    "num_classes": NUM_CLASSES,
}

# Cache key: absolute model path.
# Cache value: (file modified_time, device_type, loaded_model, device).
# Caches loaded model so app doesn't reload weights from disk for every run.
MODEL_CACHE: dict[str, tuple[float, str, Any, Any]] = {}


def _model_file_name_to_absolute_path(model_file_name: str) -> Path:
    """Return a validated absolute model path for model_execution.

    Requirements:
    - Input must already be absolute (frontend provides full path).
    - File must exist on disk.
    """
    expanded_path = Path(model_file_name).expanduser()
    if not expanded_path.is_absolute():
        raise ValueError(f"model_file_name must be an absolute path: {model_file_name}")
    model_path = expanded_path.resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    return model_path


def _build_model(config: dict[str, Any]) -> Any:
    """Instantiate a TorchVision Faster R-CNN model from a config dict.

    Config keys:
    - ``arch``: architecture name; must be a key in ``_SUPPORTED_ARCHS``.
    - ``num_classes``: total output classes including background.
    """
    arch = config.get("arch", "fasterrcnn_resnet50_fpn_v2")
    num_classes = config.get("num_classes", 3)
    builder = _SUPPORTED_ARCHS.get(arch)
    if builder is None:
        raise ValueError(
            f"Unsupported architecture: {arch!r}. "
            f"Supported architectures: {sorted(_SUPPORTED_ARCHS)}"
        )
    return builder(weights=None, weights_backbone=None, num_classes=num_classes)


def clear_model_cache() -> None:
    """Clear cached loaded models so future calls respect current device preference."""
    MODEL_CACHE.clear()


def _load_model(model_path: Path, preferred_compute_mode: str) -> tuple[Any, Any]:
    """Load RCNN weights from disk and return `(model, device)`.

    Supported checkpoint layouts:
    - Raw state-dict object
    - Dict containing `model_state_dict`
    - Dict containing `state_dict`
    """
    # Pick GPU when available; otherwise run on CPU.
    device = resolve_torch_device(preferred_compute_mode)

    # Load checkpoint on the target device.
    checkpoint = torch.load(str(model_path), map_location=device)

    normalized_state_dict = normalize_loaded_state_dict(checkpoint)

    model = _build_model(MODEL_CONFIG)
    try:
        model.load_state_dict(normalized_state_dict)
    except Exception as error:
        raise RuntimeError(f"Failed to load RCNN model weights from {model_path}: {error}") from error

    model = model.to(device)
    model.eval()
    return model, device


def _get_model_device(model_file_name: str, preferred_compute_mode: str) -> tuple[Any, Any]:
    """Return cached `(model, device)` and reload only when model file changed.

    The cache invalidates using file modified-time (`st_mtime`).
    Device comes from model load-time selection: GPU (`cuda`) when available,
    otherwise CPU.
    """
    model_path = _model_file_name_to_absolute_path(model_file_name)
    cache_key = str(model_path)
    modified_time = model_path.stat().st_mtime
    current_device_type = resolve_torch_device(preferred_compute_mode).type

    cached = MODEL_CACHE.get(cache_key)
    if cached is not None and cached[0] == modified_time and cached[1] == current_device_type:
        return cached[2], cached[3]

    model, device = _load_model(model_path, preferred_compute_mode)
    MODEL_CACHE[cache_key] = (modified_time, current_device_type, model, device)
    return model, device


def _run_rcnn_model_execution(model_device_tuple: tuple[Any, Any], image_path: str) -> list[dict[str, Any]]:
    """Run RCNN on one image and return standardized detection records.

    Output records are normalized to the detection table fields:
    `class_name`, `confidence_score`, and `bbox_x1..bbox_y2`.
    """
    model, device = model_device_tuple
    image = Image.open(image_path).convert("RGB")
    original_width, original_height = image.size
    tensor, replay = replay_transform_image(image)
    tensor = tensor.to(device)

    with torch.no_grad():
        prediction = model([tensor])[0]

    transformed_boxes = prediction["boxes"].detach().cpu().tolist()
    scores = prediction["scores"].detach().cpu().tolist()
    labels = prediction["labels"].detach().cpu().tolist()
    boxes = invert_replay_boxes(
        transformed_boxes,
        replay=replay,
        original_width=original_width,
        original_height=original_height,
    )

    detections: list[dict[str, Any]] = []
    for box, score, label in zip(boxes, scores, labels):
        class_name = RCNN_LABELS.get(int(label))
        # Ignore labels outside this app's live/dead mapping.
        if class_name is None:
            continue
        detections.append(
            {
                "class_name": class_name,
                "confidence_score": float(score),
                "bbox_x1": float(box[0]),
                "bbox_y1": float(box[1]),
                "bbox_x2": float(box[2]),
                "bbox_y2": float(box[3]),
            }
        )

    # Keep GPU memory stable across repeated model_execution calls.
    if device.type == "cuda":
        torch.cuda.empty_cache()

    return detections


def run_rcnn_model_execution_for_run_images(
    database_connection: sqlite3.Connection,
    run_image_ids: list[int],
    model_file_name: str,
    threshold_score: float,
    preferred_compute_mode: str,
    on_run_image_processed: Callable[[int, int], None] | None = None,
) -> None:
    """Run model_execution for selected `run_images` rows and write results to DB.

    For each `run_image_id`:
    - Load image path from DB.
    - Delete old detections for that run-image row.
    - Insert new detections from model output.
    - Recompute thresholded live/dead counts for the run-image row.

    A progress callback can be provided for frontend polling state.
    """
    if not run_image_ids:
        return

    model_device_tuple = _get_model_device(model_file_name, preferred_compute_mode)
    placeholders = ",".join(["?"] * len(run_image_ids))
    # Pull run-image rows with physical file path for model_execution.
    run_images_from_database = database_connection.execute(
        f"""
        SELECT
            run_images.id AS run_image_id,
            images.stored_path
        FROM run_images
        JOIN images ON images.id = run_images.image_id
        WHERE run_images.id IN ({placeholders})
        ORDER BY run_images.id ASC
        """,
        run_image_ids,
    ).fetchall()
    total_images_to_process = len(run_images_from_database)

    for processed_images, run_image_from_database in enumerate(run_images_from_database, start=1):
        run_image_id = int(run_image_from_database["run_image_id"])
        image_path = str(run_image_from_database["stored_path"])
        detections = _run_rcnn_model_execution(model_device_tuple, image_path)

        # Replace prior detections so reruns are deterministic per run-image row.
        database_connection.execute(
            """
            DELETE FROM detections
            WHERE run_image_id = ?
            """,
            (run_image_id,),
        )

        live_mussel_count = 0
        dead_mussel_count = 0

        for detection in detections:
            # Persist every raw detection; threshold only affects aggregate counters.
            database_connection.execute(
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
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
                """,
                (
                    run_image_id,
                    detection["class_name"],
                    detection["confidence_score"],
                    detection["bbox_x1"],
                    detection["bbox_y1"],
                    detection["bbox_x2"],
                    detection["bbox_y2"],
                ),
            )

            if detection["confidence_score"] >= threshold_score:
                if detection["class_name"] == "live":
                    live_mussel_count += 1
                elif detection["class_name"] == "dead":
                    dead_mussel_count += 1

        # Store per-image counters used by run-level aggregate queries.
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

        if on_run_image_processed is not None:
            # Frontend progress: (processed so far, total to process).
            on_run_image_processed(processed_images, total_images_to_process)
