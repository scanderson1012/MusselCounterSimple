"""Helpers for storing simple application settings in SQLite."""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.compute import COMPUTE_MODE_AUTOMATIC
from backend.compute import normalize_compute_mode
from backend.compute import parse_bool_setting
from backend.init_db import DEFAULT_APP_SETTINGS


def get_app_settings(database_connection: sqlite3.Connection) -> dict[str, Any]:
    """Return validated application settings with defaults applied."""
    rows = database_connection.execute(
        """
        SELECT setting_key, setting_value
        FROM app_settings
        """
    ).fetchall()
    raw_settings = {str(row["setting_key"]): str(row["setting_value"]) for row in rows}
    merged = {**DEFAULT_APP_SETTINGS, **raw_settings}
    return {
        "fine_tune_min_new_images": _parse_positive_int(merged.get("fine_tune_min_new_images"), 25),
        "fine_tune_num_epochs": _parse_positive_int(merged.get("fine_tune_num_epochs"), 10),
        "compute_mode": normalize_compute_mode(merged.get("compute_mode"), COMPUTE_MODE_AUTOMATIC),
        "gpu_upgrade_prompt_seen": parse_bool_setting(merged.get("gpu_upgrade_prompt_seen"), False),
    }


def update_app_settings(database_connection: sqlite3.Connection, settings: dict[str, Any]) -> dict[str, Any]:
    """Persist supported settings and return the validated current values."""
    current_settings = get_app_settings(database_connection)
    validated_settings = {
        "fine_tune_min_new_images": _parse_positive_int(
            settings.get("fine_tune_min_new_images", current_settings["fine_tune_min_new_images"]),
            25,
        ),
        "fine_tune_num_epochs": _parse_positive_int(
            settings.get("fine_tune_num_epochs", current_settings["fine_tune_num_epochs"]),
            10,
        ),
        "compute_mode": normalize_compute_mode(
            settings.get("compute_mode", current_settings["compute_mode"]),
            COMPUTE_MODE_AUTOMATIC,
        ),
        "gpu_upgrade_prompt_seen": parse_bool_setting(
            settings.get("gpu_upgrade_prompt_seen", current_settings["gpu_upgrade_prompt_seen"]),
            False,
        ),
    }
    for setting_key, setting_value in validated_settings.items():
        database_connection.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = excluded.setting_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (setting_key, "1" if isinstance(setting_value, bool) and setting_value else "0" if isinstance(setting_value, bool) else str(setting_value)),
        )
    return get_app_settings(database_connection)


def _parse_positive_int(raw_value: object, default_value: int) -> int:
    try:
        parsed_value = int(raw_value)
    except (TypeError, ValueError):
        parsed_value = default_value
    return max(1, parsed_value)
