import { useCallback, useEffect, useMemo, useState } from "react";
import {
  DEFAULT_THRESHOLD,
  RUN_JOB_POLL_INTERVAL_MS,
  clampThreshold,
  formatRunDisplayName,
  getCountsFromDetections,
  parseRoute,
  waitMilliseconds,
} from "./lib/app-utils.js";
import DetectionModal from "./components/DetectionModal.jsx";
import LoadingBar from "./components/LoadingBar.jsx";
import StatusBanner from "./components/StatusBanner.jsx";
import TopBar from "./components/TopBar.jsx";
import useDetectionCanvas from "./hooks/useDetectionCanvas.js";
import useRunActions from "./hooks/useRunActions.js";
import HistoryView from "./views/HistoryView.jsx";
import ImageDetailView from "./views/ImageDetailView.jsx";
import RunView from "./views/RunView.jsx";

/**
 * Main app component.
 * Keeps shared state, loads backend data, and renders each page.
 */
function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [models, setModels] = useState([]);
  const [runs, setRuns] = useState([]);
  const [currentRun, setCurrentRun] = useState(null);
  const [pendingImagePaths, setPendingImagePaths] = useState([]);
  const [selectedModelFileName, setSelectedModelFileName] = useState("");
  const [thresholdValue, setThresholdValue] = useState(DEFAULT_THRESHOLD);
  const [isBusy, setIsBusy] = useState(false);
  const [status, setStatus] = useState({ message: "", type: "info" });
  const [loading, setLoading] = useState({ visible: false, processedImages: 0, totalImages: 0 });
  const [route, setCurrentRoute] = useState(() => parseRoute(window.location.hash));
  const [bboxVisible, setBboxVisible] = useState(true);
  const [editingDetection, setEditingDetection] = useState(null);

  const toErrorMessage = useCallback((error) => String(error?.message ?? error), []);

  // Navigate by updating the URL hash (for example, "#/history").
  const goToRoute = useCallback((targetRoute) => {
    const currentRoute = window.location.hash.replace(/^#/, "");
    if (currentRoute === targetRoute) {
      setCurrentRoute(parseRoute(`#${targetRoute}`));
      return;
    }
    window.location.hash = targetRoute;
  }, []);

  // Small API helpers used by hooks and page actions.
  const apiGet = useCallback(async (apiPath) => window.desktopAPI.apiGet(apiPath), []);
  const apiPost = useCallback(async (apiPath, body) => window.desktopAPI.apiPost(apiPath, body), []);
  const apiPatch = useCallback(async (apiPath, body) => window.desktopAPI.apiPatch(apiPath, body), []);
  const apiDelete = useCallback(async (apiPath) => window.desktopAPI.apiDelete(apiPath), []);

  const runImageUrl = useCallback((relativePath) => {
    if (!relativePath) {
      return "";
    }
    return `${apiBaseUrl}${relativePath}`;
  }, [apiBaseUrl]);

  const showStatus = useCallback((message, type = "info") => {
    if (!message) {
      setStatus({ message: "", type: "info" });
      return;
    }
    setStatus({ message: String(message), type });
  }, []);

  const showErrorStatus = useCallback((error) => {
    showStatus(toErrorMessage(error), "error");
  }, [showStatus, toErrorMessage]);

  // Load model options shown in the run settings model dropdown.
  const loadModels = useCallback(async () => {
    const modelsResponse = await apiGet("/models");
    const nextModels = Array.isArray(modelsResponse.models) ? modelsResponse.models : [];
    setModels(nextModels);
    return nextModels;
  }, [apiGet]);

  // Load run history used by the Prediction History page.
  const loadRuns = useCallback(async () => {
    const runData = await apiGet("/runs");
    const nextRuns = Array.isArray(runData) ? runData : [];
    setRuns(nextRuns);
    return nextRuns;
  }, [apiGet]);

  // Load one run by ID, then sync selected model + threshold controls.
  const loadRun = useCallback(async (runId) => {
    const runData = await apiGet(`/runs/${runId}`);
    setCurrentRun(runData);
    setThresholdValue(clampThreshold(runData.threshold_score));
    if (runData.model_file_name) {
      setSelectedModelFileName(runData.model_file_name);
    }
    return runData;
  }, [apiGet]);

  // Wait for backend before loading models and runs.
  const waitForBackend = useCallback(async () => {
    const maxAttempts = 25;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        if (window.desktopAPI.isBackendReady) {
          const isReady = await window.desktopAPI.isBackendReady();
          if (isReady) {
            return;
          }
        } else {
          await apiGet("/models");
          return;
        }
      } catch {
        // Keep trying until timeout.
      }
      await waitMilliseconds(300);
    }
    throw new Error("Backend did not become ready in time.");
  }, [apiGet]);

  // Keep checking run-job status until it finishes.
  const pollRunJobUntilDone = useCallback(async (runJobId) => {
    while (true) {
      const runJobData = await apiGet(`/predict/run-jobs/${runJobId}`);
      setLoading((previousLoading) => ({
        ...previousLoading,
        processedImages: Number(runJobData.processed_images) || 0,
        totalImages: Number(runJobData.total_images) || 0,
      }));

      if (runJobData.status === "completed") {
        return runJobData;
      }
      if (runJobData.status === "failed") {
        throw new Error(runJobData.error_message || "Run job failed.");
      }
      await waitMilliseconds(RUN_JOB_POLL_INTERVAL_MS);
    }
  }, [apiGet]);

  // Keep route state in sync with browser hash changes.
  useEffect(() => {
    const handleRouteChange = () => {
      setCurrentRoute(parseRoute(window.location.hash));
    };

    if (!window.location.hash) {
      window.location.hash = "/";
    }
    handleRouteChange();

    window.addEventListener("hashchange", handleRouteChange);
    return () => {
      window.removeEventListener("hashchange", handleRouteChange);
    };
  }, []);

  // Boot sequence: connect backend, then load models + runs for first paint.
  useEffect(() => {
    let isMounted = true;

    async function initializeApp() {
      try {
        const backendBaseUrl = await window.desktopAPI.getApiBaseUrl();
        if (!isMounted) {
          return;
        }

        setApiBaseUrl(backendBaseUrl);
        await waitForBackend();

        const [nextModels] = await Promise.all([loadModels(), loadRuns()]);

        if (isMounted && nextModels.length > 0) {
          setSelectedModelFileName((previousSelection) => {
            const hasPreviousSelection = nextModels.some((model) => model.model_file_name === previousSelection);
            if (hasPreviousSelection) {
              return previousSelection;
            }
            return nextModels[0].model_file_name;
          });
        }

        if (isMounted) {
          showStatus("Ready.", "info");
        }
      } catch (error) {
        if (isMounted) {
          showStatus(String(error.message ?? error), "error");
        }
      }
    }

    initializeApp();

    return () => {
      isMounted = false;
    };
  }, [loadModels, loadRuns, showStatus, waitForBackend]);

  // Ensure selected model always points to a currently available model option.
  useEffect(() => {
    if (models.length === 0) {
      setSelectedModelFileName("");
      return;
    }

    const hasSelectedModel = models.some((model) => model.model_file_name === selectedModelFileName);
    if (!hasSelectedModel) {
      setSelectedModelFileName(models[0].model_file_name);
    }
  }, [models, selectedModelFileName]);

  const routedRunId = useMemo(() => {
    if (route.kind === "run" || route.kind === "image") {
      return route.runId || null;
    }
    return null;
  }, [route]);

  // Load run data for the current route when needed.
  useEffect(() => {
    if (!routedRunId) {
      return;
    }
    if (currentRun && currentRun.id === routedRunId) {
      return;
    }

    loadRun(routedRunId).catch((error) => {
      showErrorStatus(error);
    });
  }, [currentRun, loadRun, routedRunId, showErrorStatus]);

  // Active image detail object for the current route.
  const detailImage = useMemo(() => {
    if (route.kind !== "image" || !currentRun || currentRun.id !== route.runId) {
      return null;
    }
    return currentRun.images.find((image) => image.run_image_id === route.runImageId) || null;
  }, [currentRun, route]);

  // Detection list for image-detail panel and overlay drawing.
  const detailDetections = useMemo(() => detailImage?.detections || [], [detailImage]);

  useEffect(() => {
    if (route.kind === "image" && !detailImage && currentRun && currentRun.id === route.runId) {
      showStatus("Image not found in run.", "error");
    }
  }, [currentRun, detailImage, route, showStatus]);

  const updateDetection = useCallback(async (detectionId, fields) => {
    try {
      const response = await apiPatch(`/detections/${detectionId}`, fields);
      setCurrentRun(response.run);
      setEditingDetection(null);
      await loadRuns();
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiPatch, loadRuns, showErrorStatus]);

  // Route-derived visibility flags used by split view components.
  const isRunViewVisible = route.kind === "run";
  const isHistoryViewVisible = route.kind === "history";
  const isImageDetailViewVisible = route.kind === "image";

  const {
    detailImageRef,
    detailCanvasRef,
    drawBoundingBoxes,
    onCanvasClick,
  } = useDetectionCanvas({
    isImageDetailVisible: isImageDetailViewVisible,
    currentRun,
    detailImage,
    detailDetections,
    thresholdValue,
    bboxVisible,
    onDetectionHit: setEditingDetection,
  });

  const runSummary = useMemo(() => {
    if (!currentRun) {
      return {
        runMetaText: "Prediction History: New run",
        currentRunTitle: "New run",
        imagesCount: 0,
        liveCount: 0,
        deadCount: 0,
        totalCount: 0,
      };
    }

    return {
      runMetaText: `Prediction History: ${formatRunDisplayName(currentRun)}`,
      currentRunTitle: `Run #${currentRun.id}`,
      imagesCount: Number(currentRun.image_count) || 0,
      liveCount: Number(currentRun.live_mussel_count) || 0,
      deadCount: Number(currentRun.dead_mussel_count) || 0,
      totalCount: Number(currentRun.total_mussels) || 0,
    };
  }, [currentRun]);

  // Friendly summary of current pending file selection.
  const selectedImagesText = useMemo(() => {
    if (pendingImagePaths.length === 0) {
      return "No new images selected.";
    }

    const previewNames = pendingImagePaths
      .slice(0, 3)
      .map((filePath) => filePath.split(/[/\\]/).pop());

    const overflowCount = pendingImagePaths.length - previewNames.length;
    const overflowText = overflowCount > 0 ? ` (+${overflowCount} more)` : "";
    return `Selected ${pendingImagePaths.length}: ${previewNames.join(", ")}${overflowText}`;
  }, [pendingImagePaths]);

  // Current run images + pending images waiting to be submitted.
  const totalReadyImages = useMemo(() => {
    const currentRunImages = currentRun ? Number(currentRun.image_count) || 0 : 0;
    return currentRunImages + pendingImagePaths.length;
  }, [currentRun, pendingImagePaths.length]);

  const openRunImage = useCallback((runImageId) => {
    if (!currentRun) {
      return;
    }
    goToRoute(`/run/${currentRun.id}/image/${runImageId}`);
  }, [currentRun, goToRoute]);

  const backToRunOrHome = useCallback(() => {
    if (currentRun) {
      goToRoute(`/run/${currentRun.id}`);
      return;
    }
    goToRoute("/");
  }, [currentRun, goToRoute]);

  const {
    onStartNewRun,
    onAddModel,
    onPickImages,
    onRunInference,
    onRecalculate,
    onRemoveImageFromRun,
    onRemoveAllImagesFromRun,
  } = useRunActions({
    apiGet,
    apiPost,
    apiDelete,
    loadModels,
    loadRuns,
    pollRunJobUntilDone,
    showStatus,
    currentRun,
    pendingImagePaths,
    selectedModelFileName,
    thresholdValue,
    setCurrentRun,
    setPendingImagePaths,
    setThresholdValue,
    setSelectedModelFileName,
    setIsBusy,
    setLoading,
    setEditingDetection,
    goToRoute,
  });

  const currentRunImages = currentRun ? currentRun.images : [];
  const detailCounts = getCountsFromDetections(detailDetections, thresholdValue);
  const detectionsForList = detailDetections.filter((detection) => {
    if (detection.is_deleted) {
      return true;
    }
    return Number(detection.confidence_score) >= thresholdValue;
  });

  const onThresholdChange = useCallback((rawValue) => {
    setThresholdValue(clampThreshold(rawValue));
  }, []);

  const onCloseDetectionModal = useCallback(() => {
    setEditingDetection(null);
  }, []);

  const onSetDetectionClass = useCallback((className) => {
    if (!editingDetection) {
      return;
    }
    updateDetection(editingDetection.id, { class_name: className });
  }, [editingDetection, updateDetection]);

  const onDeleteDetection = useCallback(() => {
    if (!editingDetection) {
      return;
    }
    updateDetection(editingDetection.id, { is_deleted: true });
  }, [editingDetection, updateDetection]);

  return (
    <div className="shell">
      <TopBar
        onGoHome={() => goToRoute("/")}
        onGoHistory={() => goToRoute("/history")}
        onAddModel={onAddModel}
        onStartNewRun={onStartNewRun}
      />

      <StatusBanner status={status} />
      <LoadingBar loading={loading} />

      <RunView
        visible={isRunViewVisible}
        runSummary={runSummary}
        totalReadyImages={totalReadyImages}
        models={models}
        selectedModelFileName={selectedModelFileName}
        onModelChange={setSelectedModelFileName}
        thresholdValue={thresholdValue}
        onThresholdChange={onThresholdChange}
        onPickImages={onPickImages}
        onRunInference={onRunInference}
        onRecalculate={onRecalculate}
        isBusy={isBusy}
        selectedImagesText={selectedImagesText}
        currentRunImages={currentRunImages}
        onDeleteAllImages={onRemoveAllImagesFromRun}
        onOpenImage={openRunImage}
        onRemoveImage={onRemoveImageFromRun}
        runImageUrl={runImageUrl}
      />

      <HistoryView
        visible={isHistoryViewVisible}
        runs={runs}
        runImageUrl={runImageUrl}
        onOpenRun={(runId) => goToRoute(`/run/${runId}`)}
      />

      <ImageDetailView
        visible={isImageDetailViewVisible}
        currentRun={currentRun}
        detailImage={detailImage}
        bboxVisible={bboxVisible}
        onToggleBboxVisible={setBboxVisible}
        detailImageRef={detailImageRef}
        detailCanvasRef={detailCanvasRef}
        runImageUrl={runImageUrl}
        onImageLoad={drawBoundingBoxes}
        onCanvasClick={onCanvasClick}
        detailCounts={detailCounts}
        detectionsForList={detectionsForList}
        onOpenDetection={setEditingDetection}
        onBack={backToRunOrHome}
      />

      <footer className="app-credit">
        Made by Nate Williams, Austin Ashley, Fernando Gomez, Siddharth Rakshit
      </footer>

      <DetectionModal
        detection={editingDetection}
        onClose={onCloseDetectionModal}
        onSetLive={() => onSetDetectionClass("live")}
        onSetDead={() => onSetDetectionClass("dead")}
        onDelete={onDeleteDetection}
      />
    </div>
  );
}

export default App;
