"""FastAPI-friendly fine-tuning helpers derived from the notebook workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import random
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import torch
from torch.utils.data import ConcatDataset
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
from torch.utils.data import Subset
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

from backend.compute import resolve_torch_device
from backend.dataset_sources import create_dataset_source
from backend.dataset_sources import list_pascal_voc_samples
from backend.model_execution import _SUPPORTED_ARCHS
from backend.training_config import BATCH_SIZE
from backend.training_config import GRAD_CLIP_NORM
from backend.training_config import LEARNING_RATE
from backend.training_config import NUM_EPOCHS
from backend.training_config import NUM_WORKERS
from backend.training_config import SEED
from backend.training_config import WEIGHT_DECAY
from backend.training_config import build_training_sample
from backend.training_config import get_train_transforms
from backend.training_config import normalize_loaded_state_dict


@dataclass(slots=True)
class FineTuneConfig:
    """Inputs required to create one new fine-tuned model version."""

    parent_model_path: str
    output_model_path: str
    architecture: str
    num_classes: int
    class_mapping: dict[str, str]
    base_train_dataset: dict[str, Any]
    replay_history_images: list[dict[str, Any]]
    replay_history_detections: dict[int, list[dict[str, Any]]]
    new_replay_images: list[dict[str, Any]]
    new_replay_detections: dict[int, list[dict[str, Any]]]
    num_epochs: int = NUM_EPOCHS
    learning_rate: float = LEARNING_RATE
    weight_decay: float = WEIGHT_DECAY
    batch_size: int = BATCH_SIZE
    num_workers: int = NUM_WORKERS
    seed: int = SEED


class PascalVOCDataset(Dataset):
    """Pascal VOC dataset loaded from image/XML sample pairs."""

    def __init__(
        self,
        samples: list[tuple[Path, Path]],
        class_name_to_id: dict[str, int],
        transforms,
    ) -> None:
        self.samples = samples
        self.class_name_to_id = class_name_to_id
        self.transforms = transforms

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        image_path, label_path = self.samples[index]
        image = np.array(Image.open(image_path).convert("RGB"))
        boxes, labels = _parse_pascal_voc_xml(label_path, self.class_name_to_id)
        return build_training_sample(
            image=image,
            boxes=boxes,
            labels=labels,
            sample_index=index,
            transforms=self.transforms,
        )


class ReplayBufferSnapshotDataset(Dataset):
    """Replay-buffer dataset built from stored image paths and DB label snapshots."""

    def __init__(
        self,
        image_rows: list[dict[str, Any]],
        detections_by_image_id: dict[int, list[dict[str, Any]]],
        class_name_to_id: dict[str, int],
        transforms,
    ) -> None:
        self.image_rows = image_rows
        self.detections_by_image_id = detections_by_image_id
        self.class_name_to_id = class_name_to_id
        self.transforms = transforms

    def __len__(self) -> int:
        return len(self.image_rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        row = self.image_rows[index]
        image = np.array(Image.open(str(row["stored_path"])).convert("RGB"))
        detections = self.detections_by_image_id.get(int(row["id"]), [])
        boxes: list[list[float]] = []
        labels: list[int] = []
        for detection in detections:
            class_name = str(detection["class_name"]).strip().lower()
            class_id = self.class_name_to_id.get(class_name)
            if class_id is None:
                continue
            xmin = float(detection["bbox_x1"])
            ymin = float(detection["bbox_y1"])
            xmax = float(detection["bbox_x2"])
            ymax = float(detection["bbox_y2"])
            if xmax <= xmin or ymax <= ymin:
                continue
            boxes.append([xmin, ymin, xmax, ymax])
            labels.append(class_id)
        return build_training_sample(
            image=image,
            boxes=boxes,
            labels=labels,
            sample_index=index,
            transforms=self.transforms,
        )


def run_fine_tuning(
    config: FineTuneConfig,
    preferred_compute_mode: str = "automatic",
    progress_callback=None,
    stage_callback=None,
    should_cancel_callback=None,
) -> dict[str, Any]:
    """Train one fine-tuned checkpoint and return training metadata."""
    class_name_to_id = _build_class_name_to_id_mapping(config.class_mapping)
    if not class_name_to_id:
        raise ValueError("Fine-tuning requires a valid class mapping.")

    _set_seed(config.seed)
    _validate_fine_tune_inputs(config)

    train_transforms = get_train_transforms()
    base_dataset = _build_base_training_dataset(config.base_train_dataset, class_name_to_id, train_transforms)
    replay_history_dataset = ReplayBufferSnapshotDataset(
        image_rows=config.replay_history_images,
        detections_by_image_id=config.replay_history_detections,
        class_name_to_id=class_name_to_id,
        transforms=train_transforms,
    )
    new_data_dataset = ReplayBufferSnapshotDataset(
        image_rows=config.new_replay_images,
        detections_by_image_id=config.new_replay_detections,
        class_name_to_id=class_name_to_id,
        transforms=train_transforms,
    )
    if len(new_data_dataset) == 0:
        raise ValueError("No new replay-buffer images were selected for fine-tuning.")

    old_train_dataset = ConcatDataset([base_dataset, replay_history_dataset])
    replay_size = min(len(old_train_dataset), len(new_data_dataset))
    replay_indices = _sample_indices(len(old_train_dataset), replay_size, config.seed + 1)
    new_indices = list(range(len(new_data_dataset)))
    train_dataset = ConcatDataset([
        Subset(new_data_dataset, new_indices),
        Subset(old_train_dataset, replay_indices),
    ])
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        collate_fn=_collate_fn,
    )
    total_steps = len(train_loader) * max(1, int(config.num_epochs))
    if total_steps <= 0:
        raise ValueError("Fine-tuning could not start because the training loader is empty.")

    model, device = _load_detection_model(
        model_path=config.parent_model_path,
        architecture=config.architecture,
        num_classes=config.num_classes,
        preferred_compute_mode=preferred_compute_mode,
    )
    trainable_parameters = _configure_trainable_parameters(model)
    optimizer = torch.optim.AdamW(
        trainable_parameters,
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=int(config.num_epochs),
        eta_min=float(config.learning_rate) / 20.0,
    )

    if progress_callback is not None:
        progress_callback(0, total_steps)
    if stage_callback is not None:
        stage_callback("Fine-tuning model")

    processed_steps = 0
    epoch_losses: list[float] = []
    try:
        for epoch_number in range(1, int(config.num_epochs) + 1):
            if stage_callback is not None:
                stage_callback(f"Fine-tuning epoch {epoch_number} of {config.num_epochs}")
            average_loss, processed_steps = _train_one_epoch(
                model=model,
                loader=train_loader,
                optimizer=optimizer,
                device=device,
                epoch_number=epoch_number,
                total_epochs=int(config.num_epochs),
                processed_steps=processed_steps,
                total_steps=total_steps,
                progress_callback=progress_callback,
                should_cancel_callback=should_cancel_callback,
            )
            epoch_losses.append(average_loss)
            scheduler.step()

        if should_cancel_callback is not None and should_cancel_callback():
            raise RuntimeError("Fine-tuning cancelled by user.")

        if stage_callback is not None:
            stage_callback("Saving fine-tuned checkpoint")
        output_path = Path(config.output_model_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), str(output_path))
    except Exception:
        output_path = Path(config.output_model_path).expanduser().resolve()
        if output_path.is_file():
            output_path.unlink(missing_ok=True)
        raise

    return {
        "output_model_path": str(Path(config.output_model_path).expanduser().resolve()),
        "device": str(device),
        "num_new_samples": len(new_data_dataset),
        "num_replay_samples": replay_size,
        "total_train_samples": len(train_dataset),
        "num_epochs": int(config.num_epochs),
        "epoch_losses": epoch_losses,
    }


def _train_one_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    epoch_number: int,
    total_epochs: int,
    processed_steps: int,
    total_steps: int,
    progress_callback=None,
    should_cancel_callback=None,
) -> tuple[float, int]:
    model.train()
    running_loss = 0.0

    for batch_index, (images, targets) in enumerate(loader, start=1):
        if should_cancel_callback is not None and should_cancel_callback():
            raise RuntimeError("Fine-tuning cancelled by user.")

        device_images, device_targets = _move_batch_to_device(images, targets, device)
        loss_dict = model(device_images, device_targets)
        total_loss = sum(loss for loss in loss_dict.values())

        optimizer.zero_grad()
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP_NORM)
        optimizer.step()

        running_loss += float(total_loss.item())
        processed_steps += 1
        if progress_callback is not None:
            progress_callback(processed_steps, total_steps)

    return running_loss / max(len(loader), 1), processed_steps


def _validate_fine_tune_inputs(config: FineTuneConfig) -> None:
    parent_model_path = Path(config.parent_model_path).expanduser().resolve()
    if not parent_model_path.is_file():
        raise FileNotFoundError(f"Model checkpoint not found: {parent_model_path}")
    _create_base_training_source(config.base_train_dataset)


def _load_detection_model(
    model_path: str,
    architecture: str,
    num_classes: int,
    preferred_compute_mode: str,
) -> tuple[torch.nn.Module, torch.device]:
    builder = _SUPPORTED_ARCHS.get(architecture)
    if builder is None:
        raise ValueError(f"Unsupported architecture for fine-tuning: {architecture}")

    device = resolve_torch_device(preferred_compute_mode)
    checkpoint = torch.load(str(Path(model_path).expanduser().resolve()), map_location=device)
    state_dict = normalize_loaded_state_dict(checkpoint)

    model = builder(weights=None, weights_backbone=None)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, int(num_classes))
    model.load_state_dict(state_dict)
    model.to(device)
    return model, device


def _configure_trainable_parameters(
    model: torch.nn.Module,
) -> list[torch.nn.Parameter]:
    return [parameter for parameter in model.parameters() if parameter.requires_grad]


def _build_class_name_to_id_mapping(class_mapping: dict[str, str]) -> dict[str, int]:
    """Invert the DB class mapping into the lowercase names used by XML labels."""
    return {
        str(class_name).strip().lower(): int(class_id)
        for class_id, class_name in class_mapping.items()
    }


def _create_base_training_source(base_train_dataset: dict[str, Any]):
    """Build a dataset source from the training dataset metadata stored in the DB."""
    return create_dataset_source(
        images_dir=str(base_train_dataset.get("images_dir") or ""),
        labels_dir=str(base_train_dataset.get("labels_dir") or ""),
        zip_file_path=str(base_train_dataset.get("zip_file_path") or ""),
        split_name=str(base_train_dataset.get("split_name") or ""),
        dataset_format=str(base_train_dataset.get("dataset_format") or ""),
    )


def _build_base_training_dataset(
    base_train_dataset: dict[str, Any],
    class_name_to_id: dict[str, int],
    transforms,
) -> PascalVOCDataset:
    """Load the original training dataset that the parent model was built from."""
    base_train_source = _create_base_training_source(base_train_dataset)
    return PascalVOCDataset(
        samples=list_pascal_voc_samples(base_train_source),
        class_name_to_id=class_name_to_id,
        transforms=transforms,
    )


def _parse_pascal_voc_xml(label_path: Path, class_name_to_id: dict[str, int]) -> tuple[list[list[float]], list[int]]:
    """Parse one Pascal VOC XML file into Faster R-CNN box/label lists."""
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
        labels.append(int(class_name_to_id[class_name]))
    return boxes, labels


def _move_batch_to_device(images, targets, device: torch.device) -> tuple[list[torch.Tensor], list[dict[str, torch.Tensor]]]:
    device_images = [image.to(device) for image in images]
    device_targets = [{key: value.to(device) for key, value in target.items()} for target in targets]
    return device_images, device_targets


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _sample_indices(total_size: int, sample_size: int, seed: int) -> list[int]:
    if sample_size <= 0:
        return []
    if sample_size >= total_size:
        return list(range(total_size))
    rng = random.Random(seed)
    return rng.sample(range(total_size), sample_size)


def _collate_fn(batch):
    return tuple(zip(*batch))
