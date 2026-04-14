/**
 * Application settings page.
 */
function SettingsView({
  visible,
  settings,
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
          Manage app-wide fine-tuning behavior. These settings apply across all model families.
        </p>
      </div>

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
    </section>
  );
}

export default SettingsView;
