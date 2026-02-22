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

const OCCUPANCY_COLOR_STOPS = [
  { pct: 10, hex: "#FAF7F0" },
  { pct: 20, hex: "#F3EBDD" },
  { pct: 30, hex: "#E8D7BF" },
  { pct: 40, hex: "#D6D3CD" },
  { pct: 50, hex: "#CFE3D2" },
  { pct: 60, hex: "#9FC7A7" },
  { pct: 70, hex: "#6FA27A" },
  { pct: 80, hex: "#3F6F52" },
  { pct: 90, hex: "#6B4F3A" },
  { pct: 100, hex: "#3E2A20" }
] as const;

function zoneClass(zone: MapZone): string {
  if (zone.zone_type === "quiet") return "zone quiet";
  if (zone.zone_type === "group") return "zone group";
  return "zone mixed";
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const cleaned = hex.replace("#", "");
  return {
    r: Number.parseInt(cleaned.slice(0, 2), 16),
    g: Number.parseInt(cleaned.slice(2, 4), 16),
    b: Number.parseInt(cleaned.slice(4, 6), 16)
  };
}

function mixRgb(a: { r: number; g: number; b: number }, b: { r: number; g: number; b: number }, t: number) {
  return {
    r: Math.round(a.r + (b.r - a.r) * t),
    g: Math.round(a.g + (b.g - a.g) * t),
    b: Math.round(a.b + (b.b - a.b) * t)
  };
}

function rgbaString(rgb: { r: number; g: number; b: number }, alpha: number): string {
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
}

function relativeLuminance(rgb: { r: number; g: number; b: number }): number {
  const toLinear = (channel: number): number => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * toLinear(rgb.r) + 0.7152 * toLinear(rgb.g) + 0.0722 * toLinear(rgb.b);
}

function interpolatedOccupancyColor(occupancyPct: number): { r: number; g: number; b: number } {
  const pct = clamp(occupancyPct, 0, 100);
  if (pct <= OCCUPANCY_COLOR_STOPS[0].pct) return hexToRgb(OCCUPANCY_COLOR_STOPS[0].hex);

  for (let i = 0; i < OCCUPANCY_COLOR_STOPS.length - 1; i += 1) {
    const left = OCCUPANCY_COLOR_STOPS[i];
    const right = OCCUPANCY_COLOR_STOPS[i + 1];
    if (pct <= right.pct) {
      const t = (pct - left.pct) / (right.pct - left.pct);
      return mixRgb(hexToRgb(left.hex), hexToRgb(right.hex), t);
    }
  }

  return hexToRgb(OCCUPANCY_COLOR_STOPS[OCCUPANCY_COLOR_STOPS.length - 1].hex);
}

function formatZoneTemp(tables: TableData[]): string {
  if (tables.length === 0) return "--";
  const temps = tables
    .map((table) => table.temp_c ?? table.room_avg_temp_c)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (temps.length === 0) return "--";
  const avg = temps.reduce((sum, value) => sum + value, 0) / temps.length;
  return `${avg.toFixed(1)}°C`;
}

function getZoneMetrics(zoneId: string, tablesByZoneId: Map<string, TableData[]>): {
  occupancyPct: number;
  avgTempLabel: string;
  zoneBackground: string;
  zoneBorder: string;
  zoneHeaderBg: string;
  zoneText: string;
  zoneMutedText: string;
} {
  const zoneTables = tablesByZoneId.get(zoneId) ?? [];
  const totalSeats = zoneTables.reduce((sum, table) => sum + table.total_seats, 0);
  const occupiedSeats = zoneTables.reduce((sum, table) => sum + table.occupied_seats, 0);
  const occupancyPct = totalSeats > 0 ? Math.round((occupiedSeats / totalSeats) * 100) : 0;
  const color = interpolatedOccupancyColor(occupancyPct);
  const isDark = relativeLuminance(color) < 0.23;
  return {
    occupancyPct,
    avgTempLabel: formatZoneTemp(zoneTables),
    zoneBackground: `linear-gradient(160deg, ${rgbaString(color, 0.3)} 0%, ${rgbaString(color, 0.16)} 100%)`,
    zoneBorder: rgbaString(color, 0.5),
    zoneHeaderBg: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(255, 255, 255, 0.22)",
    zoneText: isDark ? "#f7f2e8" : "#23342d",
    zoneMutedText: isDark ? "rgba(247, 242, 232, 0.88)" : "#43574d"
  };
}

export function LibraryMap(props: LibraryMapProps): JSX.Element {
  const { tables, dimmedTableIds, recommendedTableIds, selectedTableId, onSelectTable } = props;
  const byId = new Map(tables.map((table) => [table.table_id, table]));
  const tablesByZoneId = new Map<string, TableData[]>();

  for (const layout of mapLayout.tables) {
    const table = byId.get(layout.table_id);
    if (!table) continue;
    const existing = tablesByZoneId.get(layout.zone_id);
    if (existing) {
      existing.push(table);
    } else {
      tablesByZoneId.set(layout.zone_id, [table]);
    }
  }

  return (
    <section className="card map-card">
      <div className="map-head">
        <h2>Live Library Map</h2>
        <MapLegend />
      </div>

      <div className="map-stage">
        {mapLayout.zones.map((zone) => {
          const metrics = getZoneMetrics(zone.id, tablesByZoneId);
          return (
            <div
              key={zone.id}
              className={zoneClass(zone)}
              style={{
                left: `${zone.x}%`,
                top: `${zone.y}%`,
                width: `${zone.width}%`,
                height: `${zone.height}%`,
                background: metrics.zoneBackground,
                borderColor: metrics.zoneBorder,
                ["--zone-text" as string]: metrics.zoneText,
                ["--zone-muted" as string]: metrics.zoneMutedText,
                ["--zone-header-bg" as string]: metrics.zoneHeaderBg
              }}
            >
              <div className="zone-header">
                <div className="zone-title-wrap">
                  <span className="zone-name">{zone.name}</span>
                  <span className="zone-occupancy">{metrics.occupancyPct}%</span>
                </div>
                <span className="zone-temp">{metrics.avgTempLabel}</span>
              </div>
            </div>
          );
        })}

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
