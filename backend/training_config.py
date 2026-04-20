"""Shared Faster R-CNN training-compatible constants and transforms."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import albumentations as A
import numpy as np
import torch
from albumentations.pytorch import ToTensorV2
from PIL import Image

MODEL_ARCHITECTURE = "fasterrcnn_resnet50_fpn_v2"
NUM_CLASSES = 3
CLASS_NAME_TO_ID = {
    "live": 1,
    "dead": 2,
}
CLASS_ID_TO_NAME = {
    1: "live",
    2: "dead",
}
DEFAULT_CLASS_MAPPING = {
    "1": "live",
    "2": "dead",
}
SEED = 42
BATCH_SIZE = 8
NUM_WORKERS = 0
NUM_EPOCHS = 10
LEARNING_RATE = 1e-4
WEIGHT_DECAY = 5e-4
GRAD_CLIP_NORM = 5.0
IMAGE_SIZE = 896
TRAIN_AFFINE_P = 0.25
TRAIN_BLUR_P = 0.10
TRAIN_BRIGHTNESS_P = 0.30
DEFAULT_EVAL_SCORE_THRESHOLD = 0.25
PADDING_FILL = (114, 114, 114)
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def get_train_transforms() -> A.Compose:
    return A.Compose(
        [
            A.LongestMaxSize(max_size=IMAGE_SIZE),
            A.PadIfNeeded(
                min_height=IMAGE_SIZE,
                min_width=IMAGE_SIZE,
                border_mode=0,
                fill=PADDING_FILL,
            ),
            A.HorizontalFlip(p=0.5),
            A.Affine(
                scale=(0.90, 1.10),
                translate_percent=(-0.05, 0.05),
                rotate=(-12, 12),
                shear=(-5, 5),
                border_mode=0,
                fill=PADDING_FILL,
                p=TRAIN_AFFINE_P,
            ),
            A.OneOf(
                [
                    A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15),
                    A.RandomGamma(gamma_limit=(85, 115)),
                    A.CLAHE(clip_limit=2.0, tile_grid_size=(8, 8)),
                ],
                p=TRAIN_BRIGHTNESS_P,
            ),
            A.OneOf(
                [
                    A.GaussNoise(std_range=(0.01, 0.04)),
                    A.MotionBlur(blur_limit=3),
                    A.MedianBlur(blur_limit=3),
                ],
                p=TRAIN_BLUR_P,
            ),
            ToTensorV2(),
        ],
        bbox_params=A.BboxParams(
            format="pascal_voc",
            label_fields=["labels"],
            min_visibility=0.25,
        ),
    )


def get_eval_transforms() -> A.Compose:
    return A.Compose(
        [
            A.LongestMaxSize(max_size=IMAGE_SIZE),
            A.PadIfNeeded(
                min_height=IMAGE_SIZE,
                min_width=IMAGE_SIZE,
                border_mode=0,
                fill=PADDING_FILL,
            ),
            ToTensorV2(),
        ],
        bbox_params=A.BboxParams(
            format="pascal_voc",
            label_fields=["labels"],
            min_visibility=0.0,
        ),
    )


def get_inference_replay_transforms() -> A.ReplayCompose:
    return A.ReplayCompose(
        [
            A.LongestMaxSize(max_size=IMAGE_SIZE),
            A.PadIfNeeded(
                min_height=IMAGE_SIZE,
                min_width=IMAGE_SIZE,
                border_mode=0,
                fill=PADDING_FILL,
            ),
            ToTensorV2(),
        ]
    )


def build_training_sample(
    image: np.ndarray,
    boxes: list[list[float]],
    labels: list[int],
    sample_index: int,
    transforms: A.Compose | None,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    boxes_np = np.array(boxes, dtype=np.float32) if boxes else np.zeros((0, 4), dtype=np.float32)
    labels_np = np.array(labels, dtype=np.int64) if labels else np.zeros((0,), dtype=np.int64)

    if transforms is not None:
        transformed = transforms(
            image=image,
            bboxes=boxes_np.tolist(),
            labels=labels_np.tolist(),
        )
        image_tensor = transformed["image"]
        boxes_np = (
            np.array(transformed["bboxes"], dtype=np.float32)
            if transformed["bboxes"]
            else np.zeros((0, 4), dtype=np.float32)
        )
        labels_np = (
            np.array(transformed["labels"], dtype=np.int64)
            if transformed["labels"]
            else np.zeros((0,), dtype=np.int64)
        )
    else:
        image_tensor = ToTensorV2()(image=image)["image"]

    image_tensor = image_tensor.float()
    if image_tensor.numel() > 0 and float(image_tensor.max()) > 1.0:
        image_tensor = image_tensor / 255.0

    boxes_tensor = torch.as_tensor(boxes_np, dtype=torch.float32)
    labels_tensor = torch.as_tensor(labels_np, dtype=torch.int64)
    area_tensor = (
        (boxes_tensor[:, 2] - boxes_tensor[:, 0]) *
        (boxes_tensor[:, 3] - boxes_tensor[:, 1])
    ) if len(boxes_tensor) > 0 else torch.zeros((0,), dtype=torch.float32)
    target = {
        "boxes": boxes_tensor,
        "labels": labels_tensor,
        "image_id": torch.tensor([sample_index], dtype=torch.int64),
        "area": area_tensor,
        "iscrowd": torch.zeros((len(labels_tensor),), dtype=torch.int64),
    }
    return image_tensor, target


def normalize_loaded_state_dict(checkpoint: Any) -> OrderedDict[str, Any]:
    if isinstance(checkpoint, dict):
        if "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        else:
            state_dict = checkpoint
    else:
        state_dict = checkpoint

    if not isinstance(state_dict, (dict, OrderedDict)):
        raise RuntimeError("Expected checkpoint to contain model weights state_dict.")

    normalized_state_dict: OrderedDict[str, Any] = OrderedDict()
    for key, value in state_dict.items():
        normalized_state_dict[str(key).removeprefix("module.")] = value
    return normalized_state_dict


def replay_transform_image(image: Image.Image) -> tuple[torch.Tensor, dict[str, Any]]:
    image_array = np.array(image.convert("RGB"))
    transformed = get_inference_replay_transforms()(image=image_array)
    image_tensor = transformed["image"].float()
    if image_tensor.numel() > 0 and float(image_tensor.max()) > 1.0:
        image_tensor = image_tensor / 255.0
    return image_tensor, transformed["replay"]


def invert_replay_boxes(
    boxes: list[list[float]],
    replay: dict[str, Any],
    original_width: int,
    original_height: int,
) -> list[list[float]]:
    if not boxes:
        return []

    scale = 1.0
    pad_left = 0.0
    pad_top = 0.0
    for transform in replay.get("transforms", []):
        class_name = str(transform.get("__class_fullname__", ""))
        params = transform.get("params") or {}
        if class_name.endswith("LongestMaxSize"):
            scale = float(params.get("scale") or 1.0)
        elif class_name.endswith("PadIfNeeded"):
            pad_left = float(params.get("pad_left") or 0.0)
            pad_top = float(params.get("pad_top") or 0.0)

    restored_boxes: list[list[float]] = []
    for xmin, ymin, xmax, ymax in boxes:
        restored_box = [
            max(0.0, min(float(original_width), (float(xmin) - pad_left) / max(scale, 1e-8))),
            max(0.0, min(float(original_height), (float(ymin) - pad_top) / max(scale, 1e-8))),
            max(0.0, min(float(original_width), (float(xmax) - pad_left) / max(scale, 1e-8))),
            max(0.0, min(float(original_height), (float(ymax) - pad_top) / max(scale, 1e-8))),
        ]
        if restored_box[2] > restored_box[0] and restored_box[3] > restored_box[1]:
            restored_boxes.append(restored_box)
    return restored_boxes
