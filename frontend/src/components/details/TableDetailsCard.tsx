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

interface DeviceStatusItem {
  desk_id: string;
  current_port?: string | null;
  plugged_in: boolean;
  thread_alive: boolean;
}

interface DeviceListResponse {
  registered_devices: DeviceStatusItem[];
}

export function TableDetailsCard({ table }: TableDetailsCardProps): JSX.Element {
  const [sensorDetails, setSensorDetails] = useState<DeskSensorDetails | null>(null);
  const [q1Connection, setQ1Connection] = useState<{ connected: boolean; port: string | null } | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (!table || table.table_id !== "Q1") {
      setSensorDetails(null);
      setQ1Connection(null);
      return () => {
        cancelled = true;
      };
    }

    const fetchQ1Details = async () => {
      try {
        const [deskResponse, devicesResponse] = await Promise.all([
          fetch(`${APP_CONFIG.apiBaseUrl}/api/desks/desk_1`),
          fetch(`${APP_CONFIG.apiBaseUrl}/api/devices`)
        ]);

        if (deskResponse.ok) {
          const deskJson = (await deskResponse.json()) as DeskSensorDetails;
          if (!cancelled) setSensorDetails(deskJson);
        }

        if (devicesResponse.ok) {
          const devicesJson = (await devicesResponse.json()) as DeviceListResponse;
          const q1Device = devicesJson.registered_devices.find((device) => device.desk_id === "desk_1");
          if (!cancelled) {
            setQ1Connection(
              q1Device
                ? {
                    connected: Boolean(q1Device.plugged_in && q1Device.thread_alive),
                    port: q1Device.current_port ?? null
                  }
                : { connected: false, port: null }
            );
          }
        }
      } catch {
        if (!cancelled) {
          setSensorDetails(null);
          setQ1Connection(null);
        }
      }
    };

    void fetchQ1Details();
    const intervalId = window.setInterval(() => {
      void fetchQ1Details();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
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
          <div className="details-status-row">
            <span className={`mode-badge ${q1Connection?.connected ? "mode-live" : "mode-demo"}`}>
              {q1Connection?.connected ? "ESP32 Connected" : "ESP32 Disconnected"}
            </span>
            <span className="muted">{q1Connection?.port ? `Port ${q1Connection.port}` : "Port unavailable"}</span>
          </div>
          <ul className="details-list">
            <li>Occupied: {sensorDetails.occupied === 1 ? "Yes" : "No"}</li>
            <li>Sound (dBrel): {sensorDetails.noise_db} dB</li>
            <li>Motion: {sensorDetails.sensor_motion === 1 ? "Detected" : "None"}</li>
            <li>
              Distance: {typeof sensorDetails.sensor_distance_cm === "number" ? `${sensorDetails.sensor_distance_cm} cm` : "--"}
            </li>
          </ul>
        </>
      ) : null}
    </section>
  );
}
