import type { StudyMode, TableData } from "../../types/seatsense";
import { statusLabel } from "../../utils/tableStatus";

interface FallbackListViewProps {
  tables: TableData[];
  studyMode: StudyMode;
  groupSize: number;
  onSelectTable: (id: string) => void;
}

function suitability(table: TableData, studyMode: StudyMode, groupSize: number): string {
  if (studyMode === "solo") {
    return table.available_seats >= 1 ? "Suitable" : "Not suitable";
  }
  return table.available_seats >= groupSize ? `Suitable for ${groupSize}` : "Not suitable";
}

export function FallbackListView(props: FallbackListViewProps): JSX.Element {
  const { tables, studyMode, groupSize, onSelectTable } = props;

  return (
    <section className="card list-card">
      <h2>Fallback List View</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Table</th>
              <th>Zone</th>
              <th>Seats</th>
              <th>Status</th>
              <th>Fit</th>
            </tr>
          </thead>
          <tbody>
            {tables.map((table) => (
              <tr key={table.table_id} onClick={() => onSelectTable(table.table_id)}>
                <td>{table.table_id}</td>
                <td>{table.zone_name}</td>
                <td>
                  {table.available_seats}/{table.total_seats}
                </td>
                <td>{statusLabel(table.status)}</td>
                <td>{suitability(table, studyMode, groupSize)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
