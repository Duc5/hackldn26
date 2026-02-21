import { mapLayout } from "../../config/mapLayout";
import type { MapZone, TableData } from "../../types/seatsense";
import { MapLegend } from "./MapLegend";
import { TableNode } from "./TableNode";

interface LibraryMapProps {
  tables: TableData[];
  dimmedTableIds: Set<string>;
  recommendedTableIds: Set<string>;
  selectedTableId: string | null;
  onSelectTable: (id: string) => void;
}

function zoneClass(zone: MapZone): string {
  if (zone.zone_type === "quiet") return "zone quiet";
  if (zone.zone_type === "group") return "zone group";
  return "zone mixed";
}

export function LibraryMap(props: LibraryMapProps): JSX.Element {
  const { tables, dimmedTableIds, recommendedTableIds, selectedTableId, onSelectTable } = props;
  const byId = new Map(tables.map((table) => [table.table_id, table]));

  return (
    <section className="card map-card">
      <div className="map-head">
        <h2>Live Library Map</h2>
        <MapLegend />
      </div>

      <div className="map-stage">
        {mapLayout.zones.map((zone) => (
          <div
            key={zone.id}
            className={zoneClass(zone)}
            style={{ left: `${zone.x}%`, top: `${zone.y}%`, width: `${zone.width}%`, height: `${zone.height}%` }}
          >
            <span>{zone.name}</span>
          </div>
        ))}

        {mapLayout.tables.map((layout) => {
          const table = byId.get(layout.table_id);
          if (!table) return null;

          return (
            <TableNode
              key={layout.table_id}
              id={layout.table_id}
              x={layout.x}
              y={layout.y}
              width={layout.width}
              height={layout.height}
              seatsLabel={`${table.available_seats}/${table.total_seats} free`}
              status={table.status}
              dimmed={dimmedTableIds.has(table.table_id)}
              selected={selectedTableId === table.table_id}
              recommended={recommendedTableIds.has(table.table_id)}
              onClick={onSelectTable}
            />
          );
        })}
      </div>
    </section>
  );
}
