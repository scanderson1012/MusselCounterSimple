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
import ModelsView from "./views/ModelsView.jsx";
import RunView from "./views/RunView.jsx";

function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [models, setModels] = useState([]);
  const [modelFamilies, setModelFamilies] = useState([]);
  const [trainingDatasets, setTrainingDatasets] = useState([]);
  const [testDatasets, setTestDatasets] = useState([]);
  const [runs, setRuns] = useState([]);
  const [currentRun, setCurrentRun] = useState(null);
  const [pendingImagePaths, setPendingImagePaths] = useState([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [thresholdValue, setThresholdValue] = useState(DEFAULT_THRESHOLD);
  const [isBusy, setIsBusy] = useState(false);
  const [status, setStatus] = useState({ message: "", type: "info" });
  const [loading, setLoading] = useState({ visible: false, processedImages: 0, totalImages: 0 });
  const [route, setCurrentRoute] = useState(() => parseRoute(window.location.hash));
  const [bboxVisible, setBboxVisible] = useState(true);
  const [editingDetection, setEditingDetection] = useState(null);
  const [trainingDatasetForm, setTrainingDatasetForm] = useState({
    name: "",
    images_dir: "",
    labels_dir: "",
    description: "",
  });
  const [testDatasetForm, setTestDatasetForm] = useState({
    name: "",
    images_dir: "",
    labels_dir: "",
    description: "",
  });
  const [modelRegistrationForm, setModelRegistrationForm] = useState({
    source_model_path: "",
    family_name: "",
    training_dataset_id: "",
    test_dataset_id: "",
    notes: "",
  });

  const toErrorMessage = useCallback((error) => String(error?.message ?? error), []);
  const goToRoute = useCallback((targetRoute) => {
    const currentRoute = window.location.hash.replace(/^#/, "");
    if (currentRoute === targetRoute) {
      setCurrentRoute(parseRoute(`#${targetRoute}`));
      return;
    }
    window.location.hash = targetRoute;
  }, []);

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

  const loadModels = useCallback(async () => {
    const response = await apiGet("/models");
    const nextModels = Array.isArray(response.models) ? response.models : [];
    setModels(nextModels);
    return nextModels;
  }, [apiGet]);

  const loadModelRegistry = useCallback(async () => {
    const response = await apiGet("/models/registry");
    const nextFamilies = Array.isArray(response.families) ? response.families : [];
    setModelFamilies(nextFamilies);
    return nextFamilies;
  }, [apiGet]);

  const loadTrainingDatasets = useCallback(async () => {
    const response = await apiGet("/datasets/training");
    const nextDatasets = Array.isArray(response.datasets) ? response.datasets : [];
    setTrainingDatasets(nextDatasets);
    return nextDatasets;
  }, [apiGet]);

  const loadTestDatasets = useCallback(async () => {
    const response = await apiGet("/datasets/test");
    const nextDatasets = Array.isArray(response.datasets) ? response.datasets : [];
    setTestDatasets(nextDatasets);
    return nextDatasets;
  }, [apiGet]);

  const loadRuns = useCallback(async () => {
    const runData = await apiGet("/runs");
    const nextRuns = Array.isArray(runData) ? runData : [];
    setRuns(nextRuns);
    return nextRuns;
  }, [apiGet]);

  const loadRun = useCallback(async (runId) => {
    const runData = await apiGet(`/runs/${runId}`);
    setCurrentRun(runData);
    setThresholdValue(clampThreshold(runData.threshold_score));
    if (runData.model_version_id) {
      setSelectedModelId(String(runData.model_version_id));
    }
    return runData;
  }, [apiGet]);

  const waitForBackend = useCallback(async () => {
    for (let attempt = 1; attempt <= 25; attempt += 1) {
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

  const pollRunJobUntilDone = useCallback(async (runJobId) => {
    while (true) {
      const runJobData = await apiGet(`/predict/run-jobs/${runJobId}`);
      setLoading((previousValue) => ({
        ...previousValue,
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

  useEffect(() => {
    const handleRouteChange = () => {
      setCurrentRoute(parseRoute(window.location.hash));
    };

    if (!window.location.hash) {
      window.location.hash = "/";
    }
    handleRouteChange();
    window.addEventListener("hashchange", handleRouteChange);
    return () => window.removeEventListener("hashchange", handleRouteChange);
  }, []);

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
        const [nextModels] = await Promise.all([
          loadModels(),
          loadModelRegistry(),
          loadTrainingDatasets(),
          loadTestDatasets(),
          loadRuns(),
        ]);

        if (isMounted && nextModels.length > 0) {
          setSelectedModelId((previousValue) => {
            const hasPreviousSelection = nextModels.some((model) => String(model.id) === String(previousValue));
            return hasPreviousSelection ? previousValue : String(nextModels[0].id);
          });
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
  }, [loadModelRegistry, loadModels, loadRuns, loadTestDatasets, loadTrainingDatasets, showStatus, waitForBackend]);

  useEffect(() => {
    if (models.length === 0) {
      setSelectedModelId("");
      return;
    }
    const hasSelectedModel = models.some((model) => String(model.id) === String(selectedModelId));
    if (!hasSelectedModel) {
      setSelectedModelId(String(models[0].id));
    }
  }, [models, selectedModelId]);

  const routedRunId = useMemo(() => {
    if (route.kind === "run" || route.kind === "image") {
      return route.runId || null;
    }
    return null;
  }, [route]);

  useEffect(() => {
    if (!routedRunId) {
      return;
    }
    if (currentRun && currentRun.id === routedRunId) {
      return;
    }
    loadRun(routedRunId).catch(showErrorStatus);
  }, [currentRun, loadRun, routedRunId, showErrorStatus]);

  const detailImage = useMemo(() => {
    if (route.kind !== "image" || !currentRun || currentRun.id !== route.runId) {
      return null;
    }
    return currentRun.images.find((image) => image.run_image_id === route.runImageId) || null;
  }, [currentRun, route]);
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

  const isRunViewVisible = route.kind === "run";
  const isHistoryViewVisible = route.kind === "history";
  const isImageDetailViewVisible = route.kind === "image";
  const isModelsViewVisible = route.kind === "models";

  const { detailImageRef, detailCanvasRef, drawBoundingBoxes, onCanvasClick } = useDetectionCanvas({
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

  const selectedImagesText = useMemo(() => {
    if (pendingImagePaths.length === 0) {
      return "No new images selected.";
    }
    const previewNames = pendingImagePaths.slice(0, 3).map((filePath) => filePath.split(/[/\\]/).pop());
    const overflowCount = pendingImagePaths.length - previewNames.length;
    return `Selected ${pendingImagePaths.length}: ${previewNames.join(", ")}${overflowCount > 0 ? ` (+${overflowCount} more)` : ""}`;
  }, [pendingImagePaths]);

  const totalReadyImages = useMemo(() => {
    const currentRunImages = currentRun ? Number(currentRun.image_count) || 0 : 0;
    return currentRunImages + pendingImagePaths.length;
  }, [currentRun, pendingImagePaths.length]);

  const openRunImage = useCallback((runImageId) => {
    if (currentRun) {
      goToRoute(`/run/${currentRun.id}/image/${runImageId}`);
    }
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
  });

  const currentRunImages = currentRun ? currentRun.images : [];
  const detailCounts = getCountsFromDetections(detailDetections, thresholdValue);
  const detectionsForList = detailDetections.filter((detection) => {
    if (detection.is_deleted) {
      return true;
    }
    return Number(detection.confidence_score) >= thresholdValue;
  });

  const onUpdateDatasetForm = useCallback((formName, fieldName, value) => {
    const setter = formName === "training" ? setTrainingDatasetForm : setTestDatasetForm;
    setter((previousValue) => ({ ...previousValue, [fieldName]: value }));
  }, []);

  const onCreateDataset = useCallback(async (datasetType) => {
    const formValue = datasetType === "training" ? trainingDatasetForm : testDatasetForm;
    const endpoint = datasetType === "training" ? "/datasets/training" : "/datasets/test";
    try {
      const response = await apiPost(endpoint, formValue);
      if (datasetType === "training") {
        setTrainingDatasetForm({ name: "", images_dir: "", labels_dir: "", description: "" });
        await loadTrainingDatasets();
      } else {
        setTestDatasetForm({ name: "", images_dir: "", labels_dir: "", description: "" });
        await loadTestDatasets();
      }
      showStatus(`Saved dataset "${response.dataset?.name || formValue.name}".`, "info");
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiPost, loadTestDatasets, loadTrainingDatasets, showErrorStatus, showStatus, testDatasetForm, trainingDatasetForm]);

  const onUpdateModelForm = useCallback((fieldName, value) => {
    setModelRegistrationForm((previousValue) => ({ ...previousValue, [fieldName]: value }));
  }, []);

  const onRegisterModel = useCallback(async () => {
    try {
      await apiPost("/models/register", {
        ...modelRegistrationForm,
        training_dataset_id: Number(modelRegistrationForm.training_dataset_id),
        test_dataset_id: Number(modelRegistrationForm.test_dataset_id),
      });
      await Promise.all([loadModels(), loadModelRegistry()]);
      setModelRegistrationForm({
        source_model_path: "",
        family_name: "",
        training_dataset_id: "",
        test_dataset_id: "",
        notes: "",
      });
      showStatus("Registered and evaluated baseline model.", "info");
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiPost, loadModelRegistry, loadModels, modelRegistrationForm, showErrorStatus, showStatus]);

  const onDeleteModelVersion = useCallback(async (modelVersionId) => {
    try {
      await apiDelete(`/models/versions/${modelVersionId}`);
      const nextModels = await loadModels();
      await loadModelRegistry();
      setSelectedModelId((previousValue) => {
        if (String(previousValue) !== String(modelVersionId)) {
          return previousValue;
        }
        return nextModels.length > 0 ? String(nextModels[0].id) : "";
      });
      showStatus("Model version deleted.", "info");
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiDelete, loadModelRegistry, loadModels, showErrorStatus, showStatus]);

  const onFinalizeReviewedRun = useCallback(async () => {
    if (!currentRun) {
      showStatus("Open or create a run first.", "error");
      return;
    }

    try {
      const response = await apiPost(`/runs/${currentRun.id}/finalize-review`, {});
      setCurrentRun(response.run);
      await loadModelRegistry();
      showStatus(
        `Finalized reviewed labels: ${response.replay_buffer_summary?.image_count || 0} images and ${response.replay_buffer_summary?.detection_count || 0} boxes saved to the replay buffer.`,
        "info"
      );
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiPost, currentRun, loadModelRegistry, showErrorStatus, showStatus]);

  return (
    <div className="shell">
      <TopBar
        onGoHome={() => goToRoute("/")}
        onGoHistory={() => goToRoute("/history")}
        onGoModels={() => goToRoute("/models")}
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
        selectedModelId={selectedModelId}
        onModelChange={setSelectedModelId}
        thresholdValue={thresholdValue}
        onThresholdChange={(rawValue) => setThresholdValue(clampThreshold(rawValue))}
        onPickImages={onPickImages}
        onRunInference={onRunInference}
        onRecalculate={onRecalculate}
        onFinalizeReviewedRun={onFinalizeReviewedRun}
        isBusy={isBusy}
        selectedImagesText={selectedImagesText}
        currentRunImages={currentRunImages}
        replayBufferSummary={currentRun?.replay_buffer_summary || null}
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

      <ModelsView
        visible={isModelsViewVisible}
        trainingDatasets={trainingDatasets}
        testDatasets={testDatasets}
        modelFamilies={modelFamilies}
        modelForm={modelRegistrationForm}
        datasetForms={{ training: trainingDatasetForm, test: testDatasetForm }}
        onUpdateDatasetForm={onUpdateDatasetForm}
        onCreateTrainingDataset={() => onCreateDataset("training")}
        onCreateTestDataset={() => onCreateDataset("test")}
        onUpdateModelForm={onUpdateModelForm}
        onRegisterModel={onRegisterModel}
        onDeleteModelVersion={onDeleteModelVersion}
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
        onClose={() => setEditingDetection(null)}
        onSetLive={() => editingDetection && updateDetection(editingDetection.id, { class_name: "live" })}
        onSetDead={() => editingDetection && updateDetection(editingDetection.id, { class_name: "dead" })}
        onDelete={() => editingDetection && updateDetection(editingDetection.id, { is_deleted: true })}
      />
    </div>
  );
}

export default App;
