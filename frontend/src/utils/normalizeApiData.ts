import type { TableData, ZoneType } from "../types/seatsense";
import { computeStatus } from "./tableStatus";

function asNumber(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function parseZoneType(value: unknown): ZoneType {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "quiet" || normalized === "group" || normalized === "mixed") {
    return normalized;
  }
  return "mixed";
}

export function normalizeApiData(payload: unknown): TableData[] {
  const rows = Array.isArray(payload)
    ? payload
    : Array.isArray((payload as { tables?: unknown })?.tables)
      ? (payload as { tables: unknown[] }).tables
      : [];

  return rows
    .map((raw) => {
      const item = raw as Record<string, unknown>;
      const tableId = String(item.table_id ?? item.tableId ?? item.id ?? "").trim();
      if (!tableId) {
        return null;
      }

      const totalSeats = asNumber(item.total_seats ?? item.totalSeats ?? item.capacity);
      const occupiedSeats = asNumber(item.occupied_seats ?? item.occupiedSeats ?? item.occupied);
      const availableSeatsRaw = asNumber(item.available_seats ?? item.availableSeats ?? item.available);
      const safeTotal = totalSeats ?? 0;
      const safeOccupied = occupiedSeats ?? 0;
      const computedAvailable = Math.max(0, safeTotal - safeOccupied);
      const availableSeats = availableSeatsRaw ?? computedAvailable;
      const clampedAvailable = Math.max(0, Math.min(availableSeats, safeTotal));
      const noiseDb = asNumber(item.noise_db ?? item.noiseDb);
      const tempC = asNumber(item.temp_c ?? item.tempC);
      const roomAvgTempC = asNumber(item.room_avg_temp_c ?? item.roomAvgTempC);

      return {
        table_id: tableId,
        zone_name: String(item.zone_name ?? item.zoneName ?? "Unknown Zone"),
        zone_type: parseZoneType(item.zone_type ?? item.zoneType),
        total_seats: safeTotal,
        occupied_seats: Math.max(0, Math.min(safeOccupied, safeTotal)),
        available_seats: clampedAvailable,
        status: computeStatus(clampedAvailable, safeTotal),
        ...(noiseDb !== null ? { noise_db: Math.round(noiseDb) } : {}),
        ...(tempC !== null ? { temp_c: tempC } : {}),
        ...(roomAvgTempC !== null ? { room_avg_temp_c: roomAvgTempC } : {}),
        last_updated: String(item.last_updated ?? item.lastUpdated ?? new Date().toISOString())
      } satisfies TableData;
    })
    .filter((row): row is TableData => row !== null && row.total_seats > 0);
}
