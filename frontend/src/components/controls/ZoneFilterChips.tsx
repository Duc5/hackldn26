import type { ZoneType } from "../../types/seatsense";

interface ZoneFilterChipsProps {
  selected: ZoneType[];
  onToggle: (zone: ZoneType) => void;
}

const FILTERS: ZoneType[] = ["quiet", "group"];

export function ZoneFilterChips({ selected, onToggle }: ZoneFilterChipsProps): JSX.Element {
  return (
    <div className="control-group">
      <p className="control-label">Zone filter</p>
      <div className="chip-row">
        {FILTERS.map((filter) => (
          <button
            key={filter}
            className={selected.includes(filter) ? "chip active" : "chip"}
            onClick={() => onToggle(filter)}
          >
            {filter === "quiet" ? "Quiet" : "Group Study"}
          </button>
        ))}
      </div>
    </div>
  );
}
