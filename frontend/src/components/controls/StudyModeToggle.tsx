import type { StudyMode } from "../../types/seatsense";

interface StudyModeToggleProps {
  value: StudyMode;
  onChange: (mode: StudyMode) => void;
}

export function StudyModeToggle({ value, onChange }: StudyModeToggleProps): JSX.Element {
  return (
    <div className="control-group">
      <p className="control-label">Study mode</p>
      <div className="segmented">
        <button className={value === "solo" ? "active" : ""} onClick={() => onChange("solo")}>
          Solo
        </button>
        <button className={value === "group" ? "active" : ""} onClick={() => onChange("group")}>
          Group
        </button>
      </div>
    </div>
  );
}
