import { formatDate, formatModelFileNameForDisplay, formatRunDisplayName } from "../lib/app-utils.js";

/**
 * Card for one historical run in the prediction history grid.
 */
function HistoryCard({ runData, previewUrl, onOpen }) {
  return (
    <article className="history-card">
      <div className="history-card-header">
        <p className="history-title">{formatRunDisplayName(runData)}</p>
        <button className="ghost history-open" onClick={onOpen}>
          Open
        </button>
      </div>

      <div className="history-badges">
        <span className="history-badge">{runData.image_count} images</span>
        <span className="history-badge">{formatModelFileNameForDisplay(runData.model_file_name)}</span>
      </div>

      <img className="history-preview" alt={`${formatRunDisplayName(runData)} preview`} src={previewUrl || ""} />

      <div className="history-info">
        <p className="history-created">Created {formatDate(runData.created_at)}</p>
        <p>
          Live: <span className="count-live">{runData.live_mussel_count}</span> &nbsp;Dead:{" "}
          <span className="count-dead">{runData.dead_mussel_count}</span>
        </p>
        <p>
          Threshold: {Number(runData.threshold_score).toFixed(2)} | Model:{" "}
          {formatModelFileNameForDisplay(runData.model_file_name)}
        </p>
      </div>
    </article>
  );
}

export default HistoryCard;
