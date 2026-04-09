import { formatDate, formatModelFileNameForDisplay } from "../lib/app-utils.js";

/**
 * Detail page for one run image with overlays and detection editing entrypoints.
 */
function ImageDetailView({
  visible,
  currentRun,
  detailImage,
  bboxVisible,
  onToggleBboxVisible,
  detailImageRef,
  detailCanvasRef,
  runImageUrl,
  onImageLoad,
  onCanvasClick,
  onCanvasMouseDown,
  onCanvasMouseMove,
  onCanvasMouseUp,
  detailCounts,
  detectionsForList,
  onOpenDetection,
  onBack,
  isDrawingBox,
  draftDetection,
  onStartDrawingBox,
  onCancelDraftDetection,
  onSaveDraftLive,
  onSaveDraftDead,
}) {
  return (
    <section id="image-detail-view" className={`view${visible ? "" : " hidden"}`}>
      <button id="back-to-run-btn" className="ghost back-link" onClick={onBack}>
        Back to prediction history
      </button>

      <div className="detail-header">
        <h1 id="detail-image-name">{detailImage ? detailImage.displayed_file_name : "-"}</h1>
        <div className="detail-header-actions">
          <label className="bbox-toggle">
            <input
              type="checkbox"
              id="bbox-visible-toggle"
              checked={bboxVisible}
              onChange={(event) => onToggleBboxVisible(event.target.checked)}
            />
            <span>Bounding Boxes</span>
          </label>
          <button className="ghost" onClick={onStartDrawingBox}>
            Add Bounding Box
          </button>
        </div>
      </div>

      <div className="detail-layout">
        <div className="detail-image-col">
          <div className="detail-image-container" id="detail-image-container">
            <img
              id="detail-image"
              ref={detailImageRef}
              alt={detailImage ? detailImage.displayed_file_name : ""}
              src={detailImage ? runImageUrl(detailImage.image_url) : ""}
              onLoad={onImageLoad}
            />
            <canvas
              id="detail-canvas"
              ref={detailCanvasRef}
              onClick={onCanvasClick}
              onMouseDown={onCanvasMouseDown}
              onMouseMove={onCanvasMouseMove}
              onMouseUp={onCanvasMouseUp}
              onMouseLeave={onCanvasMouseUp}
            />
          </div>
          {isDrawingBox ? (
            <p className="helper detail-draw-helper">
              Drag to create a box. Drag inside the box to move it. Drag the corner handles to resize and change aspect ratio.
            </p>
          ) : null}
        </div>

        <div className="detail-sidebar">
          <div className="panel detail-panel">
            <h3>Statistics</h3>
            <div className="detail-stat">
              <span className="detail-stat-label">Live Mussels</span>
              <span className="detail-stat-value count-live" id="detail-live">
                {detailCounts.liveCount}
              </span>
            </div>
            <div className="detail-stat">
              <span className="detail-stat-label">Dead Mussels</span>
              <span className="detail-stat-value count-dead" id="detail-dead">
                {detailCounts.deadCount}
              </span>
            </div>
            <div className="detail-stat">
              <span className="detail-stat-label">Total</span>
              <span className="detail-stat-value" id="detail-total">
                {detailCounts.totalCount}
              </span>
            </div>
          </div>

          <div className="panel detail-panel">
            <h3>Model Information</h3>
            <p className="detail-info-line" id="detail-model">
              Model: {currentRun ? formatModelFileNameForDisplay(currentRun.model_file_name) : "-"}
            </p>
            <p className="detail-info-line" id="detail-threshold">
              Threshold: {currentRun ? Number(currentRun.threshold_score).toFixed(2) : "-"}
            </p>
            <p className="detail-info-line" id="detail-processed">
              Processed: {currentRun ? formatDate(currentRun.updated_at) : "-"}
            </p>
          </div>

          {draftDetection ? (
            <div className="panel detail-panel">
              <h3>New Box Draft</h3>
              <p className="detail-info-line">
                X: {Math.round(draftDetection.x1)} to {Math.round(draftDetection.x2)}
              </p>
              <p className="detail-info-line">
                Y: {Math.round(draftDetection.y1)} to {Math.round(draftDetection.y2)}
              </p>
              <p className="detail-info-line">
                Size: {Math.round(draftDetection.x2 - draftDetection.x1)} x {Math.round(draftDetection.y2 - draftDetection.y1)}
              </p>
              <div className="modal-actions">
                <button className="modal-btn modal-btn-live" onClick={onSaveDraftLive}>
                  Save As Live
                </button>
                <button className="modal-btn modal-btn-dead" onClick={onSaveDraftDead}>
                  Save As Dead
                </button>
              </div>
              <button className="modal-btn modal-btn-delete" onClick={onCancelDraftDetection}>
                Cancel Draft Box
              </button>
            </div>
          ) : null}

          <div className="panel detail-panel">
            <h3>Detections</h3>
            <div id="detail-detection-list" className="detail-detection-list">
              {detectionsForList.length === 0 ? (
                <p className="empty-state">No detections above threshold.</p>
              ) : (
                detectionsForList.map((detection) => (
                  <div
                    key={detection.id}
                    className={`detection-list-item${detection.is_deleted ? " is-deleted" : ""}`}
                    onClick={() => onOpenDetection(detection)}
                  >
                    <span className={`detection-list-tag ${detection.class_name}`}>{detection.class_name}</span>
                    <span className="detection-list-conf">
                      {Number.isFinite(Number(detection.confidence_score))
                        ? `${(Number(detection.confidence_score) * 100).toFixed(0)}%`
                        : "manual"}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default ImageDetailView;
