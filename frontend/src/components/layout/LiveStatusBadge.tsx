import type { SourceMode } from "../../types/seatsense";
import { formatTime } from "../../utils/format";

interface LiveStatusBadgeProps {
  sourceMode: SourceMode;
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
  embedded?: boolean;
}

export function LiveStatusBadge(props: LiveStatusBadgeProps): JSX.Element {
  const { sourceMode, loading, error, lastUpdated, embedded = false } = props;
  const modeLabel = sourceMode === "live" ? "LIVE" : sourceMode === "hybrid" ? "HYBRID" : "DEMO";
  const className = embedded ? "status-card status-embedded" : "card status-card";

  return (
    <div className={className}>
      <div className="status-row">
        <span className={`mode-badge mode-${sourceMode}`}>{modeLabel}</span>
        {loading ? <span className="loading-dot">Updating...</span> : <span>Stable</span>}
      </div>
      <p className="status-meta">Last updated: {formatTime(lastUpdated)}</p>
      {error ? <p className="status-error">Live feed issue: {error}</p> : null}
    </div>
  );
}
