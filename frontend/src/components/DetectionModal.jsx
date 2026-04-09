/**
 * Modal for reviewing and editing a single detection.
 */
function DetectionModal({ detection, onClose, onSetLive, onSetDead, onDelete }) {
  if (!detection) {
    return <div id="detection-modal" className="modal-overlay hidden" />;
  }

  const isLive = detection.class_name === "live";

  return (
    <div
      id="detection-modal"
      className="modal-overlay"
      onClick={(event) => {
        if (event.target.id === "detection-modal") {
          onClose();
        }
      }}
    >
      <div className="modal-card">
        <div className="modal-header">
          <h3 id="modal-title">Edit Detection #{detection.id}</h3>
          <button id="modal-close-btn" className="ghost modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <div className="modal-field">
            <span className="modal-field-label">Classification</span>
            <span
              id="modal-class"
              className="modal-field-value"
              style={{ color: isLive ? "var(--accent-green)" : "var(--accent-red)" }}
            >
              {isLive ? "Live" : "Dead"}
            </span>
          </div>

          <div className="modal-field">
            <span className="modal-field-label">Confidence</span>
            <span id="modal-confidence" className="modal-field-value">
              {Number.isFinite(Number(detection.confidence_score))
                ? `${(Number(detection.confidence_score) * 100).toFixed(1)}% ${detection.class_name}`
                : `Manual ${detection.class_name}`}
            </span>
          </div>

          <div className="modal-field">
            <span className="modal-field-label">Manually Edited</span>
            <span id="modal-edited" className="modal-field-value">
              {detection.is_edited ? "Yes" : "No"}
            </span>
          </div>

          <hr className="modal-divider" />
          <p className="modal-section-label">Change Classification</p>
          <div className="modal-actions">
            <button id="modal-set-live" className="modal-btn modal-btn-live" onClick={onSetLive}>
              Live
            </button>
            <button id="modal-set-dead" className="modal-btn modal-btn-dead" onClick={onSetDead}>
              Dead
            </button>
          </div>
          <hr className="modal-divider" />
          <button id="modal-delete-btn" className="modal-btn modal-btn-delete" onClick={onDelete}>
            Delete Detection
          </button>
        </div>
      </div>
    </div>
  );
}

export default DetectionModal;
