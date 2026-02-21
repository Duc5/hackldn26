export function MapLegend(): JSX.Element {
  return (
    <div className="legend">
      <span>
        <i className="legend-dot available" />
        Available
      </span>
      <span>
        <i className="legend-dot partial" />
        Partially Available
      </span>
      <span>
        <i className="legend-dot full" />
        Full
      </span>
    </div>
  );
}
