CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_file_name TEXT NOT NULL,
    model_version_id INTEGER,
    threshold_score REAL NOT NULL,
    image_count INTEGER NOT NULL DEFAULT 0,
    live_mussel_count INTEGER NOT NULL DEFAULT 0,
    dead_mussel_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    displayed_file_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    sha_256_file_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS run_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    image_id INTEGER NOT NULL,
    live_mussel_count INTEGER NOT NULL DEFAULT 0,
    dead_mussel_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    UNIQUE(run_id, image_id)
);

CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_image_id INTEGER NOT NULL,
    class_name TEXT NOT NULL CHECK (class_name IN ('live', 'dead')),
    confidence_score REAL,
    bbox_x1 REAL NOT NULL,
    bbox_y1 REAL NOT NULL,
    bbox_x2 REAL NOT NULL,
    bbox_y2 REAL NOT NULL,
    is_edited INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (run_image_id) REFERENCES run_images(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS training_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    images_dir TEXT NOT NULL,
    labels_dir TEXT NOT NULL,
    zip_file_path TEXT,
    split_name TEXT,
    dataset_format TEXT NOT NULL DEFAULT 'folder_pairs',
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    images_dir TEXT NOT NULL,
    labels_dir TEXT NOT NULL,
    zip_file_path TEXT,
    split_name TEXT,
    dataset_format TEXT NOT NULL DEFAULT 'folder_pairs',
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    version_tag TEXT NOT NULL,
    parent_version_id INTEGER,
    original_file_name TEXT NOT NULL,
    model_file_name TEXT NOT NULL UNIQUE,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    architecture TEXT NOT NULL DEFAULT 'fasterrcnn_resnet50_fpn_v2',
    num_classes INTEGER NOT NULL DEFAULT 3,
    class_mapping_json TEXT NOT NULL DEFAULT '{"1":"live","2":"dead"}',
    training_dataset_id INTEGER,
    test_dataset_id INTEGER,
    description TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (family_id) REFERENCES model_families(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_version_id) REFERENCES model_versions(id) ON DELETE SET NULL,
    FOREIGN KEY (training_dataset_id) REFERENCES training_datasets(id) ON DELETE SET NULL,
    FOREIGN KEY (test_dataset_id) REFERENCES test_datasets(id) ON DELETE SET NULL,
    UNIQUE (family_id, version_number)
);

CREATE TABLE IF NOT EXISTS model_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id INTEGER NOT NULL,
    test_dataset_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    score_threshold REAL NOT NULL DEFAULT 0.5,
    overall_metrics_json TEXT NOT NULL,
    per_class_metrics_json TEXT NOT NULL,
    summary_text TEXT,
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE CASCADE,
    FOREIGN KEY (test_dataset_id) REFERENCES test_datasets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS replay_buffer_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL UNIQUE,
    model_version_id INTEGER,
    image_count INTEGER NOT NULL DEFAULT 0,
    detection_count INTEGER NOT NULL DEFAULT 0,
    finalized_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS replay_buffer_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    replay_buffer_run_id INTEGER NOT NULL,
    model_version_id INTEGER,
    consumed_in_model_version_id INTEGER,
    consumed_at TEXT,
    run_image_id INTEGER NOT NULL,
    image_id INTEGER NOT NULL,
    displayed_file_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (replay_buffer_run_id) REFERENCES replay_buffer_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL,
    FOREIGN KEY (consumed_in_model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL,
    FOREIGN KEY (run_image_id) REFERENCES run_images(id) ON DELETE CASCADE,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    UNIQUE (replay_buffer_run_id, run_image_id)
);

CREATE TABLE IF NOT EXISTS replay_buffer_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    replay_buffer_image_id INTEGER NOT NULL,
    class_name TEXT NOT NULL CHECK (class_name IN ('live', 'dead')),
    bbox_x1 REAL NOT NULL,
    bbox_y1 REAL NOT NULL,
    bbox_x2 REAL NOT NULL,
    bbox_y2 REAL NOT NULL,
    source_detection_id INTEGER,
    confidence_score REAL,
    was_edited INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (replay_buffer_image_id) REFERENCES replay_buffer_images(id) ON DELETE CASCADE,
    FOREIGN KEY (source_detection_id) REFERENCES detections(id) ON DELETE SET NULL
);
