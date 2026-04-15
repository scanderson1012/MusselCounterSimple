/**
 * Application settings page.
 */
function formatComputeModeLabel(mode) {
  const normalizedMode = String(mode || "automatic").toLowerCase();
  if (normalizedMode === "cpu_only") {
    return "CPU Only";
  }
  if (normalizedMode === "gpu_if_available") {
    return "GPU If Available";
  }
  return "Automatic";
}

function SettingsView({
  visible,
  settings,
  computeStatus,
  draftSettings,
  onChangeSetting,
  onSaveSettings,
  isSavingSettings,
}) {
  return (
    <section id="settings-view" className={`view${visible ? "" : " hidden"}`}>
      <div className="run-header">
        <h1>Settings</h1>
        <p className="run-meta-text">
          Manage app-wide fine-tuning behavior and compute preferences. These settings apply across all model families.
        </p>
      </div>

      <div className="settings-stack">
        <div className="panel settings-panel">
          <div className="settings-panel-header">
            <div>
              <h3>Fine-Tuning</h3>
              <p className="helper">
                Control when fine-tuning becomes available and how many epochs each fine-tuning run should use.
              </p>
            </div>
          </div>

          <div className="settings-grid">
            <div className="field">
              <label htmlFor="fine-tune-min-new-images">New Images Required</label>
              <input
                id="fine-tune-min-new-images"
                type="number"
                min="1"
                value={draftSettings.fine_tune_min_new_images}
                onChange={(event) => onChangeSetting("fine_tune_min_new_images", event.target.value)}
              />
              <p className="helper">
                Fine-tuning becomes available once the replay buffer has at least this many new finalized images for the latest version of a model.
              </p>
            </div>

            <div className="field">
              <label htmlFor="fine-tune-num-epochs">Fine-Tuning Epochs</label>
              <input
                id="fine-tune-num-epochs"
                type="number"
                min="1"
                value={draftSettings.fine_tune_num_epochs}
                onChange={(event) => onChangeSetting("fine_tune_num_epochs", event.target.value)}
              />
              <p className="helper">
                An epoch is one full pass through the selected fine-tuning images plus the replay sample from older training data.
              </p>
            </div>
          </div>

          <div className="settings-footer">
            <p className="helper">
              Current saved settings: {Number(settings.fine_tune_min_new_images || 0)} new images, {Number(settings.fine_tune_num_epochs || 0)} epochs.
            </p>
            <button className="primary" onClick={onSaveSettings} disabled={isSavingSettings}>
              {isSavingSettings ? "Saving..." : "Save Settings"}
            </button>
          </div>
        </div>

        <div className="panel settings-panel">
          <div className="settings-panel-header">
            <div>
              <h3>Compute</h3>
              <p className="helper">
                Choose whether the app should stay on CPU or use GPU acceleration when a compatible setup is available.
              </p>
            </div>
          </div>

          <div className="settings-grid">
            <div className="field">
              <label htmlFor="compute-mode">Compute Mode</label>
              <select
                id="compute-mode"
                value={draftSettings.compute_mode}
                onChange={(event) => onChangeSetting("compute_mode", event.target.value)}
              >
                <option value="automatic">Automatic</option>
                <option value="cpu_only">CPU only</option>
                <option value="gpu_if_available">GPU if available</option>
              </select>
              <p className="helper">
                Automatic and GPU modes both fall back to CPU if GPU acceleration is not ready on this computer.
              </p>
            </div>

            <div className="field">
              <label>Current Status</label>
              <div className="settings-compute-summary">
                <p className="settings-compute-line">
                  Preferred mode: <strong>{formatComputeModeLabel(settings.compute_mode)}</strong>
                </p>
                <p className="settings-compute-line">
                  Active device: <strong>{computeStatus?.effective_device === "cuda" ? "GPU" : "CPU"}</strong>
                </p>
                <p className="settings-compute-line">
                  Compatible GPU detected: <strong>{computeStatus?.compatible_gpu_detected ? (computeStatus.detected_gpu_name || "Yes") : "No"}</strong>
                </p>
                <p className="settings-compute-line">
                  GPU runtime ready: <strong>{computeStatus?.gpu_runtime_ready ? "Yes" : "No"}</strong>
                </p>
              </div>
            </div>
          </div>

          <div className="settings-footer">
            <p className="helper">
              CPU support is always kept available. GPU acceleration is used only when the computer and installed runtime support it.
            </p>
            <button className="primary" onClick={onSaveSettings} disabled={isSavingSettings}>
              {isSavingSettings ? "Saving..." : "Save Settings"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

export default SettingsView;
