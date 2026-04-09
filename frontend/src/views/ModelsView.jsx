/**
 * Models registry page: dataset registration plus model family/version browsing.
 */
function ModelsView({
  visible,
  trainingDatasets,
  testDatasets,
  modelFamilies,
  modelForm,
  datasetForms,
  onUpdateDatasetForm,
  onCreateTrainingDataset,
  onCreateTestDataset,
  onUpdateModelForm,
  onRegisterModel,
  onDeleteModelVersion,
}) {
  return (
    <section id="models-view" className={`view${visible ? "" : " hidden"}`}>
      <div className="run-header">
        <h1>Models</h1>
        <p className="run-meta-text">
          Register baseline models, connect them to datasets, and inspect version performance.
        </p>
      </div>

      <div className="panel models-help-panel">
        <h3>What To Upload</h3>
        <p className="helper">
          Training dataset path: paste the full path to the folder that contains the training images.
        </p>
        <p className="helper">
          Training labels path: paste the full path to the folder that contains the Pascal VOC XML files for those same training images.
        </p>
        <p className="helper">
          Test dataset path: paste the full path to the folder that contains the test images used for evaluation.
        </p>
        <p className="helper">
          Test labels path: paste the full path to the folder that contains the Pascal VOC XML files for those same test images.
        </p>
        <p className="helper">
          Baseline model file path: paste the full path to a `.pth` or `.pt` checkpoint file. The app will copy it into managed storage as version `v1`.
        </p>
        <p className="helper">
          Expected structure: matching file stems such as `IMG0001.jpg` and `IMG0001.xml`.
        </p>
      </div>

      <div className="models-layout">
        <div className="panel">
          <h3>Register Training Dataset</h3>
          <p className="helper">
            Please upload training set path information by entering the full images-folder path and the full Pascal VOC labels-folder path.
          </p>
          <div className="field">
            <label htmlFor="training-dataset-name">Name</label>
            <input
              id="training-dataset-name"
              type="text"
              placeholder="Example: species_a_train"
              value={datasetForms.training.name}
              onChange={(event) => onUpdateDatasetForm("training", "name", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="training-images-dir">Training Images Folder Path</label>
            <input
              id="training-images-dir"
              type="text"
              placeholder="Please upload training set path to the images folder"
              value={datasetForms.training.images_dir}
              onChange={(event) => onUpdateDatasetForm("training", "images_dir", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="training-labels-dir">Training Labels Folder Path</label>
            <input
              id="training-labels-dir"
              type="text"
              placeholder="Please upload training labels path to the Pascal VOC XML folder"
              value={datasetForms.training.labels_dir}
              onChange={(event) => onUpdateDatasetForm("training", "labels_dir", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="training-description">Description</label>
            <textarea
              id="training-description"
              rows="3"
              value={datasetForms.training.description}
              onChange={(event) => onUpdateDatasetForm("training", "description", event.target.value)}
            />
          </div>
          <button className="primary" onClick={onCreateTrainingDataset}>Save Training Dataset</button>
        </div>

        <div className="panel">
          <h3>Register Test Dataset</h3>
          <p className="helper">
            Please upload testing set path information by entering the full images-folder path and the full Pascal VOC labels-folder path.
          </p>
          <div className="field">
            <label htmlFor="test-dataset-name">Name</label>
            <input
              id="test-dataset-name"
              type="text"
              placeholder="Example: species_a_test"
              value={datasetForms.test.name}
              onChange={(event) => onUpdateDatasetForm("test", "name", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="test-images-dir">Test Images Folder Path</label>
            <input
              id="test-images-dir"
              type="text"
              placeholder="Please upload testing set path to the images folder"
              value={datasetForms.test.images_dir}
              onChange={(event) => onUpdateDatasetForm("test", "images_dir", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="test-labels-dir">Test Labels Folder Path</label>
            <input
              id="test-labels-dir"
              type="text"
              placeholder="Please upload testing labels path to the Pascal VOC XML folder"
              value={datasetForms.test.labels_dir}
              onChange={(event) => onUpdateDatasetForm("test", "labels_dir", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="test-description">Description</label>
            <textarea
              id="test-description"
              rows="3"
              value={datasetForms.test.description}
              onChange={(event) => onUpdateDatasetForm("test", "description", event.target.value)}
            />
          </div>
          <button className="primary" onClick={onCreateTestDataset}>Save Test Dataset</button>
        </div>
      </div>

      <div className="panel models-register-panel">
        <h3>Register Baseline Model</h3>
        <p className="helper">
          Please upload the baseline model file path, then choose the training dataset and testing dataset linked to that model.
        </p>
        <div className="models-register-grid">
          <div className="field">
            <label htmlFor="model-source-path">Model File Path</label>
            <input
              id="model-source-path"
              type="text"
              placeholder="Please upload baseline model path to the .pth or .pt file"
              value={modelForm.source_model_path}
              onChange={(event) => onUpdateModelForm("source_model_path", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="model-family-name">Base Model Name</label>
            <input
              id="model-family-name"
              type="text"
              placeholder="Example: my_model"
              value={modelForm.family_name}
              onChange={(event) => onUpdateModelForm("family_name", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="training-dataset-select">Training Dataset</label>
            <select
              id="training-dataset-select"
              value={modelForm.training_dataset_id}
              onChange={(event) => onUpdateModelForm("training_dataset_id", event.target.value)}
            >
              <option value="">Select training dataset</option>
              {trainingDatasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="test-dataset-select">Test Dataset</label>
            <select
              id="test-dataset-select"
              value={modelForm.test_dataset_id}
              onChange={(event) => onUpdateModelForm("test_dataset_id", event.target.value)}
            >
              <option value="">Select test dataset</option>
              {testDatasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field models-register-notes">
            <label htmlFor="model-notes">Notes</label>
            <textarea
              id="model-notes"
              rows="3"
              value={modelForm.notes}
              onChange={(event) => onUpdateModelForm("notes", event.target.value)}
            />
          </div>
        </div>
        <button className="primary" onClick={onRegisterModel}>Register and Evaluate v1</button>
      </div>

      <div className="models-family-list">
        {modelFamilies.length === 0 ? (
          <p className="empty-state">No registered models yet.</p>
        ) : (
          modelFamilies.map((family) => (
            <article key={family.id} className="panel model-family-card">
              <div className="model-family-header">
                <div>
                  <h3>{family.name}</h3>
                  <p className="muted">{family.versions.length} version(s)</p>
                </div>
              </div>

              <div className="model-version-list">
                {family.versions.map((version) => (
                  <div key={version.id} className="model-version-row">
                    <div className="model-version-main">
                      <p className="model-version-title">
                        {family.name} {version.version_tag}
                      </p>
                      <p className="muted">
                        {version.original_file_name} | {(Number(version.file_size_bytes || 0) / (1024 * 1024)).toFixed(2)} MB
                      </p>
                      <p className="muted">
                        Training: {version.training_dataset_name || "-"} | Test: {version.test_dataset_name || "-"}
                      </p>
                      <p className="muted">Stored path: {version.model_file_name}</p>
                      <p className="muted">
                        Replay buffer: {Number(version.replay_buffer_counts?.image_count || 0)} images | {Number(version.replay_buffer_counts?.detection_count || 0)} boxes
                      </p>
                    </div>

                    <div className="model-version-actions">
                      <button className="ghost" onClick={() => onDeleteModelVersion(version.id)}>
                        Delete Version
                      </button>
                    </div>

                    {version.latest_evaluation ? (
                      <div className="model-metrics-grid">
                        <div className="summary-item">
                          <p className="label">mAP</p>
                          <p className="value">{Number(version.latest_evaluation.overall_metrics.map || 0).toFixed(4)}</p>
                        </div>
                        <div className="summary-item">
                          <p className="label">mAP@50</p>
                          <p className="value">{Number(version.latest_evaluation.overall_metrics.map_50 || 0).toFixed(4)}</p>
                        </div>
                        <div className="summary-item">
                          <p className="label">mAR@100</p>
                          <p className="value">{Number(version.latest_evaluation.overall_metrics.mar_100 || 0).toFixed(4)}</p>
                        </div>
                      </div>
                    ) : (
                      <p className="muted">No evaluation stored yet.</p>
                    )}

                    {Array.isArray(version.latest_evaluation?.per_class_metrics) && version.latest_evaluation.per_class_metrics.length > 0 ? (
                      <div className="model-class-table">
                        {version.latest_evaluation.per_class_metrics.map((row) => (
                          <p key={`${version.id}-${row.class_id}`} className="muted">
                            {row.class_name}: mAP {Number(row.map || 0).toFixed(4)} | P {Number(row.precision || 0).toFixed(4)} | R{" "}
                            {Number(row.recall || 0).toFixed(4)} | F1 {Number(row.f1 || 0).toFixed(4)}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

export default ModelsView;
