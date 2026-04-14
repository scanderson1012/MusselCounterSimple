"""Evaluate registered models against Pascal VOC test datasets."""

from __future__ import annotations

from pathlib import Path
import json
import xml.etree.ElementTree as ET
from typing import Any

from PIL import Image
import torch
from torch.utils.data import DataLoader, Dataset
from torchmetrics.detection.mean_ap import MeanAveragePrecision
from torchvision.ops import box_iou
import torchvision.transforms as transforms

from backend.model_execution import _get_model_device

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
EVAL_IMAGE_SIZE = 640


class PascalVOCDataset(Dataset):
    """Small detection dataset wrapper for images + Pascal VOC XML labels."""

    def __init__(self, images_dir: str, labels_dir: str, class_name_to_id: dict[str, int]):
        self.images_dir = Path(images_dir)
        self.labels_dir = Path(labels_dir)
        self.class_name_to_id = class_name_to_id
        self.transform = transforms.ToTensor()
        self.samples: list[tuple[Path, Path]] = []

        for image_path in sorted(self.images_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in VALID_IMAGE_EXTENSIONS:
                continue
            label_path = self.labels_dir / f"{image_path.stem}.xml"
            if label_path.is_file():
                self.samples.append((image_path, label_path))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, dict[str, Any]]:
        image_path, label_path = self.samples[index]
        image = Image.open(image_path).convert("RGB")
        boxes, labels = parse_pascal_voc_xml(label_path, self.class_name_to_id)
        resized_image, resized_boxes = _resize_image_and_boxes(
            image=image,
            boxes=boxes,
            target_size=EVAL_IMAGE_SIZE,
        )
        boxes_tensor = torch.as_tensor(resized_boxes, dtype=torch.float32)
        labels_tensor = torch.as_tensor(labels, dtype=torch.int64)
        area_tensor = (
            (boxes_tensor[:, 2] - boxes_tensor[:, 0]) *
            (boxes_tensor[:, 3] - boxes_tensor[:, 1])
        ) if len(boxes_tensor) > 0 else torch.zeros((0,), dtype=torch.float32)

        target = {
            "boxes": boxes_tensor,
            "labels": labels_tensor,
            "image_id": torch.tensor([index], dtype=torch.int64),
            "area": area_tensor,
            "iscrowd": torch.zeros((len(labels_tensor),), dtype=torch.int64),
        }
        return self.transform(resized_image), target


def evaluate_model_file(
    model_file_name: str,
    images_dir: str,
    labels_dir: str,
    class_mapping: dict[str, str],
    score_threshold: float = 0.5,
    progress_callback=None,
    stage_callback=None,
    should_cancel_callback=None,
) -> dict[str, Any]:
    """Run mAP + per-class metrics on one registered model file."""
    class_id_to_name = {int(key): str(value) for key, value in class_mapping.items()}
    class_name_to_id = {value: key for key, value in class_id_to_name.items()}
    dataset = PascalVOCDataset(images_dir, labels_dir, class_name_to_id)
    if len(dataset) == 0:
        raise ValueError("No Pascal VOC image/XML pairs were found in the selected test dataset")

    if stage_callback is not None:
        stage_callback("Loading model and preparing evaluation")

    loader = DataLoader(dataset, batch_size=1, shuffle=False, collate_fn=_collate_fn)
    model, device = _get_model_device(model_file_name)
    try:
        mean_average_precision = MeanAveragePrecision(
            box_format="xyxy",
            iou_type="bbox",
            class_metrics=True,
            backend="faster_coco_eval",
        ).to(device)
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Model evaluation requires the `faster-coco-eval` package. "
            "Install project requirements again, then restart the app."
        ) from error

    classwise_totals = {
        class_id: {"tp": 0, "fp": 0, "fn": 0}
        for class_id in class_id_to_name.keys()
    }

    total_batches = len(loader)
    if progress_callback is not None:
        progress_callback(0, total_batches)
    if stage_callback is not None:
        stage_callback("Evaluating test dataset")

    for batch_index, (images, targets) in enumerate(loader, start=1):
        if should_cancel_callback is not None and should_cancel_callback():
            raise RuntimeError("Evaluation cancelled by user.")
        device_images = [image.to(device) for image in images]
        with torch.no_grad():
            outputs = model(device_images)

        predictions_for_metric: list[dict[str, torch.Tensor]] = []
        targets_for_metric: list[dict[str, torch.Tensor]] = []
        for output, target in zip(outputs, targets):
            predictions_for_metric.append(
                {
                    "boxes": output["boxes"].detach().to(device),
                    "scores": output["scores"].detach().to(device),
                    "labels": output["labels"].detach().to(device),
                }
            )
            targets_for_metric.append(
                {
                    "boxes": target["boxes"].to(device),
                    "labels": target["labels"].to(device),
                }
            )
            _update_classwise_totals(
                classwise_totals,
                output=output,
                target=target,
                class_ids=list(class_id_to_name.keys()),
                score_threshold=score_threshold,
            )

        mean_average_precision.update(predictions_for_metric, targets_for_metric)
        if progress_callback is not None:
            progress_callback(batch_index, total_batches)

    if should_cancel_callback is not None and should_cancel_callback():
        raise RuntimeError("Evaluation cancelled by user.")
    if stage_callback is not None:
        stage_callback("Summarizing evaluation metrics")
    raw_results = mean_average_precision.compute()
    overall_metrics = _serialize_map_results(raw_results)
    per_class_rows = _serialize_per_class_rows(raw_results, class_id_to_name, classwise_totals)
    return {
        "overall_metrics": overall_metrics,
        "per_class_metrics": per_class_rows,
        "summary_text": _build_summary_text(overall_metrics, per_class_rows),
    }


def parse_pascal_voc_xml(label_path: Path, class_name_to_id: dict[str, int]) -> tuple[list[list[float]], list[int]]:
    boxes: list[list[float]] = []
    labels: list[int] = []
    root = ET.parse(label_path).getroot()
    for object_node in root.findall("object"):
        class_name = str(object_node.findtext("name", "")).strip().lower()
        if class_name not in class_name_to_id:
            continue

        bbox_node = object_node.find("bndbox")
        if bbox_node is None:
            continue
        xmin = float(bbox_node.findtext("xmin", "0"))
        ymin = float(bbox_node.findtext("ymin", "0"))
        xmax = float(bbox_node.findtext("xmax", "0"))
        ymax = float(bbox_node.findtext("ymax", "0"))
        if xmax <= xmin or ymax <= ymin:
            continue
        boxes.append([xmin, ymin, xmax, ymax])
        labels.append(class_name_to_id[class_name])
    return boxes, labels


def _resize_image_and_boxes(
    image: Image.Image,
    boxes: list[list[float]],
    target_size: int,
) -> tuple[Image.Image, list[list[float]]]:
    """Mirror the training notebook's eval resize to a fixed square image size."""
    original_width, original_height = image.size
    resized_image = image.resize((target_size, target_size), Image.Resampling.BILINEAR)

    if original_width <= 0 or original_height <= 0 or not boxes:
        return resized_image, boxes

    scale_x = target_size / float(original_width)
    scale_y = target_size / float(original_height)
    resized_boxes: list[list[float]] = []
    for xmin, ymin, xmax, ymax in boxes:
        resized_boxes.append(
            [
                xmin * scale_x,
                ymin * scale_y,
                xmax * scale_x,
                ymax * scale_y,
            ]
        )
    return resized_image, resized_boxes


def store_model_evaluation(
    database_connection,
    model_version_id: int,
    test_dataset_id: int,
    evaluation_result: dict[str, Any],
    score_threshold: float = 0.5,
) -> dict[str, Any]:
    cursor = database_connection.execute(
        """
        INSERT INTO model_evaluations (
            model_version_id,
            test_dataset_id,
            score_threshold,
            overall_metrics_json,
            per_class_metrics_json,
            summary_text
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            model_version_id,
            test_dataset_id,
            score_threshold,
            json.dumps(evaluation_result["overall_metrics"]),
            json.dumps(evaluation_result["per_class_metrics"]),
            evaluation_result.get("summary_text"),
        ),
    )
    evaluation_id = int(cursor.lastrowid)
    row = database_connection.execute(
        """
        SELECT
            id,
            model_version_id,
            test_dataset_id,
            created_at,
            score_threshold,
            overall_metrics_json,
            per_class_metrics_json,
            summary_text
        FROM model_evaluations
        WHERE id = ?
        """,
        (evaluation_id,),
    ).fetchone()
    evaluation_data = dict(row)
    evaluation_data["overall_metrics"] = json.loads(evaluation_data.pop("overall_metrics_json"))
    evaluation_data["per_class_metrics"] = json.loads(evaluation_data.pop("per_class_metrics_json"))
    return evaluation_data


def _collate_fn(batch):
    return tuple(zip(*batch))


def _update_classwise_totals(
    classwise_totals: dict[int, dict[str, int]],
    output: dict[str, torch.Tensor],
    target: dict[str, torch.Tensor],
    class_ids: list[int],
    score_threshold: float,
) -> None:
    pred_boxes = output["boxes"].detach().cpu()
    pred_scores = output["scores"].detach().cpu()
    pred_labels = output["labels"].detach().cpu()
    keep_mask = pred_scores >= score_threshold
    pred_boxes = pred_boxes[keep_mask]
    pred_labels = pred_labels[keep_mask]

    gt_boxes = target["boxes"].cpu()
    gt_labels = target["labels"].cpu()

    for class_id in class_ids:
        class_pred_boxes = pred_boxes[pred_labels == class_id]
        class_gt_boxes = gt_boxes[gt_labels == class_id]
        if len(class_pred_boxes) == 0 and len(class_gt_boxes) == 0:
            continue
        if len(class_pred_boxes) == 0:
            classwise_totals[class_id]["fn"] += len(class_gt_boxes)
            continue
        if len(class_gt_boxes) == 0:
            classwise_totals[class_id]["fp"] += len(class_pred_boxes)
            continue

        ious = box_iou(class_pred_boxes, class_gt_boxes)
        matched_predictions: set[int] = set()
        matched_ground_truth: set[int] = set()

        candidates: list[tuple[float, int, int]] = []
        for pred_index in range(ious.shape[0]):
            for gt_index in range(ious.shape[1]):
                iou_value = float(ious[pred_index, gt_index].item())
                if iou_value >= 0.5:
                    candidates.append((iou_value, pred_index, gt_index))
        candidates.sort(reverse=True, key=lambda row: row[0])

        for _, pred_index, gt_index in candidates:
            if pred_index in matched_predictions or gt_index in matched_ground_truth:
                continue
            matched_predictions.add(pred_index)
            matched_ground_truth.add(gt_index)

        classwise_totals[class_id]["tp"] += len(matched_predictions)
        classwise_totals[class_id]["fp"] += len(class_pred_boxes) - len(matched_predictions)
        classwise_totals[class_id]["fn"] += len(class_gt_boxes) - len(matched_ground_truth)


def _serialize_map_results(raw_results: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in raw_results.items():
        if torch.is_tensor(value):
            if value.numel() == 1:
                serialized[key] = float(value.item())
            else:
                serialized[key] = [float(item) for item in value.detach().cpu().tolist()]
        else:
            serialized[key] = value
    return serialized


def _serialize_per_class_rows(
    raw_results: dict[str, Any],
    class_id_to_name: dict[int, str],
    classwise_totals: dict[int, dict[str, int]],
) -> list[dict[str, Any]]:
    map_per_class = _to_class_metric_lookup(raw_results.get("classes"), raw_results.get("map_per_class"))
    mar_per_class = _to_class_metric_lookup(raw_results.get("classes"), raw_results.get("mar_100_per_class"))

    rows: list[dict[str, Any]] = []
    for class_id, class_name in class_id_to_name.items():
        stats = classwise_totals[class_id]
        tp = int(stats["tp"])
        fp = int(stats["fp"])
        fn = int(stats["fn"])
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        rows.append(
            {
                "class_id": class_id,
                "class_name": class_name,
                "map": float(map_per_class.get(class_id, 0.0)),
                "mar_100": float(mar_per_class.get(class_id, 0.0)),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    return rows


def _to_class_metric_lookup(class_ids_tensor, values_tensor) -> dict[int, float]:
    if class_ids_tensor is None or values_tensor is None:
        return {}
    class_ids = [int(value) for value in class_ids_tensor.detach().cpu().tolist()]
    values = [float(value) for value in values_tensor.detach().cpu().tolist()]
    return dict(zip(class_ids, values))


def _build_summary_text(overall_metrics: dict[str, Any], per_class_rows: list[dict[str, Any]]) -> str:
    per_class_lookup = {
        str(row.get("class_name") or "").strip().lower(): row
        for row in per_class_rows
    }
    dead_row = per_class_lookup.get("dead", {})
    live_row = per_class_lookup.get("live", {})
    summary_lines = [
        f"mAP={overall_metrics.get('map', 0):.4f}",
        f"mAP@50={overall_metrics.get('map_50', 0):.4f}",
        f"mAP@75={overall_metrics.get('map_75', 0):.4f}",
        f"Dead Precision={dead_row.get('precision', 0):.4f}",
        f"Dead Recall={dead_row.get('recall', 0):.4f}",
        f"Alive Precision={live_row.get('precision', 0):.4f}",
        f"Alive Recall={live_row.get('recall', 0):.4f}",
    ]
    return " | ".join(summary_lines)
