import { useCallback } from "react";
import { clampThreshold } from "../lib/app-utils.js";

/**
 * Handles run actions like start run, recalculate, and image/model updates.
 */
function useRunActions({
  apiGet,
  apiPost,
  apiDelete,
  loadModels,
  loadModelRegistry,
  loadRuns,
  pollRunJobUntilDone,
  showStatus,
  currentRun,
  pendingImagePaths,
  selectedModelId,
  thresholdValue,
  setCurrentRun,
  setPendingImagePaths,
  setThresholdValue,
  setSelectedModelId,
  setIsBusy,
  setLoading,
  setEditingDetection,
  goToRoute,
  onOpenAddModelModal,
}) {
  // Reset to a fresh run workspace and navigate back to the run page.
  const onStartNewRun = useCallback(() => {
    setCurrentRun(null);
    setPendingImagePaths([]);
    setEditingDetection(null);
    goToRoute("/");
  }, [setCurrentRun, setPendingImagePaths, setEditingDetection, goToRoute]);

  // Open native file picker for models, then refresh model list.
  const onAddModel = useCallback(async () => {
    onOpenAddModelModal();
  }, [onOpenAddModelModal]);

  // Open native file picker for images and merge with pending set.
  const onPickImages = useCallback(async () => {
    try {
      const selectedPaths = await window.desktopAPI.pickImagePaths();
      setPendingImagePaths((previousPaths) => Array.from(new Set([...previousPaths, ...selectedPaths])));
    } catch (error) {
      showStatus(String(error.message ?? error), "error");
    }
  }, [setPendingImagePaths, showStatus]);

  // Start a model run and wait if backend returns a run-job ID.
  const onRunInference = useCallback(async () => {
    if (!selectedModelId) {
      showStatus("No model selected. Register a baseline model first.", "error");
      return;
    }

    if (!currentRun && pendingImagePaths.length === 0) {
      showStatus("Select at least one image to start a new run.", "error");
      return;
    }

    setIsBusy(true);
    setLoading({
      visible: true,
      processedImages: 0,
      totalImages: 0,
      message: "Running model...",
      estimatedRemainingSeconds: null,
      canCancel: false,
      onCancel: null,
    });
    showStatus("Running model...", "info");

    try {
      const predictStartData = await apiPost("/predict", {
        run_id: currentRun ? currentRun.id : null,
        image_ids: [],
        image_paths: pendingImagePaths,
        model_version_id: Number(selectedModelId),
        threshold_score: thresholdValue,
      });

      let predictionData = predictStartData;
      // For longer runs, keep checking progress until done.
      if (predictStartData.run_job_id && predictStartData.status !== "completed") {
        predictionData = await pollRunJobUntilDone(predictStartData.run_job_id);
      }

      if (predictionData.status === "failed") {
        throw new Error(predictionData.error_message || "Run job failed.");
      }

      if (!predictionData.run) {
        throw new Error("Model run finished without run data.");
      }

      setCurrentRun(predictionData.run);
      setPendingImagePaths([]);
      setThresholdValue(clampThreshold(predictionData.run.threshold_score));
      await loadRuns();
      goToRoute(`/run/${predictionData.run.id}`);

      const skippedImageIds = Array.isArray(predictionData.skipped_image_ids)
        ? predictionData.skipped_image_ids.length
        : 0;
      const skippedImages = Array.isArray(predictionData.skipped_images)
        ? predictionData.skipped_images.length
        : 0;
      const skippedCount = skippedImageIds + skippedImages;
      const processedCount = Array.isArray(predictionData.processed_run_image_ids)
        ? predictionData.processed_run_image_ids.length
        : 0;

      showStatus(
        `Inference complete. Processed ${processedCount} run-image rows. Skipped ${skippedCount}.`,
        "info"
      );
    } catch (error) {
      showStatus(String(error.message ?? error), "error");
    } finally {
      setLoading({
        visible: false,
        processedImages: 0,
        totalImages: 0,
        message: "",
        estimatedRemainingSeconds: null,
        canCancel: false,
        onCancel: null,
      });
      setIsBusy(false);
    }
  }, [
    apiPost,
    currentRun,
    loadRuns,
    pendingImagePaths,
    pollRunJobUntilDone,
    selectedModelId,
    setCurrentRun,
    goToRoute,
    setIsBusy,
    setLoading,
    setPendingImagePaths,
    setThresholdValue,
    showStatus,
    thresholdValue,
  ]);

  // Recompute counts and detection visibility using the new threshold.
  const onRecalculate = useCallback(async () => {
    if (!currentRun) {
      showStatus("Open or create a run first.", "error");
      return;
    }

    setIsBusy(true);
    showStatus("Recalculating counts...", "info");

    try {
      const recalculateResponse = await apiPost("/recalculate", {
        run_id: currentRun.id,
        threshold_score: thresholdValue,
      });

      setCurrentRun(recalculateResponse.run);
      await loadRuns();
      showStatus("Recalculation complete.", "info");
    } catch (error) {
      showStatus(String(error.message ?? error), "error");
    } finally {
      setIsBusy(false);
    }
  }, [apiPost, currentRun, loadRuns, setCurrentRun, setIsBusy, showStatus, thresholdValue]);

  // Remove one image from the current run and refresh run summary/history.
  const onRemoveImageFromRun = useCallback(async (runImageId) => {
    if (!currentRun) {
      return;
    }

    try {
      const response = await apiDelete(`/runs/${currentRun.id}/images/${runImageId}`);
      setCurrentRun(response.run);
      await loadRuns();
      await loadModelRegistry();
      showStatus("Image removed from run.", "info");
    } catch (error) {
      showStatus(String(error.message ?? error), "error");
    }
  }, [apiDelete, currentRun, loadModelRegistry, loadRuns, setCurrentRun, showStatus]);

  // Remove every image from the current run in sequence.
  const onRemoveAllImagesFromRun = useCallback(async () => {
    if (!currentRun || currentRun.images.length === 0) {
      return;
    }

    const runImageIds = currentRun.images.map((image) => image.run_image_id);
    try {
      for (const runImageId of runImageIds) {
        // eslint-disable-next-line no-await-in-loop
        await apiDelete(`/runs/${currentRun.id}/images/${runImageId}`);
      }

      const refreshedRun = await apiGet(`/runs/${currentRun.id}`);
      setCurrentRun(refreshedRun);
      await loadRuns();
      await loadModelRegistry();
      showStatus(`Removed ${runImageIds.length} images from run.`, "info");
    } catch (error) {
      showStatus(String(error.message ?? error), "error");
    }
  }, [apiDelete, apiGet, currentRun, loadModelRegistry, loadRuns, setCurrentRun, showStatus]);

  return {
    onStartNewRun,
    onAddModel,
    onPickImages,
    onRunInference,
    onRecalculate,
    onRemoveImageFromRun,
    onRemoveAllImagesFromRun,
  };
}

export default useRunActions;
