r"""Lightweight backend smoke checks for core app workflows.

Run with:
    .\.venv\Scripts\python.exe scripts\smoke_check.py
"""

from __future__ import annotations

from pathlib import Path
import importlib
import os
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    temp_root = (PROJECT_ROOT / ".tmp_smoke").resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    root = (temp_root / "workspace").resolve()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    try:
        app_data_dir = root / "app_data"
        train_images_dir = root / "train" / "images"
        train_labels_dir = root / "train" / "labels"
        test_images_dir = root / "test" / "images"
        test_labels_dir = root / "test" / "labels"
        replay_source_dir = root / "replay_inputs"
        dummy_model_path = root / "dummy_model.pth"

        for directory in [
            app_data_dir,
            train_images_dir,
            train_labels_dir,
            test_images_dir,
            test_labels_dir,
            replay_source_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        _write_sample_image_and_xml(train_images_dir, train_labels_dir, "train_001")
        _write_sample_image_and_xml(test_images_dir, test_labels_dir, "test_001")
        _write_sample_image(replay_source_dir / "replay_001.jpg", color=(180, 180, 180))
        _write_sample_image(replay_source_dir / "replay_002.jpg", color=(120, 170, 210))
        dummy_model_path.write_bytes(b"not-a-real-checkpoint")

        os.environ["MUSSEL_APP_DATA_DIR"] = str(app_data_dir)
        os.environ["MUSSEL_BASELINE_MODEL_PATH"] = str(root / "missing_baseline.pth")

        init_db = _reload("backend.init_db")
        database = _reload("backend.database")
        image_ingest = _reload("backend.image_ingest")

        init_db.init_db()

        with database.get_database_connection() as conn:
            conn.row_factory = sqlite3.Row

            _check_settings(conn)

            training_dataset = database.create_dataset_record(
                conn,
                "training_datasets",
                name="smoke_train",
                images_dir=str(train_images_dir),
                labels_dir=str(train_labels_dir),
                description="Smoke test training dataset",
            )
            test_dataset = database.create_dataset_record(
                conn,
                "test_datasets",
                name="smoke_test",
                images_dir=str(test_images_dir),
                labels_dir=str(test_labels_dir),
                description="Smoke test test dataset",
            )
            version = database.register_baseline_model(
                database_connection=conn,
                source_model_path=str(dummy_model_path),
                family_name="smoke_model",
                training_dataset_id=int(training_dataset["id"]),
                test_dataset_id=int(test_dataset["id"]),
                description="Smoke model",
            )
            conn.commit()

            registry = database.list_model_registry(conn)
            assert len(registry) == 1, "Expected one model family after baseline registration"
            assert registry[0]["versions"][0]["is_latest_version"] is True

            image_one = image_ingest.ingest_image_into_database(
                conn,
                image_path=str(replay_source_dir / "replay_001.jpg"),
            )
            image_two = image_ingest.ingest_image_into_database(
                conn,
                image_path=str(replay_source_dir / "replay_002.jpg"),
            )
            run_id = database.create_run(
                database_connection=conn,
                model_file_name=str(version["model_file_name"]),
                threshold_score=0.5,
                model_version_id=int(version["id"]),
            )
            run_image_id_one, _ = database.link_image_to_run(conn, run_id, int(image_one["image_id"]))
            run_image_id_two, _ = database.link_image_to_run(conn, run_id, int(image_two["image_id"]))
            _insert_detection(conn, run_image_id_one, "live")
            _insert_detection(conn, run_image_id_two, "dead")
            database.recalculate_run_image_mussel_counts_from_detections(conn, run_image_id_one, 0.5)
            database.recalculate_run_image_mussel_counts_from_detections(conn, run_image_id_two, 0.5)
            database.update_run_mussel_count(conn, run_id)

            replay_summary = database.finalize_run_into_replay_buffer(conn, run_id)
            conn.commit()
            assert int(replay_summary["image_count"]) == 2, "Expected two images in replay buffer"
            pending_counts = database.list_replay_buffer_counts_by_model(conn)
            assert int(pending_counts[int(version["id"])]["image_count"]) == 2

            pending_images = database.list_pending_replay_buffer_images_for_model(conn, int(version["id"]))
            assert len(pending_images) == 2, "Expected two pending replay images"
            next_version_number = database.get_next_version_number_for_family(conn, int(version["family_id"]))
            next_model_path = database.build_model_file_path_for_version(
                family_name=str(version["family_name"]),
                version_number=int(next_version_number),
                original_file_name=str(version["original_file_name"]),
            )
            shutil.copy2(dummy_model_path, next_model_path)
            version_two = database.register_finetuned_model_version(
                database_connection=conn,
                parent_version_id=int(version["id"]),
                model_file_path=str(next_model_path),
            )
            database.mark_replay_buffer_images_consumed(
                conn,
                [int(pending_images[0]["id"])],
                int(version_two["id"]),
            )
            conn.commit()

            locked = database.is_run_image_locked_for_editing(conn, int(pending_images[0]["run_image_id"]))
            assert locked is True, "Consumed replay image should be locked"
            pending_counts_after_consume = database.list_replay_buffer_counts_by_model(conn)
            assert int(pending_counts_after_consume[int(version["id"])]["image_count"]) == 1

            deleted = database.delete_model_version(conn, int(version_two["id"]))
            assert deleted is True, "Expected fine-tuned version deletion to succeed"
            conn.commit()
            restored_pending_images = database.list_pending_replay_buffer_images_for_model(conn, int(version["id"]))
            assert len(restored_pending_images) == 2, "Deleting v2 should restore consumed replay image to v1"

        print("Smoke checks passed.")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _reload(module_name: str):
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def _check_settings(conn: sqlite3.Connection) -> None:
    app_settings = _reload("backend.app_settings")
    settings = app_settings.get_app_settings(conn)
    assert int(settings["fine_tune_min_new_images"]) == 10
    assert int(settings["fine_tune_num_epochs"]) == 5
    updated = app_settings.update_app_settings(
        conn,
        {
            "fine_tune_min_new_images": 12,
            "fine_tune_num_epochs": 7,
        },
    )
    assert int(updated["fine_tune_min_new_images"]) == 12
    assert int(updated["fine_tune_num_epochs"]) == 7


def _insert_detection(conn: sqlite3.Connection, run_image_id: int, class_name: str) -> None:
    _reload("backend.database").create_detection_for_run_image(
        database_connection=conn,
        run_image_id=run_image_id,
        class_name=class_name,
        bbox_x1=4,
        bbox_y1=4,
        bbox_x2=40,
        bbox_y2=40,
        confidence_score=0.9,
    )


def _write_sample_image(image_path: Path, color=(180, 180, 180)) -> None:
    image = Image.new("RGB", (64, 64), color=color)
    image.save(image_path)


def _write_sample_image_and_xml(images_dir: Path, labels_dir: Path, stem: str) -> None:
    image_path = images_dir / f"{stem}.jpg"
    xml_path = labels_dir / f"{stem}.xml"
    _write_sample_image(image_path, color=(180, 180, 180))

    annotation = ET.Element("annotation")
    obj = ET.SubElement(annotation, "object")
    ET.SubElement(obj, "name").text = "live"
    bbox = ET.SubElement(obj, "bndbox")
    ET.SubElement(bbox, "xmin").text = "5"
    ET.SubElement(bbox, "ymin").text = "5"
    ET.SubElement(bbox, "xmax").text = "30"
    ET.SubElement(bbox, "ymax").text = "30"
    tree = ET.ElementTree(annotation)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    raise SystemExit(main())
