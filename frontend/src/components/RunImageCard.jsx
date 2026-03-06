/**
 * Card for one image within the current run.
 */
function RunImageCard({ imageData, imageUrl, onOpen, onRemove }) {
  return (
    <article className="image-card">
      <div className="image-wrapper">
        <img
          src={imageUrl}
          alt={imageData.displayed_file_name}
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={onOpen}
        />
        <button className="image-delete-btn" title="Remove from run" onClick={onRemove}>
          ×
        </button>
      </div>
      <div className="image-meta" style={{ cursor: "pointer" }} onClick={onOpen}>
        <p className="image-name" title={imageData.displayed_file_name}>
          {imageData.displayed_file_name}
        </p>
        <p className="image-counts">
          Live: <span className="count-live">{imageData.live_mussel_count}</span> &nbsp;Dead:{" "}
          <span className="count-dead">{imageData.dead_mussel_count}</span>
        </p>
      </div>
    </article>
  );
}

export default RunImageCard;
