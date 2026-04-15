/**
 * Models registry page and add-model / model-info modals.
 */
function getRequestedMetrics(modelReport) {
  const overall = modelReport?.evaluation?.overall_metrics || {};
  const perClassRows = Array.isArray(modelReport?.evaluation?.per_class_metrics)
    ? modelReport.evaluation.per_class_metrics
    : [];
  const deadRow = perClassRows.find((row) => String(row.class_name || "").toLowerCase() === "dead") || {};
  const liveRow = perClassRows.find((row) => String(row.class_name || "").toLowerCase() === "live") || {};
  return [
    { label: "Overall mAP", value: Number(overall.map || 0).toFixed(4) },
    { label: "mAP@50", value: Number(overall.map_50 || 0).toFixed(4) },
    { label: "mAP@75", value: Number(overall.map_75 || 0).toFixed(4) },
    { label: "Dead Precision", value: Number(deadRow.precision || 0).toFixed(4) },
    { label: "Dead Recall", value: Number(deadRow.recall || 0).toFixed(4) },
    { label: "Alive Precision", value: Number(liveRow.precision || 0).toFixed(4) },
    { label: "Alive Recall", value: Number(liveRow.recall || 0).toFixed(4) },
  ];
}

function getMetricLines(modelReport) {
  const metrics = getRequestedMetrics(modelReport);
  return [
    {
      title: "mAP Values",
      values: metrics.slice(0, 3),
    },
    {
      title: "Dead Class",
      values: metrics.slice(3, 5),
    },
    {
      title: "Alive Class",
      values: metrics.slice(5, 7),
    },
  ];
}

function ModelsView({
  visible,
  modelFamilies,
  modelForm,
  onUpdateModelForm,
  onChooseModelFile,
  onRegisterModel,
  onDeleteModelVersion,
  onDeleteModelFamily,
  onExportModelVersion,
  onOpenModelInfo,
  onEvaluateModelVersion,
  onFineTuneModelVersion,
  isModelModalOpen,
  onCloseModelModal,
  isSubmittingModel,
  modelReport,
  onCloseModelReport,
}) {
  return (
    <section id="models-view" className={`view${visible ? "" : " hidden"}`}>
      <div className="run-header">
        <h1>Models</h1>
        <p className="run-meta-text">
          Browse stored models and versions, review their evaluation results, and export model packages.
        </p>
      </div>

      <div className="panel models-help-panel">
        <h3>How Model Registration Works</h3>
        <p className="helper">
          Click <strong>Add Model</strong>, choose a `.pth` or `.pt` checkpoint file, then enter a model name, a clear description,
          and the training/test dataset image and label folder paths.
        </p>
        <p className="helper">
          The description should explain what the model is, what scope of data it should be tested on, and the intended use cases.
        </p>
        <p className="helper">
          After submission, the app stores the model and links its training and test datasets. Evaluation runs only when you click
          <strong> Evaluate on Test Set</strong> for that version.
        </p>
      </div>

      <div className="models-family-list">
        {modelFamilies.length === 0 ? (
          <p className="empty-state">No registered models yet.</p>
        ) : (
          modelFamilies.map((family) => (
            <article key={family.id} className="panel model-family-card">
              {(() => {
                const isBaselineFamily = String(family.name || "").toLowerCase() === "fasterrcnn_baseline";
                return (
              <div className="model-family-header">
                <div>
                  <h3>{family.name}</h3>
                  <p className="muted">{family.versions.length} version(s)</p>
                </div>
                {!isBaselineFamily ? (
                  <button className="ghost delete-all-btn" onClick={() => onDeleteModelFamily(family)}>
                    Delete Model
                  </button>
                ) : null}
              </div>
                );
              })()}

                <div className="model-version-list">
                  {family.versions.map((version) => {
                    const isBaselineFamily = String(family.name || "").toLowerCase() === "fasterrcnn_baseline";
                    const canDeleteVersion = !isBaselineFamily || Number(version.version_number || 0) > 1;
                    return (
                      <div key={version.id} className="model-version-row">
                      <div className="model-version-main">
                        <p className="model-version-title">
                          {family.name} {version.version_tag}
                        </p>
                        <p className="muted">
                          Replay buffer: {Number(version.replay_buffer_counts?.image_count || 0)} images | {Number(version.replay_buffer_counts?.detection_count || 0)} mussels
                        </p>
                      </div>

                      <div className="model-version-actions">
                        {version.is_latest_version ? (
                          <button className="ghost" onClick={() => onFineTuneModelVersion({ ...version, family_name: family.name })}>
                            Fine-Tune
                          </button>
                        ) : null}
                        <button className="ghost" onClick={() => onEvaluateModelVersion({ ...version, family_name: family.name })}>
                          Evaluate on Test Set
                        </button>
                        <button className="ghost" onClick={() => onOpenModelInfo(version.id)}>
                          Model Information
                        </button>
                        <button className="ghost" onClick={() => onExportModelVersion({ ...version, family_name: family.name })}>
                          Export
                        </button>
                        {canDeleteVersion ? (
                          <button className="ghost" onClick={() => onDeleteModelVersion({ ...version, family_name: family.name })}>
                            Delete Version
                          </button>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </article>
          ))
        )}
      </div>

      {isModelModalOpen ? (
        <div className="modal-overlay" onClick={onCloseModelModal}>
          <div className="modal-card model-modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Model</h3>
              <button className="ghost modal-close" onClick={onCloseModelModal}>×</button>
            </div>
            <div className="modal-body">
              <div className="field">
                <label>Model File</label>
                <button className="ghost modal-wide-btn" onClick={onChooseModelFile}>
                  {modelForm.selected_model_file_name || "Choose .pth or .pt file"}
                </button>
                <p className="helper">Select the actual checkpoint file. The app will store it in managed model storage.</p>
              </div>

              <div className="field">
                <label htmlFor="model-family-name">Model Name</label>
                <input
                  id="model-family-name"
                  type="text"
                  placeholder="Defaults to the selected file name"
                  value={modelForm.family_name}
                  onChange={(event) => onUpdateModelForm("family_name", event.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="model-description">Model Description</label>
                <textarea
                  id="model-description"
                  rows="6"
                  placeholder="Explain what the model is, what scope of data it should be tested on, and the intended use cases."
                  value={modelForm.description}
                  onChange={(event) => onUpdateModelForm("description", event.target.value)}
                />
                <p className="helper">
                  Include: what the model detects, the types of images or conditions it should be tested on, and when users should choose it.
                </p>
              </div>

              <div className="models-register-grid">
                <div className="field">
                  <label htmlFor="training-images-dir">Training Images Folder Path</label>
                  <input
                    id="training-images-dir"
                    type="text"
                    value={modelForm.training_images_dir}
                    onChange={(event) => onUpdateModelForm("training_images_dir", event.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="training-labels-dir">Training Labels Folder Path</label>
                  <input
                    id="training-labels-dir"
                    type="text"
                    value={modelForm.training_labels_dir}
                    onChange={(event) => onUpdateModelForm("training_labels_dir", event.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="test-images-dir">Test Images Folder Path</label>
                  <input
                    id="test-images-dir"
                    type="text"
                    value={modelForm.test_images_dir}
                    onChange={(event) => onUpdateModelForm("test_images_dir", event.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="test-labels-dir">Test Labels Folder Path</label>
                  <input
                    id="test-labels-dir"
                    type="text"
                    value={modelForm.test_labels_dir}
                    onChange={(event) => onUpdateModelForm("test_labels_dir", event.target.value)}
                  />
                </div>
              </div>

              <div className="field">
                <label htmlFor="model-notes">Notes</label>
                <textarea
                  id="model-notes"
                  rows="3"
                  value={modelForm.notes}
                  onChange={(event) => onUpdateModelForm("notes", event.target.value)}
                />
              </div>

              <button className="primary modal-wide-btn" onClick={onRegisterModel} disabled={isSubmittingModel}>
                {isSubmittingModel ? "Registering..." : "Register Model"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {modelReport ? (
        <div className="modal-overlay" onClick={onCloseModelReport}>
          <div className="modal-card model-report-card" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>{modelReport.title}</h3>
              <button className="ghost modal-close" onClick={onCloseModelReport}>×</button>
            </div>
            <div className="modal-body model-report-body">
              <section className="model-report-section">
                <p className="model-report-eyebrow">Description</p>
                <p className="helper prewrap model-report-copy">{modelReport.description || "No description provided."}</p>
              </section>

              <section className="model-report-section">
                <p className="model-report-eyebrow">Training Dataset</p>
                <p className="helper model-report-copy"><strong>Name:</strong> {modelReport.training_dataset.name}</p>
                <p className="helper model-report-copy"><strong>Images:</strong> {modelReport.training_dataset.images_dir}</p>
                <p className="helper model-report-copy"><strong>Labels:</strong> {modelReport.training_dataset.labels_dir}</p>
              </section>

              <section className="model-report-section">
                <p className="model-report-eyebrow">Test Dataset</p>
                <p className="helper model-report-copy"><strong>Name:</strong> {modelReport.test_dataset.name}</p>
                <p className="helper model-report-copy"><strong>Images:</strong> {modelReport.test_dataset.images_dir}</p>
                <p className="helper model-report-copy"><strong>Labels:</strong> {modelReport.test_dataset.labels_dir}</p>
              </section>

              <section className="model-report-section">
                <p className="model-report-eyebrow">Evaluation</p>
                <div className="model-report-metrics">
                  {getMetricLines(modelReport).map((line) => (
                    <div key={line.title} className="model-report-metric-line">
                      <p className="model-report-metric-title">{line.title}</p>
                      <div className="model-report-metric-values">
                        {line.values.map((metric) => (
                          <span key={metric.label}>{metric.label}: {metric.value}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default ModelsView;
