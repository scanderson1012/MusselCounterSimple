import HistoryCard from "../components/HistoryCard.jsx";

/**
 * Prediction history view listing past runs.
 */
function HistoryView({ visible, runs, runImageUrl, onOpenRun }) {
  return (
    <section id="history-view" className={`view${visible ? "" : " hidden"}`}>
      <div className="history-header">
        <div>
          <h1>Prediction History</h1>
          <p className="history-subtitle">Pick a past run to view its images and model results.</p>
        </div>
      </div>

      <div id="history-list" className="history-grid">
        {runs.length === 0 ? (
          <p className="empty-state">No runs yet.</p>
        ) : (
          runs.map((runData) => (
            <HistoryCard
              key={runData.id}
              runData={runData}
              previewUrl={runData.preview_image_url ? runImageUrl(runData.preview_image_url) : ""}
              onOpen={() => onOpenRun(runData.id)}
            />
          ))
        )}
      </div>
    </section>
  );
}

export default HistoryView;
