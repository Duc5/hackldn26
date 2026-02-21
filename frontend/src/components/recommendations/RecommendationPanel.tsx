import type { Recommendation, StudyMode } from "../../types/seatsense";

interface RecommendationPanelProps {
  recommendations: Recommendation[];
  studyMode: StudyMode;
  groupSize: number;
  onSelectTable: (tableId: string) => void;
}

export function RecommendationPanel(props: RecommendationPanelProps): JSX.Element {
  const { recommendations, studyMode, groupSize, onSelectTable } = props;

  return (
    <section className="card recommendations-card">
      <h2>Recommended Right Now</h2>
      {recommendations.length === 0 ? (
        <p className="muted">
          No exact match for {studyMode === "solo" ? "solo mode" : `group of ${groupSize}`}. Try changing zone filter.
        </p>
      ) : (
        <ul className="recommendation-list">
          {recommendations.map((rec, index) => (
            <li key={rec.table.table_id}>
              <button className="rec-item" onClick={() => onSelectTable(rec.table.table_id)}>
                <div>
                  <p className="rec-rank">
                    #{index + 1} {rec.table.table_id}
                  </p>
                  <p>{rec.table.zone_name}</p>
                </div>
                <div className="rec-meta">
                  <span>
                    {rec.table.available_seats}/{rec.table.total_seats} free
                  </span>
                  <small>{rec.reason}</small>
                  {rec.secondaryTag ? <small>{rec.secondaryTag}</small> : null}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
