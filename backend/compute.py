"""Helpers for compute-mode selection and GPU capability reporting."""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
from typing import Any

import torch


COMPUTE_MODE_AUTOMATIC = "automatic"
COMPUTE_MODE_CPU_ONLY = "cpu_only"
COMPUTE_MODE_GPU_IF_AVAILABLE = "gpu_if_available"
VALID_COMPUTE_MODES = {
    COMPUTE_MODE_AUTOMATIC,
    COMPUTE_MODE_CPU_ONLY,
    COMPUTE_MODE_GPU_IF_AVAILABLE,
}


@dataclass(slots=True)
class ComputeStatus:
    preferred_mode: str
    effective_device: str
    backend_runtime_variant: str
    torch_cuda_available: bool
    torch_version: str
    torch_cuda_version: str | None
    compatible_gpu_detected: bool
    detected_gpu_name: str | None
    gpu_runtime_ready: bool
    optional_gpu_runtime_installed: bool
    gpu_upgrade_available: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_mode": self.preferred_mode,
            "effective_device": self.effective_device,
            "backend_runtime_variant": self.backend_runtime_variant,
            "torch_cuda_available": self.torch_cuda_available,
            "torch_version": self.torch_version,
            "torch_cuda_version": self.torch_cuda_version,
            "compatible_gpu_detected": self.compatible_gpu_detected,
            "detected_gpu_name": self.detected_gpu_name,
            "gpu_runtime_ready": self.gpu_runtime_ready,
            "optional_gpu_runtime_installed": self.optional_gpu_runtime_installed,
            "gpu_upgrade_available": self.gpu_upgrade_available,
            "can_offer_gpu_upgrade": self.gpu_upgrade_available,
        }


def normalize_compute_mode(raw_value: object, default_value: str = COMPUTE_MODE_AUTOMATIC) -> str:
    normalized_value = str(raw_value or "").strip().lower()
    if normalized_value in VALID_COMPUTE_MODES:
        return normalized_value
    return default_value


def parse_bool_setting(raw_value: object, default_value: bool = False) -> bool:
    normalized_value = str(raw_value or "").strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    return bool(default_value)


def resolve_torch_device(preferred_mode: str) -> torch.device:
    normalized_mode = normalize_compute_mode(preferred_mode)
    if normalized_mode == COMPUTE_MODE_CPU_ONLY:
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def get_compute_status(preferred_mode: str) -> ComputeStatus:
    normalized_mode = normalize_compute_mode(preferred_mode)
    detected_gpu_name = _detect_compatible_gpu_name()
    torch_cuda_available = bool(torch.cuda.is_available())
    effective_device = resolve_torch_device(normalized_mode).type
    backend_runtime_variant = _get_backend_runtime_variant()
    optional_gpu_runtime_installed = parse_bool_setting(
        os.getenv("MUSSEL_OPTIONAL_GPU_RUNTIME_INSTALLED", "0"),
        False,
    )
    gpu_upgrade_available = (
        bool(detected_gpu_name)
        and optional_gpu_runtime_installed
        and backend_runtime_variant != "gpu"
    )
    return ComputeStatus(
        preferred_mode=normalized_mode,
        effective_device=effective_device,
        backend_runtime_variant=backend_runtime_variant,
        torch_cuda_available=torch_cuda_available,
        torch_version=str(torch.__version__),
        torch_cuda_version=torch.version.cuda,
        compatible_gpu_detected=bool(detected_gpu_name),
        detected_gpu_name=detected_gpu_name,
        gpu_runtime_ready=torch_cuda_available,
        optional_gpu_runtime_installed=optional_gpu_runtime_installed,
        gpu_upgrade_available=gpu_upgrade_available,
    )


def _detect_compatible_gpu_name() -> str | None:
    """Return the first detected NVIDIA GPU name when `nvidia-smi` is available."""
    nvidia_smi_path = shutil.which("nvidia-smi")
    if not nvidia_smi_path:
        return None

    try:
        result = subprocess.run(
            [nvidia_smi_path, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    gpu_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return gpu_names[0] if gpu_names else None


def _get_backend_runtime_variant() -> str:
    runtime_variant = str(os.getenv("MUSSEL_BACKEND_RUNTIME_VARIANT", "cpu")).strip().lower()
    return runtime_variant if runtime_variant in {"cpu", "gpu"} else "cpu"
