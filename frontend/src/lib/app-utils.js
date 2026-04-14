export const DEFAULT_THRESHOLD = 0.5;
export const RUN_JOB_POLL_INTERVAL_MS = 350;

/**
 * Read the URL hash and return which page the app should show.
 */
export function parseRoute(hashValue) {
  const route = String(hashValue || "").replace(/^#/, "") || "/";

  if (route === "/history") {
    return { kind: "history" };
  }

  if (route === "/models") {
    return { kind: "models" };
  }

  if (route === "/settings") {
    return { kind: "settings" };
  }

  const imageMatch = route.match(/^\/run\/(\d+)\/image\/(\d+)$/);
  if (imageMatch) {
    return {
      kind: "image",
      runId: Number(imageMatch[1]),
      runImageId: Number(imageMatch[2]),
    };
  }

  const runMatch = route.match(/^\/run\/(\d+)$/);
  if (runMatch) {
    return {
      kind: "run",
      runId: Number(runMatch[1]),
    };
  }

  return { kind: "run", runId: null };
}

/**
 * Pause for a short time.
 */
export function waitMilliseconds(durationMilliseconds) {
  return new Promise((resolve) => setTimeout(resolve, durationMilliseconds));
}

/**
 * Make sure threshold stays between 0 and 1.
 */
export function clampThreshold(rawValue) {
  const numericValue = Number(rawValue);
  if (Number.isNaN(numericValue)) {
    return DEFAULT_THRESHOLD;
  }
  return Math.min(1, Math.max(0, numericValue));
}

/**
 * Format date text for display.
 */
export function formatDate(dateString) {
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) {
    return String(dateString || "");
  }
  return date.toLocaleString();
}

/**
 * Build the run title shown in cards and headers.
 */
export function formatRunDisplayName(runData) {
  return `Run ${runData.id} - ${formatDate(runData.created_at)}`;
}

/**
 * Shorten long model file names so cards stay easy to read.
 */
export function formatModelFileNameForDisplay(modelFileName) {
  const baseFileName = String(modelFileName || "").split(/[/\\]/).pop() || String(modelFileName || "");
  const maxLength = 36;
  if (baseFileName.length <= maxLength) {
    return baseFileName;
  }
  return `${baseFileName.slice(0, maxLength - 3)}...`;
}

/**
 * Keep only detections that pass the current threshold.
 */
export function getVisibleDetections(detections, threshold) {
  return detections.filter((detection) => {
    return !detection.is_deleted && (
      detection.confidence_score == null || Number(detection.confidence_score) >= threshold
    );
  });
}

/**
 * Count live, dead, and total detections.
 */
export function getCountsFromDetections(detections, threshold) {
  const visibleDetections = getVisibleDetections(detections, threshold);
  const liveCount = visibleDetections.filter((detection) => detection.class_name === "live").length;
  const deadCount = visibleDetections.filter((detection) => detection.class_name === "dead").length;
  return { liveCount, deadCount, totalCount: liveCount + deadCount };
}
