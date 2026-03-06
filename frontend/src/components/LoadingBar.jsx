/**
 * Progress bar for background model runs.
 */
function LoadingBar({ loading }) {
  if (!loading.visible) {
    return (
      <div id="inference-loading" className="inference-loading hidden" aria-live="polite">
        <div
          id="inference-loading-track"
          className="inference-loading-track"
          role="progressbar"
          aria-label="Model run progress"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow="0"
        >
          <div id="inference-loading-bar" className="inference-loading-bar" style={{ width: "0%" }} />
        </div>
        <p id="inference-loading-text" className="inference-loading-text">
          Running model... 0 / 0 images
        </p>
      </div>
    );
  }

  const boundedProcessed = Math.max(0, Number(loading.processedImages) || 0);
  const boundedTotal = Math.max(0, Number(loading.totalImages) || 0);
  const percentage =
    boundedTotal > 0 ? Math.round((Math.min(boundedProcessed, boundedTotal) / boundedTotal) * 100) : 0;

  return (
    <div id="inference-loading" className="inference-loading" aria-live="polite">
      <div
        id="inference-loading-track"
        className="inference-loading-track"
        role="progressbar"
        aria-label="Model run progress"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={String(percentage)}
      >
        <div id="inference-loading-bar" className="inference-loading-bar" style={{ width: `${percentage}%` }} />
      </div>
      <p id="inference-loading-text" className="inference-loading-text">
        Running model... {boundedProcessed} / {boundedTotal} images
      </p>
    </div>
  );
}

export default LoadingBar;
