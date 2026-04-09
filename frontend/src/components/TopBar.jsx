/**
 * Main app navigation and top-level actions.
 */
function TopBar({ onGoHome, onGoHistory, onGoModels, onAddModel, onStartNewRun }) {
  return (
    <header className="topbar">
      <nav className="topbar-actions-left">
        <button id="go-home" className="ghost topbar-chip" onClick={onGoHome}>
          Home
        </button>
        <button id="go-history" className="ghost topbar-chip" onClick={onGoHistory}>
          View History
        </button>
        <button id="go-models" className="ghost topbar-chip" onClick={onGoModels}>
          Models
        </button>
      </nav>
      <nav className="topbar-actions-right">
        <button id="add-model-btn" className="ghost topbar-chip" onClick={onAddModel}>
          + Add Model
        </button>
        <button id="start-new-run-btn" className="primary topbar-primary" onClick={onStartNewRun}>
          Start New Run
        </button>
      </nav>
    </header>
  );
}

export default TopBar;
