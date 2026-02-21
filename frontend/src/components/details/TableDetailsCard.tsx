import type { TableData } from "../../types/seatsense";
import { statusLabel } from "../../utils/tableStatus";

interface TableDetailsCardProps {
  table: TableData | null;
}

export function TableDetailsCard({ table }: TableDetailsCardProps): JSX.Element {
  if (!table) {
    return (
      <section className="card details-card">
        <h2>Table Details</h2>
        <p className="muted">Select a table on the map to inspect live seat availability.</p>
      </section>
    );
  }

  return (
    <section className="card details-card">
      <h2>Table {table.table_id}</h2>
      <ul className="details-list">
        <li>Zone: {table.zone_name}</li>
        <li>Type: {table.zone_type}</li>
        <li>
          Seats free: {table.available_seats}/{table.total_seats}
        </li>
        <li>Status: {statusLabel(table.status)}</li>
      </ul>
    </section>
  );
}
