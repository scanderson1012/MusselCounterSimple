/**
 * App usage guidance page for non-technical users.
 */
function UsageView({ visible, onOpenSharedDrive }) {
  return (
    <section id="usage-view" className={`view${visible ? "" : " hidden"}`}>
      <div className="run-header">
        <h1>App Usage</h1>
        <p className="run-meta-text usage-intro-text">
          Follow these step-by-step guides to run the app, review detections, manage models, and fine-tune new versions.
        </p>
      </div>

      <div className="usage-section-grid">
        <div className="panel usage-panel">
          <h3>1. Run a Model on New Images</h3>
          <p className="helper usage-copy">
            Use this process when you want the app to count mussels in new microscope images.
          </p>
          <ol className="usage-step-list">
            <li>Open the Home page.</li>
            <li>Select the model version you want to use.</li>
            <li>Upload one or more microscope images.</li>
            <li>Click the run button to start model execution.</li>
            <li>Wait for the app to finish counting live and dead mussels for each image.</li>
            <li>If needed, adjust the threshold and recalculate counts without running the model again.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3>2. Review and Edit Detections</h3>
          <p className="helper usage-copy">
            Review every run carefully so the saved labels are correct before they enter the replay buffer.
          </p>
          <ol className="usage-step-list">
            <li>Open a processed image from the run results.</li>
            <li>Check each detection box for the correct location and class label.</li>
            <li>Relabel boxes if the model marked a mussel incorrectly.</li>
            <li>Delete boxes that should not be there.</li>
            <li>Add new boxes if the model missed a mussel.</li>
            <li>Repeat for all images you want to save as reviewed data.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3>3. Finalize Reviewed Labels Into the Replay Buffer</h3>
          <p className="helper usage-copy">
            Finalizing is what turns reviewed run results into training-ready examples for future fine-tuning.
          </p>
          <ol className="usage-step-list">
            <li>Finish reviewing the images in a run.</li>
            <li>Return to the Home page.</li>
            <li>Click the finalize button for that run.</li>
            <li>The app stores the corrected labels in the replay buffer for the model version that created the run.</li>
            <li>Those replay-buffer images are then available for future fine-tuning once the image threshold is reached.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3>4. Evaluate a Model on Its Test Set</h3>
          <p className="helper usage-copy">
            Evaluation measures model quality on the test set that was assigned when the model was added.
          </p>
          <ol className="usage-step-list">
            <li>Open the Models page.</li>
            <li>Find the model version you want to evaluate.</li>
            <li>Click <strong>Evaluate on Test Set</strong>.</li>
            <li>Wait for the progress bar to finish, or cancel if needed.</li>
            <li>The app saves the evaluation metrics for that version after the run completes.</li>
            <li>Each model version only needs to be evaluated once on its assigned test set.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3>5. Fine-Tune the Latest Model Version</h3>
          <p className="helper usage-copy">
            Fine-tuning creates the next version of a model by learning from reviewed replay-buffer images.
          </p>
          <ol className="usage-step-list">
            <li>Open the Settings page and confirm the fine-tuning image threshold and epoch count.</li>
            <li>Keep reviewing and finalizing runs until the replay buffer reaches the required number of new images.</li>
            <li>Wait for the global notification that fine-tuning is available.</li>
            <li>Open the Models page and click <strong>Fine-Tune</strong> on the newest model version.</li>
            <li>The app uses the oldest eligible replay-buffer images first and combines them with randomly selected older training images.</li>
            <li>When fine-tuning finishes, a new model version is created and the used replay-buffer images are removed from the buffer.</li>
            <li>If you cancel fine-tuning, nothing is saved and the replay buffer stays unchanged.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3>6. Understand Version Deletion and Rollback</h3>
          <p className="helper usage-copy">
            Deletion rules are designed to keep model history clean and predictable.
          </p>
          <ol className="usage-step-list">
            <li>Deleting a model version removes that version and every newer version after it in the same family.</li>
            <li>If you delete the newest versions, the latest remaining older version becomes the active newest version again.</li>
            <li>Replay-buffer images consumed by deleted newer versions are restored so they can be used again later.</li>
            <li>Deleting version 1 is treated like deleting the whole model family.</li>
            <li>The bundled baseline model family cannot be deleted, and its version 1 cannot be deleted.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3>7. Export and Share Models</h3>
          <p className="helper usage-copy">
            Exporting packages a model version so another user can add it into their own copy of the app.
          </p>
          <ol className="usage-step-list">
            <li>Open the Models page.</li>
            <li>Find the model version you want to share.</li>
            <li>Click <strong>Export</strong>.</li>
            <li>The app downloads a zip file containing the model checkpoint file and the model information document.</li>
            <li>Share that exported package with another user.</li>
            <li>The other user can then add the model into their own app with the normal Add Model workflow.</li>
          </ol>
        </div>
      </div>

      <div className="usage-subsection">
        <div className="run-header usage-subsection-header">
          <h2>Model Sharing</h2>
          <p className="helper usage-copy">
            Use this section to share models between users with the shared Google Drive. This is separate from normal app
            usage and is meant for moving model files and model information documents between team members.
          </p>
        </div>

        <div className="panel usage-panel usage-drive-panel">
          <h3>Shared Google Drive Workflow</h3>
          <button className="ghost usage-link-btn" onClick={onOpenSharedDrive}>
            Open Shared Google Drive
          </button>
          <ol className="usage-step-list">
            <li>Open the shared drive using the button above.</li>
            <li>Use the baseline training set, baseline test set, and baseline model file as the shared starting point for all users.</li>
            <li>When you want to share a model, export it from the app first.</li>
            <li>Create a new folder on the drive using the model name.</li>
            <li>Upload the exported model information document and the model `.pth` or `.pt` file into that folder.</li>
            <li>Other users can then download those files from the drive and add the model into their own app.</li>
          </ol>
          <div className="usage-example-block">
            <p className="usage-example-title">Folder layout</p>
            <div className="usage-example-structure">
              <p className="usage-example-folder">ModelName/</p>
              <ul className="usage-example-list">
                <li>ModelName info document</li>
                <li>ModelName .pth or .pt file</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default UsageView;
