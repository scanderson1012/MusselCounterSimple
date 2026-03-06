/**
 * Pick the banner style from the status object.
 */
function getStatusClassName(status) {
  if (!status.message) {
    return "status-banner hidden";
  }
  return `status-banner ${status.type}`;
}

/**
 * Global status message banner shown near the top of the app.
 */
function StatusBanner({ status }) {
  return (
    <p id="status-banner" className={getStatusClassName(status)}>
      {status.message || ""}
    </p>
  );
}

export default StatusBanner;
