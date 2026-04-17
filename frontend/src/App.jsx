import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import HelpTooltip from "./components/HelpTooltip.jsx";
import LoadingBar from "./components/LoadingBar.jsx";
import StatusBanner from "./components/StatusBanner.jsx";
import TopBar from "./components/TopBar.jsx";
import useDetectionCanvas from "./hooks/useDetectionCanvas.js";
import useRunActions from "./hooks/useRunActions.js";
import HistoryView from "./views/HistoryView.jsx";
import ImageDetailView from "./views/ImageDetailView.jsx";
import ModelsView from "./views/ModelsView.jsx";
import RunView from "./views/RunView.jsx";
import SettingsView from "./views/SettingsView.jsx";
import UsageView from "./views/UsageView.jsx";

function App() {
  const statusTimeoutRef = useRef(null);
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
  const [loading, setLoading] = useState({
    visible: false,
    processedImages: 0,
    totalImages: 0,
    message: "",
    estimatedRemainingSeconds: null,
    canCancel: false,
    onCancel: null,
  });
  const [route, setCurrentRoute] = useState(() => parseRoute(window.location.hash));
  const [bboxVisible, setBboxVisible] = useState(true);
  const [editingDetection, setEditingDetection] = useState(null);
  const [isDrawingBox, setIsDrawingBox] = useState(false);
  const [draftDetection, setDraftDetection] = useState(null);
  const [isAddModelModalOpen, setIsAddModelModalOpen] = useState(false);
  const [isSubmittingModel, setIsSubmittingModel] = useState(false);
  const [modelReport, setModelReport] = useState(null);
  const [appSettings, setAppSettings] = useState({
    fine_tune_min_new_images: 10,
    fine_tune_num_epochs: 5,
    compute_mode: "automatic",
    gpu_upgrade_prompt_seen: false,
  });
  const [draftAppSettings, setDraftAppSettings] = useState({
    fine_tune_min_new_images: "10",
    fine_tune_num_epochs: "5",
    compute_mode: "automatic",
  });
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [computeStatus, setComputeStatus] = useState(null);
  const [isGpuUpgradePromptOpen, setIsGpuUpgradePromptOpen] = useState(false);
  const [modelRegistrationForm, setModelRegistrationForm] = useState({
    source_model_path: "",
    selected_model_file_name: "",
    family_name: "",
    description: "",
    training_images_dir: "",
    training_labels_dir: "",
    test_images_dir: "",
    test_labels_dir: "",
    notes: "",
  });

  const toErrorMessage = useCallback((error) => {
    const rawMessage = String(error?.message ?? error ?? "");
    const requestFailureMatch = rawMessage.match(/^Request failed \([^)]+\):\s*(.+)$/);
    if (requestFailureMatch) {
      return requestFailureMatch[1];
    }
    return rawMessage;
  }, []);
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
    if (statusTimeoutRef.current) {
      window.clearTimeout(statusTimeoutRef.current);
      statusTimeoutRef.current = null;
    }
    if (!message) {
      setStatus({ message: "", type: "info" });
      return;
    }
    setStatus({ message: String(message), type });
    statusTimeoutRef.current = window.setTimeout(() => {
      setStatus({ message: "", type: "info" });
      statusTimeoutRef.current = null;
    }, 5000);
  }, []);

  useEffect(() => () => {
    if (statusTimeoutRef.current) {
      window.clearTimeout(statusTimeoutRef.current);
    }
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

  const loadSettings = useCallback(async () => {
    const response = await apiGet("/settings");
    const nextSettings = response.settings || {};
    const normalizedSettings = {
      fine_tune_min_new_images: Number(nextSettings.fine_tune_min_new_images) || 10,
      fine_tune_num_epochs: Number(nextSettings.fine_tune_num_epochs) || 5,
      compute_mode: nextSettings.compute_mode || "automatic",
      gpu_upgrade_prompt_seen: Boolean(nextSettings.gpu_upgrade_prompt_seen),
    };
    setAppSettings(normalizedSettings);
    setDraftAppSettings({
      fine_tune_min_new_images: String(normalizedSettings.fine_tune_min_new_images),
      fine_tune_num_epochs: String(normalizedSettings.fine_tune_num_epochs),
      compute_mode: normalizedSettings.compute_mode,
    });
    return normalizedSettings;
  }, [apiGet]);

  const loadComputeStatus = useCallback(async () => {
    const response = await apiGet("/compute/status");
    const nextComputeStatus = response.compute_status || null;
    setComputeStatus(nextComputeStatus);
    return nextComputeStatus;
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
        estimatedRemainingSeconds: runJobData.estimated_remaining_seconds,
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

  const pollModelJobUntilDone = useCallback(async (modelJobId) => {
    while (true) {
      const modelJobData = await apiGet(`/models/jobs/${modelJobId}`);
      setLoading((previousValue) => ({
        ...previousValue,
        processedImages: Number(modelJobData.processed_images) || 0,
        totalImages: Number(modelJobData.total_images) || 0,
        message: modelJobData.stage || "Evaluating model...",
        estimatedRemainingSeconds: modelJobData.estimated_remaining_seconds,
        canCancel: modelJobData.status === "running",
      }));

      if (modelJobData.status === "completed") {
        return modelJobData;
      }
      if (modelJobData.status === "cancelling") {
        await waitMilliseconds(RUN_JOB_POLL_INTERVAL_MS);
        continue;
      }
      if (modelJobData.status === "cancelled") {
        return modelJobData;
      }
      if (modelJobData.status === "failed") {
        throw new Error(modelJobData.error_message || "Model job failed.");
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
        const [
          nextModels,
          _nextFamilies,
          _nextTrainingDatasets,
          _nextTestDatasets,
          _nextRuns,
          nextSettings,
          nextComputeStatus,
        ] = await Promise.all([
          loadModels(),
          loadModelRegistry(),
          loadTrainingDatasets(),
          loadTestDatasets(),
          loadRuns(),
          loadSettings(),
          loadComputeStatus(),
        ]);

        if (isMounted && nextModels.length > 0) {
          setSelectedModelId((previousValue) => {
            const hasPreviousSelection = nextModels.some((model) => String(model.id) === String(previousValue));
            return hasPreviousSelection ? previousValue : String(nextModels[0].id);
          });
          showStatus("Ready.", "info");
        }
        if (
          isMounted &&
          nextSettings &&
          !nextSettings.gpu_upgrade_prompt_seen &&
          nextComputeStatus?.compatible_gpu_detected
        ) {
          setIsGpuUpgradePromptOpen(true);
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
  }, [loadComputeStatus, loadModelRegistry, loadModels, loadRuns, loadSettings, loadTestDatasets, loadTrainingDatasets, showStatus, waitForBackend]);

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

  useEffect(() => {
    setDraftDetection(null);
    setIsDrawingBox(false);
  }, [route.kind, detailImage?.run_image_id]);

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

  const createDetection = useCallback(async (runImageId, payload) => {
    try {
      const response = await apiPost(`/run-images/${runImageId}/detections`, payload);
      setCurrentRun(response.run);
      setDraftDetection(null);
      setIsDrawingBox(false);
      await loadRuns();
      showStatus("New detection box saved.", "info");
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiPost, loadRuns, showErrorStatus, showStatus]);

  const isRunViewVisible = route.kind === "run";
  const isHistoryViewVisible = route.kind === "history";
  const isImageDetailViewVisible = route.kind === "image";
  const isModelsViewVisible = route.kind === "models";
  const isSettingsViewVisible = route.kind === "settings";
  const isUsageViewVisible = route.kind === "usage";

  const openAddModelModal = useCallback(() => {
    setIsAddModelModalOpen(true);
    goToRoute("/models");
  }, [goToRoute]);

  const closeAddModelModal = useCallback(() => {
    if (isSubmittingModel) {
      return;
    }
    setIsAddModelModalOpen(false);
  }, [isSubmittingModel]);

  const {
    detailImageRef,
    detailCanvasRef,
    drawBoundingBoxes,
    onCanvasClick,
    onCanvasMouseDown,
    onCanvasMouseMove,
    onCanvasMouseUp,
  } = useDetectionCanvas({
    isDrawingBox,
    isImageDetailVisible: isImageDetailViewVisible,
    currentRun,
    detailImage,
    detailDetections,
    thresholdValue,
    bboxVisible,
    onDetectionHit: setEditingDetection,
    draftDetection,
    onDraftDetectionChange: setDraftDetection,
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
    onOpenAddModelModal: openAddModelModal,
  });

  const currentRunImages = currentRun ? currentRun.images : [];
  const detailCounts = getCountsFromDetections(detailDetections, thresholdValue);
  const detectionsForList = detailDetections.filter((detection) => {
    if (detection.is_deleted) {
      return true;
    }
    return detection.confidence_score == null || Number(detection.confidence_score) >= thresholdValue;
  });

  const onUpdateModelForm = useCallback((fieldName, value) => {
    setModelRegistrationForm((previousValue) => ({ ...previousValue, [fieldName]: value }));
  }, []);

  const onChangeAppSetting = useCallback((fieldName, value) => {
    setDraftAppSettings((previousValue) => ({ ...previousValue, [fieldName]: value }));
  }, []);

  const updateComputePreference = useCallback(async (nextComputeMode, promptSeen) => {
    const response = await apiPatch("/settings", {
      compute_mode: nextComputeMode,
      gpu_upgrade_prompt_seen: promptSeen,
    });
    const nextSettings = response.settings || {};
    setAppSettings((previousValue) => ({
      ...previousValue,
      compute_mode: nextSettings.compute_mode || nextComputeMode,
      gpu_upgrade_prompt_seen: Boolean(nextSettings.gpu_upgrade_prompt_seen),
    }));
    setDraftAppSettings((previousValue) => ({
      ...previousValue,
      compute_mode: nextSettings.compute_mode || nextComputeMode,
    }));
    return loadComputeStatus();
  }, [apiPatch, loadComputeStatus]);

  const onEnableGpuPreference = useCallback(async () => {
    try {
      const nextComputeStatus = await updateComputePreference("gpu_if_available", true);
      setIsGpuUpgradePromptOpen(false);
      if (nextComputeStatus?.gpu_runtime_ready) {
        showStatus("GPU preference enabled. The app will use the GPU when possible.", "info");
      } else {
        showStatus(
          "GPU preference saved. This app build will continue on CPU until optional GPU runtime support is installed.",
          "info",
        );
      }
    } catch (error) {
      showErrorStatus(error);
    }
  }, [showErrorStatus, showStatus, updateComputePreference]);

  const onKeepCpuForNow = useCallback(async () => {
    try {
      await updateComputePreference(appSettings.compute_mode || "automatic", true);
      setIsGpuUpgradePromptOpen(false);
      showStatus("The app will stay on CPU for now. You can change this later in Settings.", "info");
    } catch (error) {
      showErrorStatus(error);
    }
  }, [appSettings.compute_mode, showErrorStatus, showStatus, updateComputePreference]);

  const onSaveSettings = useCallback(async () => {
    try {
      setIsSavingSettings(true);
      const payload = {
        fine_tune_min_new_images: Math.max(1, Number(draftAppSettings.fine_tune_min_new_images) || 1),
        fine_tune_num_epochs: Math.max(1, Number(draftAppSettings.fine_tune_num_epochs) || 1),
        compute_mode: draftAppSettings.compute_mode || "automatic",
        gpu_upgrade_prompt_seen: Boolean(appSettings.gpu_upgrade_prompt_seen),
      };
      const response = await apiPatch("/settings", payload);
      const nextSettings = response.settings || payload;
      setAppSettings({
        fine_tune_min_new_images: Number(nextSettings.fine_tune_min_new_images) || payload.fine_tune_min_new_images,
        fine_tune_num_epochs: Number(nextSettings.fine_tune_num_epochs) || payload.fine_tune_num_epochs,
        compute_mode: nextSettings.compute_mode || payload.compute_mode,
        gpu_upgrade_prompt_seen: Boolean(nextSettings.gpu_upgrade_prompt_seen),
      });
      setDraftAppSettings({
        fine_tune_min_new_images: String(nextSettings.fine_tune_min_new_images || payload.fine_tune_min_new_images),
        fine_tune_num_epochs: String(nextSettings.fine_tune_num_epochs || payload.fine_tune_num_epochs),
        compute_mode: nextSettings.compute_mode || payload.compute_mode,
      });
      await loadComputeStatus();
      showStatus("Settings saved.", "info");
      await loadModelRegistry();
    } catch (error) {
      showErrorStatus(error);
    } finally {
      setIsSavingSettings(false);
    }
  }, [apiPatch, appSettings.gpu_upgrade_prompt_seen, draftAppSettings, loadComputeStatus, loadModelRegistry, showErrorStatus, showStatus]);

  const onChooseModelFile = useCallback(async () => {
    try {
      const result = await window.desktopAPI.pickModelFile();
      if (!result) {
        return;
      }
      const defaultName = String(result.fileName || "").replace(/\.[^.]+$/, "");
      setModelRegistrationForm((previousValue) => ({
        ...previousValue,
        source_model_path: result.filePath || "",
        selected_model_file_name: result.fileName || "",
        family_name: previousValue.family_name ? previousValue.family_name : defaultName,
      }));
    } catch (error) {
      showErrorStatus(error);
    }
  }, [showErrorStatus]);

  const onRegisterModel = useCallback(async () => {
    try {
      if (!modelRegistrationForm.source_model_path) {
        throw new Error("Choose a .pth or .pt model file before continuing.");
      }
      if (!modelRegistrationForm.family_name.trim()) {
        throw new Error("Enter a model name.");
      }
      if (!modelRegistrationForm.description.trim()) {
        throw new Error("Enter a model description.");
      }
      if (!modelRegistrationForm.training_images_dir.trim() || !modelRegistrationForm.training_labels_dir.trim()) {
        throw new Error("Enter both training dataset paths.");
      }
      if (!modelRegistrationForm.test_images_dir.trim() || !modelRegistrationForm.test_labels_dir.trim()) {
        throw new Error("Enter both test dataset paths.");
      }
      setIsSubmittingModel(true);
      const response = await apiPost("/models/register", modelRegistrationForm);
      const nextModels = await loadModels();
      await Promise.all([loadModelRegistry(), loadTrainingDatasets(), loadTestDatasets()]);
      if (response.model_version?.id) {
        setSelectedModelId(String(response.model_version.id));
      } else if (nextModels.length > 0) {
        setSelectedModelId(String(nextModels[0].id));
      }
      setModelRegistrationForm({
        source_model_path: "",
        selected_model_file_name: "",
        family_name: "",
        description: "",
        training_images_dir: "",
        training_labels_dir: "",
        test_images_dir: "",
        test_labels_dir: "",
        notes: "",
      });
      setIsAddModelModalOpen(false);
      showStatus("Model registered. Use Evaluate on Test Set when you are ready.", "info");
    } catch (error) {
      showErrorStatus(error);
    } finally {
      setIsSubmittingModel(false);
    }
  }, [
    apiPost,
    loadModelRegistry,
    loadModels,
    loadTestDatasets,
    loadTrainingDatasets,
    modelRegistrationForm,
    showErrorStatus,
    showStatus,
  ]);

  const onEvaluateModelVersion = useCallback(async (version) => {
    try {
      setLoading({
        visible: true,
        processedImages: 0,
        totalImages: 0,
        message: `Preparing evaluation for ${version.family_name} ${version.version_tag}...`,
        estimatedRemainingSeconds: null,
        canCancel: false,
        onCancel: null,
      });
      const response = await apiPost(`/models/versions/${version.id}/evaluate-default`, {});
      if (response.already_evaluated) {
        setLoading({
          visible: false,
          processedImages: 0,
          totalImages: 0,
          message: "",
          estimatedRemainingSeconds: null,
          canCancel: false,
          onCancel: null,
        });
        showStatus(response.message || "Evaluation already occurred for this model version.", "info");
        return;
      }

      setLoading((previousValue) => ({
        ...previousValue,
        canCancel: true,
        onCancel: async () => {
          try {
            await apiPost(`/models/jobs/${response.model_job_id}/cancel`, {});
            showStatus("Cancellation requested for test evaluation.", "info");
          } catch (error) {
            showErrorStatus(error);
          }
        },
      }));

      await pollModelJobUntilDone(response.model_job_id);
      await Promise.all([loadModels(), loadModelRegistry()]);
      const latestJob = await apiGet(`/models/jobs/${response.model_job_id}`);
      if (latestJob.status === "cancelled") {
        showStatus(`Evaluation cancelled for ${version.family_name} ${version.version_tag}.`, "info");
        return;
      }
      showStatus(`Evaluation complete for ${version.family_name} ${version.version_tag}.`, "info");
    } catch (error) {
      showErrorStatus(error);
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
    }
  }, [apiPost, loadModelRegistry, loadModels, pollModelJobUntilDone, showErrorStatus, showStatus]);

  const onFineTuneModelVersion = useCallback(async (version) => {
    try {
      setLoading({
        visible: true,
        processedImages: 0,
        totalImages: 0,
        message: `Preparing fine-tuning for ${version.family_name} ${version.version_tag}...`,
        estimatedRemainingSeconds: null,
        canCancel: false,
        onCancel: null,
      });
      const response = await apiPost(`/models/versions/${version.id}/fine-tune`, {});
      setLoading((previousValue) => ({
        ...previousValue,
        canCancel: true,
        onCancel: async () => {
          try {
            await apiPost(`/models/jobs/${response.model_job_id}/cancel`, {});
            showStatus("Cancellation requested for fine-tuning.", "info");
          } catch (error) {
            showErrorStatus(error);
          }
        },
      }));

      const finalJob = await pollModelJobUntilDone(response.model_job_id);
      await Promise.all([loadModels(), loadModelRegistry()]);
      if (finalJob.status === "cancelled") {
        showStatus(`Fine-tuning cancelled for ${version.family_name} ${version.version_tag}.`, "info");
        return;
      }
      if (finalJob.model_version?.id) {
        setSelectedModelId(String(finalJob.model_version.id));
      }
      showStatus(`Fine-tuning complete. ${version.family_name} ${finalJob.model_version?.version_tag || ""} is ready.`, "info");
    } catch (error) {
      showErrorStatus(error);
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
    }
  }, [apiPost, loadModelRegistry, loadModels, pollModelJobUntilDone, showErrorStatus, showStatus]);

  const onDeleteModelVersion = useCallback(async (version) => {
    const versionNumber = Number(version.version_number || 0);
    const isBaselineFamily = String(version.family_name || "").toLowerCase() === "fasterrcnn_baseline";
    if (isBaselineFamily && versionNumber <= 1) {
      showStatus("The bundled baseline model v1 cannot be deleted.", "error");
      return;
    }
    const confirmed = window.confirm(
      versionNumber <= 1
        ? `Permanently delete the model family "${version.family_name || "this model"}" and all of its versions? This cannot be undone.`
        : `Permanently delete ${version.family_name || "this model"} ${version.version_tag || ""} and all later versions? This cannot be undone.`
    );
    if (!confirmed) {
      return;
    }
    try {
      await apiDelete(`/models/versions/${version.id}`);
      const nextModels = await loadModels();
      await loadModelRegistry();
      setSelectedModelId((previousValue) => {
        if (String(previousValue) !== String(version.id)) {
          return previousValue;
        }
        return nextModels.length > 0 ? String(nextModels[0].id) : "";
      });
      showStatus("Model version deleted.", "info");
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiDelete, loadModelRegistry, loadModels, showErrorStatus, showStatus]);

  const onDeleteModelFamily = useCallback(async (family) => {
    const isBaselineFamily = String(family.name || "").toLowerCase() === "fasterrcnn_baseline";
    if (isBaselineFamily) {
      showStatus("The bundled baseline model cannot be deleted.", "error");
      return;
    }
    const confirmed = window.confirm(
      `Permanently delete the model family "${family.name}" and all of its versions? This cannot be undone.`
    );
    if (!confirmed) {
      return;
    }
    try {
      await apiDelete(`/models/families/${family.id}`);
      const nextModels = await loadModels();
      await loadModelRegistry();
      setSelectedModelId((previousValue) => {
        const stillExists = nextModels.some((model) => String(model.id) === String(previousValue));
        return stillExists ? previousValue : (nextModels[0] ? String(nextModels[0].id) : "");
      });
      showStatus(`Deleted model "${family.name}".`, "info");
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiDelete, loadModelRegistry, loadModels, showErrorStatus, showStatus]);

  const onOpenModelInfo = useCallback(async (modelVersionId) => {
    try {
      const response = await apiGet(`/models/versions/${modelVersionId}/report`);
      setModelReport(response.report || null);
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiGet, showErrorStatus]);

  const onExportModelVersion = useCallback(async (version) => {
    try {
      const defaultFileName = `${version.family_name || "model"}_${version.version_tag || "version"}.zip`;
      const response = await window.desktopAPI.downloadBackendFile(
        `/models/versions/${version.id}/export`,
        defaultFileName
      );
      if (response?.saved) {
        showStatus(`Export saved to ${response.filePath}.`, "info");
      }
    } catch (error) {
      showErrorStatus(error);
    }
  }, [showErrorStatus, showStatus]);

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
        `Finalized reviewed labels: ${response.replay_buffer_summary?.image_count || 0} images and ${response.replay_buffer_summary?.detection_count || 0} mussels saved to the replay buffer.`,
        "info"
      );
    } catch (error) {
      showErrorStatus(error);
    }
  }, [apiPost, currentRun, loadModelRegistry, showErrorStatus, showStatus]);

  const onStartDrawingBox = useCallback(() => {
    if (detailImage?.is_locked_for_editing) {
      showStatus("This image has already been used for fine-tuning and is now read-only.", "error");
      return;
    }
    setEditingDetection(null);
    setDraftDetection(null);
    setIsDrawingBox(true);
    showStatus("Drag on the image to create a new box, then move or resize it before saving.", "info");
  }, [detailImage?.is_locked_for_editing, showStatus]);

  const onCancelDraftDetection = useCallback(() => {
    setDraftDetection(null);
    setIsDrawingBox(false);
  }, []);

  const onSaveDraftDetection = useCallback((className) => {
    if (!detailImage || !draftDetection) {
      return;
    }
    const width = Number(draftDetection.x2) - Number(draftDetection.x1);
    const height = Number(draftDetection.y2) - Number(draftDetection.y1);
    if (width < 2 || height < 2) {
      showStatus("Draw a larger box before saving it.", "error");
      return;
    }
    createDetection(detailImage.run_image_id, {
      class_name: className,
      bbox_x1: draftDetection.x1,
      bbox_y1: draftDetection.y1,
      bbox_x2: draftDetection.x2,
      bbox_y2: draftDetection.y2,
      confidence_score: null,
    });
  }, [createDetection, detailImage, draftDetection, showStatus]);

  const fineTuneNotification = useMemo(() => {
    const threshold = Number(appSettings.fine_tune_min_new_images) || 0;
    if (threshold <= 0) {
      return null;
    }
    for (const family of modelFamilies) {
      const latestVersion = Array.isArray(family.versions)
        ? family.versions.find((version) => version.is_latest_version)
        : null;
      if (!latestVersion) {
        continue;
      }
      const pendingImageCount = Number(latestVersion.replay_buffer_counts?.image_count || 0);
      const pendingDetectionCount = Number(latestVersion.replay_buffer_counts?.detection_count || 0);
      if (pendingImageCount >= threshold) {
        return {
          familyName: family.name,
          versionTag: latestVersion.version_tag,
          imageCount: pendingImageCount,
          detectionCount: pendingDetectionCount,
        };
      }
    }
    return null;
  }, [appSettings.fine_tune_min_new_images, modelFamilies]);

  return (
    <div className="shell">
      <TopBar
        onGoHome={() => goToRoute("/")}
        onGoHistory={() => goToRoute("/history")}
        onGoModels={() => goToRoute("/models")}
        onGoUsage={() => goToRoute("/usage")}
        onGoSettings={() => goToRoute("/settings")}
        onAddModel={onAddModel}
        onStartNewRun={onStartNewRun}
      />

      <StatusBanner status={status} />
      <LoadingBar loading={loading} />
      {fineTuneNotification ? (
        <div className="panel fine-tune-notice">
          <div className="fine-tune-notice-copy">
            <div className="title-with-help">
              <p className="fine-tune-notice-title">Fine-Tuning Available</p>
              <HelpTooltip
                title="Fine-tuning available"
                wide
                content={[
                  "This appears when you have saved enough reviewed images to make a new version of a model.",
                  "Open Models and click Fine-Tune on the newest version when you are ready.",
                ]}
              />
            </div>
            <p className="helper">
              {fineTuneNotification.familyName} {fineTuneNotification.versionTag} has {fineTuneNotification.imageCount} saved reviewed images and {fineTuneNotification.detectionCount} saved mussels ready for Fine-Tune.
            </p>
          </div>
          <button className="ghost" onClick={() => goToRoute("/models")}>
            Open Models
          </button>
        </div>
      ) : null}
      {isGpuUpgradePromptOpen ? (
        <div className="modal-overlay" onClick={onKeepCpuForNow}>
          <div className="modal-card gpu-upgrade-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Compatible GPU Detected</h3>
            </div>
            <div className="modal-body">
              <p className="helper usage-copy">
                GPU acceleration is available on this computer. Enable it for faster model runs, evaluation, and fine-tuning.
              </p>
              {computeStatus?.gpu_runtime_ready ? (
                <p className="helper usage-copy">
                  This app can use the detected GPU right away if you enable the GPU preference now.
                </p>
              ) : (
                <p className="helper usage-copy">
                  This current build still runs on CPU, but saving the GPU preference now prepares the app for the optional GPU-enabled installer workflow later.
                </p>
              )}
              {computeStatus?.detected_gpu_name ? (
                <p className="helper usage-copy">
                  Detected GPU: <strong>{computeStatus.detected_gpu_name}</strong>
                </p>
              ) : null}
            </div>
            <div className="settings-footer">
              <button className="ghost" onClick={onKeepCpuForNow}>
                Keep CPU for Now
              </button>
              <button className="primary" onClick={onEnableGpuPreference}>
                Enable GPU Preference
              </button>
            </div>
          </div>
        </div>
      ) : null}

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
        modelFamilies={modelFamilies}
        modelForm={modelRegistrationForm}
        onUpdateModelForm={onUpdateModelForm}
        onChooseModelFile={onChooseModelFile}
        onRegisterModel={onRegisterModel}
        onDeleteModelVersion={onDeleteModelVersion}
        onDeleteModelFamily={onDeleteModelFamily}
        onExportModelVersion={onExportModelVersion}
        onOpenModelInfo={onOpenModelInfo}
        onEvaluateModelVersion={onEvaluateModelVersion}
        onFineTuneModelVersion={onFineTuneModelVersion}
        isModelModalOpen={isAddModelModalOpen}
        onCloseModelModal={closeAddModelModal}
        isSubmittingModel={isSubmittingModel}
        modelReport={modelReport}
        onCloseModelReport={() => setModelReport(null)}
      />

      <SettingsView
        visible={isSettingsViewVisible}
        settings={appSettings}
        computeStatus={computeStatus}
        draftSettings={draftAppSettings}
        onChangeSetting={onChangeAppSetting}
        onSaveSettings={onSaveSettings}
        isSavingSettings={isSavingSettings}
      />

      <UsageView
        visible={isUsageViewVisible}
        onOpenSharedDrive={() => {
          window.desktopAPI.openExternalUrl(
            "https://drive.google.com/drive/folders/1GigNwEYUg6u1zxXWBg0SBv7gm660JccT?usp=drive_link"
          ).catch(showErrorStatus);
        }}
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
        onCanvasMouseDown={onCanvasMouseDown}
        onCanvasMouseMove={onCanvasMouseMove}
        onCanvasMouseUp={onCanvasMouseUp}
        detailCounts={detailCounts}
        detectionsForList={detectionsForList}
        onOpenDetection={(detection) => {
          if (detailImage?.is_locked_for_editing) {
            showStatus("This image has already been used for fine-tuning and is now read-only.", "error");
            return;
          }
          setEditingDetection(detection);
        }}
        onBack={backToRunOrHome}
        isDrawingBox={isDrawingBox}
        draftDetection={draftDetection}
        onStartDrawingBox={onStartDrawingBox}
        onCancelDraftDetection={onCancelDraftDetection}
        onSaveDraftLive={() => onSaveDraftDetection("live")}
        onSaveDraftDead={() => onSaveDraftDetection("dead")}
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
