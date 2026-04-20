/**
 * App usage guidance page for non-technical users.
 */
function UsageView({ visible, onOpenSharedDrive, onOpenRoboflow, onOpenTrainingCode }) {
  return (
    <section id="usage-view" className={`view${visible ? "" : " hidden"}`}>
      <div className="run-header">
        <h1>App Usage</h1>
        <p className="run-meta-text usage-intro-text">
          Follow these step-by-step guides to run the app, review results, manage models, and create new model versions.
        </p>
      </div>

      <div className="usage-section-grid">
        <div className="panel usage-panel">
          <h3 className="usage-panel-title">1. Run a Model on New Images</h3>
          <p className="helper usage-copy">
            Use this process when you want the app to count mussels in new microscope images.
          </p>
          <ol className="usage-step-list">
            <li>Open the Home page.</li>
            <li>Select the model you want to use.</li>
            <li>Upload one or more microscope images.</li>
            <li>Click the run button to start model execution.</li>
            <li>Wait for the app to finish counting live and dead mussels for each image.</li>
            <li>If needed, change the threshold setting and recalculate counts without running the model again.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3 className="usage-panel-title">2. Review and Edit Detections</h3>
          <p className="helper usage-copy">
            Review each run carefully so the saved boxes and labels are correct before they are used later.
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
          <h3 className="usage-panel-title">3. Finalize Reviewed Labels Into the Replay Buffer</h3>
          <p className="helper usage-copy">
            Finalizing saves your reviewed boxes so they can help make a better model later.
          </p>
          <ol className="usage-step-list">
            <li>Finish reviewing the images in a run.</li>
            <li>Return to the Home page.</li>
            <li>Click the finalize button for that run.</li>
            <li>The app saves the corrected boxes for the model that created the run.</li>
            <li>Those saved images can later be used to make a new version once you have enough of them.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3 className="usage-panel-title">4. Evaluate a Model on Its Test Set</h3>
          <p className="helper usage-copy">
            This checks how well a model works on the test images saved with it.
          </p>
          <ol className="usage-step-list">
            <li>Open the Models page.</li>
            <li>Find the model you want to test.</li>
            <li>Click <strong>Evaluate on Test Set</strong>.</li>
            <li>Wait for the progress bar to finish, or cancel if needed.</li>
            <li>The app saves the test results for that model after it finishes.</li>
            <li>Each model only needs to be tested once unless you add a new version.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3 className="usage-panel-title">5. Fine-Tune the Latest Model Version</h3>
          <p className="helper usage-copy">
            Fine-Tune makes a new version of a model using reviewed images you saved earlier.
          </p>
          <ol className="usage-step-list">
            <li>Open the Settings page and check how many reviewed images are needed before Fine-Tune becomes available.</li>
            <li>Keep reviewing and finalizing runs until you have enough saved images.</li>
            <li>Wait for the app to show that Fine-Tune is available.</li>
            <li>Open the Models page and click <strong>Fine-Tune</strong> on the newest version of that model.</li>
            <li>The app uses saved reviewed images and some older images it already knows.</li>
            <li>When Fine-Tune finishes, the app creates a new model version and removes the used saved images from the list.</li>
            <li>If you cancel Fine-Tune, nothing is saved and the list stays the same.</li>
          </ol>
        </div>

        <div className="panel usage-panel">
          <h3 className="usage-panel-title">6. Export and Share Models</h3>
          <p className="helper usage-copy">
            Exporting saves a model as a shareable zip file so another user can add it to their app.
          </p>
          <ol className="usage-step-list">
            <li>Open the Models page.</li>
            <li>Find the model you want to share.</li>
            <li>Click <strong>Export</strong>.</li>
            <li>The app downloads a zip file with the model file and its information file.</li>
            <li>Share that exported package with another user.</li>
            <li>The other user can then add it to their app with the normal Add Model steps.</li>
          </ol>
        </div>
      </div>

      <div className="usage-subsection">
        <div className="run-header usage-subsection-header">
          <h2>Full Model Training</h2>
          <p className="helper usage-copy">
            Use this process when you need to make a brand-new model family, such as a model for a different mussel
            species or age group. Try to have at least 300 labeled images before fully training a new model. More
            labeled images are usually better.
          </p>
        </div>

        <div className="panel usage-panel usage-drive-panel">
          <h3 className="usage-panel-title">New Model Family Workflow</h3>
          <ol className="usage-step-list">
            <li>
              Label your dataset in Roboflow. There is a video explaining how to use Roboflow in the shared drive inside
              the <strong>Videos/Manuals</strong> folder. Refer to that for details.{" "}
              <button type="button" className="ghost usage-link-btn" onClick={onOpenRoboflow}>
                Link to Roboflow
              </button>
            </li>
            <li>
              After downloading the zip file that holds the labeled images from Roboflow, open the Google Colab notebook and
              follow the directions at the top of the notebook.{" "}
              <button type="button" className="ghost usage-link-btn" onClick={onOpenTrainingCode}>
                Training Code
              </button>
            </li>
            <li>When the notebook finishes, upload your new model and its matching dataset zip to the app with the <strong>Add Model</strong> button.</li>
          </ol>
        </div>
      </div>

      <div className="usage-subsection">
        <div className="run-header usage-subsection-header">
          <h2>Model Sharing</h2>
          <p className="helper usage-copy">
            Use this section to share models between users with the shared Google Drive. This is separate from everyday app
            use and is meant for moving model files and model information files between team members.
          </p>
        </div>

        <div className="panel usage-panel usage-drive-panel">
          <h3 className="usage-panel-title">Shared Google Drive Workflow</h3>
          <button className="ghost usage-link-btn" onClick={onOpenSharedDrive}>
            Open Shared Google Drive
          </button>
          <ol className="usage-step-list">
            <li>Open the shared drive using the button above.</li>
            <li>Use the shared starting model and image folders as the starting point for all users.</li>
            <li>When you want to share a model, export it from the app first.</li>
            <li>Create a new folder on the drive using the model name.</li>
            <li>Upload the exported information file and the model `.pth` or `.pt` file into that folder.</li>
            <li>Other users can then download those files and add the model to their own app.</li>
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
