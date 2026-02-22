import { useEffect, useState } from "react";
import { APP_CONFIG } from "../../config/appConfig";
import type { TableData } from "../../types/seatsense";
import { statusLabel } from "../../utils/tableStatus";

interface TableDetailsCardProps {
  table: TableData | null;
}

interface DeskSensorDetails {
  desk_id: string;
  occupied: number;
  noise_db: number;
  temp_c: number;
  sensor_distance_cm?: number;
  sensor_motion?: number;
}

export function TableDetailsCard({ table }: TableDetailsCardProps): JSX.Element {
  const [sensorDetails, setSensorDetails] = useState<DeskSensorDetails | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (!table || table.table_id !== "Q1") {
      setSensorDetails(null);
      return () => {
        cancelled = true;
      };
    }

    const fetchQ1Details = async () => {
      try {
        const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/desks/desk_1`);
        if (!response.ok) return;
        const json = (await response.json()) as DeskSensorDetails;
        if (!cancelled) setSensorDetails(json);
      } catch {
        if (!cancelled) setSensorDetails(null);
      }
    };

    void fetchQ1Details();
    return () => {
      cancelled = true;
    };
  }, [table]);

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
      {table.table_id === "Q1" && sensorDetails ? (
        <>
          <h3 className="details-subhead">Live Sensor Feed (Q1)</h3>
          <ul className="details-list">
            <li>Occupied: {sensorDetails.occupied === 1 ? "Yes" : "No"}</li>
            <li>Sound (dBrel): {sensorDetails.noise_db} dB</li>
            <li>Motion: {sensorDetails.sensor_motion === 1 ? "Detected" : "None"}</li>
            <li>
              Distance: {typeof sensorDetails.sensor_distance_cm === "number" ? `${sensorDetails.sensor_distance_cm} cm` : "—"}
            </li>
          </ul>
        </>
      ) : null}
    </section>
  );
}
