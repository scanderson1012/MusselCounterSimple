import HelpTooltip from "../components/HelpTooltip.jsx";

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
  onActivateGpuRuntime,
  isActivatingGpuRuntime,
}) {
  return (
    <section id="settings-view" className={`view${visible ? "" : " hidden"}`}>
      <div className="run-header">
        <h1>Settings</h1>
        <p className="run-meta-text">
          Choose when fine-tuning becomes available and whether the app should use automatic compute, CPU only, or GPU if available.
        </p>
      </div>

      <div className="settings-stack">
        <div className="panel settings-panel">
          <div className="settings-panel-header">
            <div>
              <div className="title-with-help">
                <h3>Fine-Tuning</h3>
                <HelpTooltip
                  title="Fine-tuning settings"
                  wide
                  content={[
                    "These settings control when you can make a new version of a model.",
                    "They affect the whole app, not just the run you are looking at now.",
                  ]}
                />
              </div>
              <p className="helper">
                These settings control when a new model version can be created. Recommended settings: Automatic compute, 10 epochs, and 25 new images.
              </p>
            </div>
          </div>

          <div className="settings-grid">
            <div className="field">
              <label htmlFor="fine-tune-min-new-images" className="label-with-help">
                <span>New Images Required</span>
                <HelpTooltip
                  title="New images required"
                  wide
                  content={[
                    "This is the number of reviewed images you need before the Fine-Tune button becomes available.",
                    "A higher number means you wait longer. A lower number means it becomes available sooner.",
                    "Recommended setting: 25 new images.",
                  ]}
                />
              </label>
              <input
                id="fine-tune-min-new-images"
                type="number"
                min="1"
                value={draftSettings.fine_tune_min_new_images}
                onChange={(event) => onChangeSetting("fine_tune_min_new_images", event.target.value)}
              />
              <p className="helper">
                Fine-Tune becomes available when the newest version of a model has at least this many reviewed images saved for later use.
              </p>
            </div>

            <div className="field">
              <label htmlFor="fine-tune-num-epochs" className="label-with-help">
                <span>Fine-Tuning Epochs</span>
                <HelpTooltip
                  title="Fine-tuning epochs"
                  wide
                  content={[
                    "This number controls how many times the app goes through the images while making a new model version.",
                    "A larger number usually means a longer run time.",
                    "Recommended setting: 10 epochs.",
                  ]}
                />
              </label>
              <input
                id="fine-tune-num-epochs"
                type="number"
                min="1"
                value={draftSettings.fine_tune_num_epochs}
                onChange={(event) => onChangeSetting("fine_tune_num_epochs", event.target.value)}
              />
              <p className="helper">
                A larger number usually means the app runs longer before the new version is ready.
              </p>
            </div>
          </div>

          <div className="settings-footer">
            <p className="helper">
              Current saved settings: {Number(settings.fine_tune_min_new_images || 0)} new images required and {Number(settings.fine_tune_num_epochs || 0)} epochs.
            </p>
            <button className="primary" onClick={onSaveSettings} disabled={isSavingSettings}>
              {isSavingSettings ? "Saving..." : "Save Settings"}
            </button>
          </div>
        </div>

        <div className="panel settings-panel">
          <div className="settings-panel-header">
            <div>
              <div className="title-with-help">
                <h3>Compute</h3>
                <HelpTooltip
                  title="Compute settings"
                  wide
                  content={[
                    "These settings decide whether the app should try to use the GPU in your computer.",
                    "This can affect how fast the app runs.",
                  ]}
                />
              </div>
              <p className="helper">
                Automatic is the recommended setting. Use CPU Only if you do not want the app to try using the GPU.
              </p>
            </div>
          </div>

          <div className="settings-grid">
            <div className="field">
              <label htmlFor="compute-mode" className="label-with-help">
                <span>Compute Mode</span>
                <HelpTooltip
                  title="Compute mode"
                  wide
                  content={[
                    "Automatic lets the app decide and is the recommended setting.",
                    "CPU Only means the app will always use the CPU.",
                    "GPU If Available means the app will try to use the GPU when it is ready.",
                  ]}
                />
              </label>
              <select
                id="compute-mode"
                value={draftSettings.compute_mode}
                onChange={(event) => onChangeSetting("compute_mode", event.target.value)}
              >
                <option value="automatic">Automatic (Recommended)</option>
                <option value="cpu_only">CPU only</option>
                <option value="gpu_if_available">GPU if available</option>
              </select>
              <p className="helper">
                If the GPU is not ready, the app uses the CPU instead.
              </p>
            </div>

            <div className="field">
              <label className="label-with-help">
                <span>Current Status</span>
                <HelpTooltip
                  title="Current status"
                  wide
                  content={[
                    "Preferred mode is the choice you saved.",
                    "Active device is what the app is using right now.",
                    "If the GPU is not ready, the app uses the CPU.",
                  ]}
                />
              </label>
              <div className="settings-compute-summary">
                <p className="settings-compute-line">
                  Preferred mode: <strong>{formatComputeModeLabel(settings.compute_mode)}</strong>
                </p>
                <p className="settings-compute-line">
                  Active runtime: <strong>{computeStatus?.backend_runtime_variant === "gpu" ? "GPU-enabled backend" : "CPU backend"}</strong>
                </p>
                <p className="settings-compute-line">
                  Active device: <strong>{computeStatus?.effective_device === "cuda" ? "GPU" : "CPU"}</strong>
                </p>
                <p className="settings-compute-line">
                  Compatible GPU detected: <strong>{computeStatus?.compatible_gpu_detected ? (computeStatus.detected_gpu_name || "Yes") : "No"}</strong>
                </p>
                <p className="settings-compute-line">
                  Optional GPU runtime installed: <strong>{computeStatus?.optional_gpu_runtime_installed ? "Yes" : "No"}</strong>
                </p>
                <p className="settings-compute-line">
                  GPU runtime ready: <strong>{computeStatus?.gpu_runtime_ready ? "Yes" : "No"}</strong>
                </p>
              </div>
            </div>
          </div>

          <div className="settings-footer">
            <p className="helper">
              Current saved setting: {formatComputeModeLabel(settings.compute_mode)}.
            </p>
            <div className="button-row">
              {computeStatus?.can_offer_gpu_upgrade ? (
                <button className="ghost" onClick={onActivateGpuRuntime} disabled={isActivatingGpuRuntime || isSavingSettings}>
                  {isActivatingGpuRuntime ? "Enabling GPU Runtime..." : "Enable Optional GPU Runtime"}
                </button>
              ) : null}
              <button className="primary" onClick={onSaveSettings} disabled={isSavingSettings || isActivatingGpuRuntime}>
                {isSavingSettings ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default SettingsView;
