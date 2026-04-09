import RunImageCard from "../components/RunImageCard.jsx";

/**
 * Main run workflow view: settings, queue, summary, and run images.
 */
function RunView({
  visible,
  runSummary,
  totalReadyImages,
  models,
  selectedModelId,
  onModelChange,
  thresholdValue,
  onThresholdChange,
  onPickImages,
  onRunInference,
  onRecalculate,
  onFinalizeReviewedRun,
  isBusy,
  selectedImagesText,
  currentRunImages,
  replayBufferSummary,
  onDeleteAllImages,
  onOpenImage,
  onRemoveImage,
  runImageUrl,
}) {
  return (
    <section id="run-view" className={`view${visible ? "" : " hidden"}`}>
      <div className="run-header">
        <h1>Run Results</h1>
        <p id="run-meta-text" className="run-meta-text">
          {runSummary.runMetaText}
        </p>
      </div>

      <div className="panel run-summary" id="run-summary">
        <div className="summary-item">
          <p className="label">Live Mussels</p>
          <p className="value value-live" id="summary-live">
            {runSummary.liveCount}
          </p>
        </div>
        <div className="summary-item">
          <p className="label">Dead Mussels</p>
          <p className="value value-dead" id="summary-dead">
            {runSummary.deadCount}
          </p>
        </div>
        <div className="summary-item">
          <p className="label">Total Images</p>
          <p className="value" id="summary-images">
            {runSummary.imagesCount}
          </p>
        </div>
        <div className="summary-item">
          <p className="label">Total Mussels</p>
          <p className="value" id="summary-total">
            {runSummary.totalCount}
          </p>
        </div>
      </div>

      <div className="run-workspace-grid">
        <div className="panel current-run-panel">
          <h3>Current Run</h3>
          <p id="current-run-title" className="run-panel-line">
            {runSummary.currentRunTitle}
          </p>
          <p id="current-run-progress" className="run-panel-line muted">
            {totalReadyImages} images ready to process
          </p>
          <p className="run-panel-line muted">Click Start New Run to begin processing.</p>
        </div>

        <div className="panel controls">
          <h3>Run Settings</h3>
          <div className="field">
            <label htmlFor="model-select">Model</label>
            <select id="model-select" value={selectedModelId} onChange={(event) => onModelChange(event.target.value)}>
              {models.length === 0 ? (
                <option value="">No registered models</option>
              ) : (
                models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.file_name}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="field">
            <label htmlFor="threshold-range">Threshold</label>
            <div className="threshold-control">
              <input
                id="threshold-range"
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={thresholdValue.toFixed(2)}
                onChange={(event) => onThresholdChange(event.target.value)}
              />
              <input
                id="threshold-number"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={thresholdValue.toFixed(2)}
                onChange={(event) => onThresholdChange(event.target.value)}
              />
            </div>
          </div>

          <div className="button-row">
            <button id="pick-images-btn" className="ghost" onClick={onPickImages} disabled={isBusy}>
              + Add Images
            </button>
            <button id="run-inference-btn" className="primary" onClick={onRunInference} disabled={isBusy}>
              Start Run
            </button>
            <button id="recalculate-btn" className="ghost" onClick={onRecalculate} disabled={isBusy}>
              Recalculate
            </button>
            <button id="finalize-reviewed-run-btn" className="ghost" onClick={onFinalizeReviewedRun} disabled={isBusy || currentRunImages.length === 0}>
              Finalize Reviewed Labels
            </button>
          </div>

          <p id="selected-images-text" className="helper">
            {selectedImagesText}
          </p>
          <p className="helper">
            Finalize reviewed labels: saves the current run's non-deleted boxes and classes into the replay buffer for future fine-tuning.
          </p>
          {replayBufferSummary ? (
            <p className="helper">
              Replay buffer snapshot: {replayBufferSummary.image_count} images, {replayBufferSummary.detection_count} mussels saved.
            </p>
          ) : null}
        </div>
      </div>

      <div className="images-header">
        <h3 id="images-title">Images ({currentRunImages.length})</h3>
        <button id="delete-all-images-btn" className="ghost delete-all-btn" onClick={onDeleteAllImages}>
          Delete All
        </button>
      </div>

      <div id="image-grid" className="image-grid">
        {currentRunImages.length === 0 ? (
          <p className="empty-state">No images in this run yet.</p>
        ) : (
          currentRunImages.map((imageData) => (
            <RunImageCard
              key={imageData.run_image_id}
              imageData={imageData}
              imageUrl={runImageUrl(imageData.image_url)}
              onOpen={() => onOpenImage(imageData.run_image_id)}
              onRemove={() => onRemoveImage(imageData.run_image_id)}
            />
          ))
        )}
      </div>
    </section>
  );
}

export default RunView;
