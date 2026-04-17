function normalizeLines(content) {
  if (Array.isArray(content)) {
    return content.filter(Boolean).map((line) => String(line));
  }
  if (!content) {
    return [];
  }
  return [String(content)];
}

/**
 * Small inline help bubble that reveals guidance on hover or focus.
 */
function HelpTooltip({ title = "Help", content, align = "center", wide = false }) {
  const lines = normalizeLines(content);

  return (
    <span className={`help-tooltip${wide ? " help-tooltip-wide" : ""}`}>
      <button
        type="button"
        className="help-tooltip-trigger"
        aria-label={title}
      >
        ?
      </button>
      <span className={`help-tooltip-popup help-tooltip-popup-${align}`} role="tooltip">
        <span className="help-tooltip-title">{title}</span>
        {lines.map((line) => (
          <span key={line} className="help-tooltip-line">
            {line}
          </span>
        ))}
      </span>
    </span>
  );
}

export default HelpTooltip;
