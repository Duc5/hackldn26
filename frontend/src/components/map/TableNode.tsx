import { statusLabel } from "../../utils/tableStatus";

interface TableNodeProps {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  seatsLabel: string;
  status: "available" | "partial" | "full";
  dimmed: boolean;
  selected: boolean;
  recommended: boolean;
  onClick: (id: string) => void;
}

export function TableNode(props: TableNodeProps): JSX.Element {
  const { id, x, y, width, height, seatsLabel, status, dimmed, selected, recommended, onClick } = props;

  const className = [
    "table-node",
    `status-${status}`,
    dimmed ? "dimmed" : "",
    selected ? "selected" : "",
    recommended ? "recommended" : ""
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      className={className}
      style={{ left: `${x}%`, top: `${y}%`, width: `${width}%`, height: `${height}%` }}
      onClick={() => onClick(id)}
      title={`${id} - ${statusLabel(status)}`}
    >
      <strong>{id}</strong>
      <small>{seatsLabel}</small>
    </button>
  );
}
