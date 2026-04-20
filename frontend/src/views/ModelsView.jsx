import HelpTooltip from "../components/HelpTooltip.jsx";

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
  onChooseDatasetZipFile,
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
          View saved models, check how they performed, and export them to share with someone else.
        </p>
      </div>

      <div className="panel models-help-panel">
        <div className="title-with-help">
          <h3>How Model Registration Works</h3>
          <HelpTooltip
            title="Model registration"
            wide
            content={[
              "Add Model saves a model file in the app and records where its training and test images came from.",
              "The app does not test the model until you click Evaluate on Test Set.",
            ]}
          />
        </div>
        <p className="helper">
          Click <strong>Add Model</strong>, choose a `.pth` or `.pt` model file, then choose the Roboflow dataset `.zip`
          used to train and test it, and enter a model name and clear description.
        </p>
        <p className="helper">
          The description should explain what the model is for, what kinds of images it fits, and when someone should use it.
        </p>
        <p className="helper">
          After you save it, the app stores the model and its dataset information. The test only runs when you click
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
                const isBaselineFamily = Boolean(family.is_bundled_baseline);
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
                    const isBaselineFamily = Boolean(version.is_bundled_baseline ?? family.is_bundled_baseline);
                    const canDeleteVersion = !isBaselineFamily || Number(version.version_number || 0) > 1;
                    return (
                      <div key={version.id} className="model-version-row">
                      <div className="model-version-main">
                        <p className="model-version-title">
                          {family.name} {version.version_tag}
                        </p>
                        <p className="muted">
                          Saved reviewed images: {Number(version.replay_buffer_counts?.image_count || 0)} | Saved mussels: {Number(version.replay_buffer_counts?.detection_count || 0)}
                        </p>
                      </div>

                      <div className="model-version-actions">
                        {version.is_latest_version ? (
                          <div className="button-with-help">
                            <button className="ghost" onClick={() => onFineTuneModelVersion({ ...version, family_name: family.name })}>
                              Fine-Tune
                            </button>
                            <HelpTooltip
                              title="Fine-tune"
                              wide
                              content={[
                                "Makes a new version of this model using reviewed images you saved earlier.",
                                "Only the newest version has this button.",
                              ]}
                            />
                          </div>
                        ) : null}
                        <div className="button-with-help">
                          <button className="ghost" onClick={() => onEvaluateModelVersion({ ...version, family_name: family.name })}>
                            Evaluate on Test Set
                          </button>
                          <HelpTooltip
                            title="Evaluate on test set"
                            wide
                            content={[
                              "Tests this model on its saved test images and records the results.",
                              "Use this when you want to compare models in a fair way.",
                            ]}
                          />
                        </div>
                        <div className="button-with-help">
                          <button className="ghost" onClick={() => onOpenModelInfo(version.id)}>
                            Model Information
                          </button>
                          <HelpTooltip
                            title="Model information"
                            wide
                            content={[
                              "Opens the saved description, folder details, and test results for this version.",
                              "Use this to check what the model is for before you run it or share it.",
                            ]}
                          />
                        </div>
                        <div className="button-with-help">
                          <button className="ghost" onClick={() => onExportModelVersion({ ...version, family_name: family.name })}>
                            Export
                          </button>
                          <HelpTooltip
                            title="Export"
                            wide
                            content={[
                              "Saves this model version as a zip file you can share.",
                              "Someone else can add that file to their copy of the app.",
                            ]}
                          />
                        </div>
                        {canDeleteVersion ? (
                          <div className="button-with-help">
                            <button className="ghost" onClick={() => onDeleteModelVersion({ ...version, family_name: family.name })}>
                              Delete Version
                            </button>
                            <HelpTooltip
                              title="Delete version"
                              wide
                              content={[
                                "Deleting this version also deletes every newer version after it.",
                                "Use this carefully because it removes part of the model's history.",
                              ]}
                            />
                          </div>
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
                <label className="label-with-help">
                  <span>Model File</span>
                  <HelpTooltip
                    title="Model file"
                    wide
                    content={[
                      "Choose the model file you want to save in the app.",
                      "The app accepts .pth and .pt files.",
                    ]}
                  />
                </label>
                <button className="ghost modal-wide-btn" onClick={onChooseModelFile}>
                  {modelForm.selected_model_file_name || "Choose .pth or .pt file"}
                </button>
                <p className="helper">Choose the model file itself. The app will save its own copy.</p>
              </div>

              <div className="field">
                <label className="label-with-help">
                  <span>Dataset Zip File</span>
                  <HelpTooltip
                    title="Dataset zip file"
                    wide
                    content={[
                      "Choose the Roboflow export zip used to make this model.",
                      "The zip should contain train and test folders with images and matching Pascal VOC XML files.",
                    ]}
                  />
                </label>
                <button className="ghost modal-wide-btn" onClick={onChooseDatasetZipFile}>
                  {modelForm.selected_dataset_zip_file_name || "Choose dataset .zip file"}
                </button>
                <p className="helper">
                  The app reads the train and test folders directly from this zip file when it needs to evaluate or fine-tune the model.
                </p>
              </div>

              <div className="field">
                <label htmlFor="model-family-name" className="label-with-help">
                  <span>Model Name</span>
                  <HelpTooltip
                    title="Model name"
                    wide
                    content={[
                      "This is the name people will see in the app.",
                      "Newer versions of this model will stay grouped under this name.",
                    ]}
                  />
                </label>
                <input
                  id="model-family-name"
                  type="text"
                  placeholder="Defaults to the selected file name"
                  value={modelForm.family_name}
                  onChange={(event) => onUpdateModelForm("family_name", event.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="model-description" className="label-with-help">
                  <span>Model Description</span>
                  <HelpTooltip
                    title="Model description"
                    wide
                    content={[
                      "Describe what the model looks for, what kinds of images it works well on, and when to use it.",
                      "This helps people choose the right model.",
                    ]}
                  />
                </label>
                <textarea
                  id="model-description"
                  rows="6"
                  placeholder="Explain what the model is, what scope of data it should be tested on, and the intended use cases."
                  value={modelForm.description}
                  onChange={(event) => onUpdateModelForm("description", event.target.value)}
                />
                <p className="helper">
                  Include what the model looks for, what kinds of images it works well on, and when someone should use it.
                </p>
              </div>

              <div className="field">
                <label htmlFor="model-notes" className="label-with-help">
                  <span>Notes</span>
                  <HelpTooltip
                    title="Notes"
                    wide
                    content={[
                      "Optional space for reminders or extra details.",
                    ]}
                  />
                </label>
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
                <p className="helper model-report-copy"><strong>Type:</strong> {modelReport.training_dataset.dataset_format === "roboflow_zip" ? "Roboflow Zip" : "Images + Labels Folders"}</p>
                <p className="helper model-report-copy"><strong>Zip:</strong> {modelReport.training_dataset.zip_file_path || "-"}</p>
                <p className="helper model-report-copy"><strong>Split:</strong> {modelReport.training_dataset.split_name || "-"}</p>
                <p className="helper model-report-copy"><strong>Images:</strong> {modelReport.training_dataset.images_dir}</p>
                <p className="helper model-report-copy"><strong>Labels:</strong> {modelReport.training_dataset.labels_dir}</p>
              </section>

              <section className="model-report-section">
                <p className="model-report-eyebrow">Test Dataset</p>
                <p className="helper model-report-copy"><strong>Name:</strong> {modelReport.test_dataset.name}</p>
                <p className="helper model-report-copy"><strong>Type:</strong> {modelReport.test_dataset.dataset_format === "roboflow_zip" ? "Roboflow Zip" : "Images + Labels Folders"}</p>
                <p className="helper model-report-copy"><strong>Zip:</strong> {modelReport.test_dataset.zip_file_path || "-"}</p>
                <p className="helper model-report-copy"><strong>Split:</strong> {modelReport.test_dataset.split_name || "-"}</p>
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
