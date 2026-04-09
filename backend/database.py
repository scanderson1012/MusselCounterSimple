"""Compatibility exports for split database modules."""

from backend.db.connection import get_database_connection
from backend.db.detections import get_run_info_from_detection_id
from backend.db.detections import recalculate_run_mussel_counts_from_detections
from backend.db.detections import recalculate_run_image_mussel_counts_from_detections
from backend.db.detections import create_detection_for_run_image
from backend.db.detections import update_detection_fields
from backend.db.reads import get_image_file_metadata_from_database
from backend.db.reads import get_run_from_database
from backend.db.reads import list_runs_from_database
from backend.db.runs import create_run
from backend.db.runs import get_model_name_from_run_id
from backend.db.runs import get_model_version_id_from_run_id
from backend.db.runs import link_image_to_run
from backend.db.runs import list_run_image_ids
from backend.db.runs import unlink_image_from_run
from backend.db.runs import run_exists
from backend.db.runs import update_run_mussel_count
from backend.db.runs import update_this_runs_model
from backend.db.runs import update_run_threshold
from backend.model_registry import create_dataset_record
from backend.model_registry import delete_model_version
from backend.model_registry import get_model_file_name_for_run
from backend.model_registry import get_model_version_by_id
from backend.model_registry import list_model_options
from backend.model_registry import list_model_registry
from backend.model_registry import list_test_datasets
from backend.model_registry import list_training_datasets
from backend.model_registry import register_baseline_model
from backend.replay_buffer import finalize_run_into_replay_buffer
from backend.replay_buffer import get_replay_buffer_summary_for_run
from backend.replay_buffer import list_replay_buffer_counts_by_model
from backend.replay_buffer import remove_replay_buffer_entry_for_run_image

__all__ = [
    "create_run",
    "create_dataset_record",
    "delete_model_version",
    "create_detection_for_run_image",
    "finalize_run_into_replay_buffer",
    "get_database_connection",
    "get_image_file_metadata_from_database",
    "get_model_file_name_for_run",
    "get_run_info_from_detection_id",
    "get_replay_buffer_summary_for_run",
    "get_run_from_database",
    "get_model_name_from_run_id",
    "get_model_version_id_from_run_id",
    "get_model_version_by_id",
    "link_image_to_run",
    "list_model_options",
    "list_model_registry",
    "list_replay_buffer_counts_by_model",
    "remove_replay_buffer_entry_for_run_image",
    "list_run_image_ids",
    "list_runs_from_database",
    "list_test_datasets",
    "list_training_datasets",
    "recalculate_run_mussel_counts_from_detections",
    "recalculate_run_image_mussel_counts_from_detections",
    "register_baseline_model",
    "run_exists",
    "update_detection_fields",
    "update_run_mussel_count",
    "unlink_image_from_run",
    "update_this_runs_model",
    "update_run_threshold",
]
