# Stability Checklist

Use this checklist before releases or after major workflow changes.

## Automated Smoke Check

Run:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_check.py
```

This verifies:

- app settings default and update flow
- model registration into a clean temporary app database
- run creation and image ingestion
- replay-buffer finalization
- replay-buffer consumption bookkeeping for fine-tuning
- fine-tuned version registration
- rollback behavior when deleting a newer version

## Manual UI Checks

### Run Flow

- Start a new run and verify image upload still works.
- Run inference on at least one image.
- Change the threshold and verify counts recompute without crashing.
- Delete one image from a run and verify counts refresh.
- Delete all images from a run and verify the run stays stable.

### Detection Editing

- Open an image detail page and relabel a detection.
- Delete a detection and verify counts update.
- Add a new bounding box and save it as both `live` and `dead` in separate runs.
- Try drawing a tiny box and verify the app blocks it cleanly.

### Replay Buffer

- Finalize a reviewed run and verify the replay-buffer summary updates.
- Finalize the same run again after edits and verify the replay-buffer snapshot refreshes cleanly.
- Remove a run image before fine-tuning and verify the replay-buffer summary stays consistent.

### Model Registration

- Register a model with valid train/test dataset paths.
- Try registering with missing required fields and verify the app shows readable messages.
- Open the model information document and verify the description/dataset sections render correctly.
- Export a model and verify the zip contains the checkpoint and HTML report.

### Evaluation

- Start `Evaluate on Test Set` and verify progress/ETA update.
- Cancel evaluation and verify the loading panel disappears quickly.
- Re-run evaluation on the same version and verify the app blocks duplicate evaluation.

### Fine-Tuning

- Verify the global banner appears only when the latest model has enough pending replay-buffer images.
- Attempt fine-tuning below the threshold and verify the app shows a plain-language message.
- Start fine-tuning on the latest version and verify progress/ETA update.
- Cancel fine-tuning and verify no new version is created.
- Complete fine-tuning and verify:
  - a new version appears
  - the consumed replay-buffer images disappear from the active buffer
  - leftover replay-buffer images remain pending
- Open a consumed image from an older run and verify it is read-only.

### Version Deletion and Rollback

- Verify the baseline model cannot be deleted.
- Delete the latest non-baseline version and verify replay-buffer images consumed by that version are restored to the previous latest version.
- Delete a middle version and verify later versions are also removed.
- Delete `v1` on a non-baseline family and verify it behaves like deleting the full family.

### Settings

- Change fine-tuning settings and restart the app.
- Verify settings persist and the fine-tuning banner threshold updates correctly.

## Residual Risks To Watch

- Actual long-running GPU fine-tuning behavior still depends on the local machine, CUDA install, and checkpoint compatibility.
- Manual UI checks are still needed for end-to-end training and evaluation timing behavior.
- Packaged desktop builds should be smoke-tested separately from development mode.
