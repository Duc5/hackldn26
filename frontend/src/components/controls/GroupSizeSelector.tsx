interface GroupSizeSelectorProps {
  value: number;
  onChange: (size: number) => void;
}

export function GroupSizeSelector({ value, onChange }: GroupSizeSelectorProps): JSX.Element {
  return (
    <div className="control-group">
      <p className="control-label">Group size</p>
      <div className="chip-row">
        {[2, 3, 4].map((size) => (
          <button
            key={size}
            className={value === size ? "chip active" : "chip"}
            onClick={() => onChange(size)}
          >
            {size === 4 ? "4+" : size}
          </button>
        ))}
      </div>
    </div>
  );
}
