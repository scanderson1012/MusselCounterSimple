"""Compatibility exports for split database modules."""

from backend.db.connection import get_database_connection
from backend.db.detections import get_run_info_from_detection_id
from backend.db.detections import recalculate_run_mussel_counts_from_detections
from backend.db.detections import recalculate_run_image_mussel_counts_from_detections
from backend.db.detections import update_detection_fields
from backend.db.reads import get_image_file_metadata_from_database
from backend.db.reads import get_run_from_database
from backend.db.reads import list_runs_from_database
from backend.db.runs import create_run
from backend.db.runs import get_model_name_from_run_id
from backend.db.runs import link_image_to_run
from backend.db.runs import list_run_image_ids
from backend.db.runs import unlink_image_from_run
from backend.db.runs import run_exists
from backend.db.runs import update_run_mussel_count
from backend.db.runs import update_this_runs_model
from backend.db.runs import update_run_threshold

__all__ = [
    "create_run",
    "get_database_connection",
    "get_image_file_metadata_from_database",
    "get_run_info_from_detection_id",
    "get_run_from_database",
    "get_model_name_from_run_id",
    "link_image_to_run",
    "list_run_image_ids",
    "list_runs_from_database",
    "recalculate_run_mussel_counts_from_detections",
    "recalculate_run_image_mussel_counts_from_detections",
    "run_exists",
    "update_detection_fields",
    "update_run_mussel_count",
    "unlink_image_from_run",
    "update_this_runs_model",
    "update_run_threshold",
]
