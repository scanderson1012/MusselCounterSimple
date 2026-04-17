import HelpTooltip from "../components/HelpTooltip.jsx";
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
          <div className="title-with-help">
            <h3>Run Settings</h3>
            <HelpTooltip
              title="Run settings"
              wide
              content={[
                "Choose a model, set how strict the app should be, add images, and start the run here.",
                "These controls affect only the run you have open right now.",
              ]}
            />
          </div>
          <div className="field">
            <label htmlFor="model-select" className="label-with-help">
              <span>Model</span>
              <HelpTooltip
                title="Model selection"
                wide
                content={[
                  "Choose which saved model the app should use for this run.",
                  "Different models may give different counts, so use the same one when you want a fair comparison.",
                ]}
              />
            </label>
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
            <label htmlFor="threshold-range" className="label-with-help">
              <span>Threshold</span>
              <HelpTooltip
                title="Detection threshold"
                wide
                content={[
                  "This setting controls how sure the app must be before it shows a box.",
                  "A lower number usually shows more boxes. A higher number usually shows fewer boxes.",
                  "Recalculate updates the counts without running the model again.",
                ]}
              />
            </label>
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
            <div className="button-with-help">
              <button id="pick-images-btn" className="ghost" onClick={onPickImages} disabled={isBusy}>
                + Add Images
              </button>
              <HelpTooltip
                title="Add images"
                content="Adds microscope images to the current run queue before you start processing."
              />
            </div>
            <div className="button-with-help">
              <button id="run-inference-btn" className="primary" onClick={onRunInference} disabled={isBusy}>
                Start Run
              </button>
              <HelpTooltip
                title="Start run"
                wide
                content={[
                  "Starts the model on the images in this run.",
                  "Use this after choosing a model and adding images.",
                ]}
              />
            </div>
            <div className="button-with-help">
              <button id="recalculate-btn" className="ghost" onClick={onRecalculate} disabled={isBusy}>
                Recalculate
              </button>
              <HelpTooltip
                title="Recalculate"
                wide
                content={[
                  "Updates the live and dead counts using the setting above.",
                  "This does not run the model again. It only updates the counts for boxes already saved in this run.",
                ]}
              />
            </div>
            <div className="button-with-help">
              <button id="finalize-reviewed-run-btn" className="ghost" onClick={onFinalizeReviewedRun} disabled={isBusy || currentRunImages.length === 0}>
                Finalize Reviewed Labels
              </button>
              <HelpTooltip
                title="Finalize reviewed labels"
                wide
                content={[
                  "This saves the boxes you kept and corrected so they can help make a better model later.",
                  "Use this only after you finish checking the boxes you want to keep.",
                ]}
              />
            </div>
          </div>

          <p id="selected-images-text" className="helper">
            {selectedImagesText}
          </p>
          <p className="helper">
            Finalize Reviewed Labels saves the boxes you kept so they can be used later when making a new model version.
          </p>
          {replayBufferSummary ? (
            <p className="helper">
              Saved for later: {replayBufferSummary.image_count} images, {replayBufferSummary.detection_count} mussels.
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
