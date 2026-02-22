import { useEffect, useMemo, useState } from "react";
import { APP_CONFIG } from "../config/appConfig";
import type { GlobalSummary, RoomSeriesPoint, RoomSummary } from "../types/analytics";

type MetricKey = "occupancy_pct" | "avg_noise_db" | "avg_temp_c";
type RangeKey = "1d" | "7d" | "14d";

const RANGE_TO_DAYS: Record<RangeKey, number> = {
  "1d": 1,
  "7d": 7,
  "14d": 14
};

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value: number, digits = 1): string {
  return Number.isFinite(value) ? value.toFixed(digits) : "-";
}

function Sparkline({
  points,
  metric
}: {
  points: RoomSeriesPoint[];
  metric: MetricKey;
}): JSX.Element {
  if (!points.length) {
    return <div className="sparkline-empty">No data yet</div>;
  }

  const values = points.map((p) => p[metric] as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 240;
  const height = 64;
  const pad = 6;

  const scaleX = (index: number) =>
    pad + (index / Math.max(1, values.length - 1)) * (width - pad * 2);
  const scaleY = (value: number) => {
    if (max === min) return height / 2;
    const pct = (value - min) / (max - min);
    return height - pad - pct * (height - pad * 2);
  };

  const path = values
    .map((v, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(v)}`)
    .join(" ");

  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Room trend">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

export function DashboardPage(): JSX.Element {
  const [summary, setSummary] = useState<GlobalSummary | null>(null);
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [metric, setMetric] = useState<MetricKey>("occupancy_pct");
  const [range, setRange] = useState<RangeKey>("14d");
  const [series, setSeries] = useState<RoomSeriesPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [seriesLoading, setSeriesLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchCore = async () => {
      try {
        setLoading(true);
        const base = APP_CONFIG.apiBaseUrl;
        const [summaryRes, roomsRes] = await Promise.all([
          fetch(`${base}/api/analytics/summary`),
          fetch(`${base}/api/rooms`)
        ]);

        if (!summaryRes.ok || !roomsRes.ok) {
          throw new Error("Dashboard data unavailable");
        }

        const [summaryJson, roomsJson] = await Promise.all([summaryRes.json(), roomsRes.json()]);

        if (cancelled) return;
        setSummary(summaryJson as GlobalSummary);
        setRooms(roomsJson as RoomSummary[]);
        setError(null);

        if (!selectedRoomId && (roomsJson as RoomSummary[]).length > 0) {
          setSelectedRoomId((roomsJson as RoomSummary[])[0].room_id);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load dashboard data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void fetchCore();
    const intervalId = window.setInterval(fetchCore, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [selectedRoomId]);

  useEffect(() => {
    if (!selectedRoomId) return;
    let cancelled = false;

    const fetchSeries = async () => {
      try {
        setSeriesLoading(true);
        const base = APP_CONFIG.apiBaseUrl;
        const days = RANGE_TO_DAYS[range];
        const response = await fetch(
          `${base}/api/analytics/db/rooms/${selectedRoomId}/series?days=${days}&limit=1500`
        );
        if (!response.ok) {
          throw new Error("Room series unavailable");
        }
        const json = (await response.json()) as { snapshots: RoomSeriesPoint[] };
        if (!cancelled) {
          const snapshots = json.snapshots ?? [];
          setSeries([...snapshots].reverse());
        }
      } catch (err) {
        if (!cancelled) {
          setSeries([]);
        }
      } finally {
        if (!cancelled) setSeriesLoading(false);
      }
    };

    void fetchSeries();
    return () => {
      cancelled = true;
    };
  }, [selectedRoomId, range]);

  const roomLookup = useMemo(() => {
    const map = new Map<string, RoomSummary>();
    rooms.forEach((room) => map.set(room.room_id, room));
    return map;
  }, [rooms]);

  const avgRoomOccupancy = useMemo(() => {
    if (!rooms.length) return 0;
    return rooms.reduce((acc, room) => acc + room.occupancy_pct, 0) / rooms.length;
  }, [rooms]);

  const avgRoomNoise = useMemo(() => {
    if (!rooms.length) return 0;
    return rooms.reduce((acc, room) => acc + room.avg_noise_db, 0) / rooms.length;
  }, [rooms]);

  const avgRoomTemp = useMemo(() => {
    if (!rooms.length) return 0;
    return rooms.reduce((acc, room) => acc + room.avg_temp_c, 0) / rooms.length;
  }, [rooms]);

  const selectedRoom = selectedRoomId ? roomLookup.get(selectedRoomId) ?? null : null;

  return (
    <section className="dashboard-shell">
      <div className="card dashboard-header">
        <div>
          <p className="eyebrow">Operations Dashboard</p>
          <h2 className="dashboard-title">SpaceSync Analytics</h2>
          <p className="subtitle">
            Track occupancy, comfort, and noise trends across all rooms. Toggle a room to see
            two-week historical patterns.
          </p>
        </div>
        <div className="dashboard-meta">
          {loading ? <span className="muted">Refreshing data…</span> : null}
          {error ? <span className="status-error">{error}</span> : null}
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="card stat-grid">
          <div className="stat-card">
            <p className="stat-label">Total Occupancy</p>
            <h3>{summary ? formatPercent(summary.occupancy_pct) : "--"}</h3>
            <span className="muted">
              {summary ? `${summary.occupied_desks}/${summary.total_desks} desks` : "—"}
            </span>
          </div>
          <div className="stat-card">
            <p className="stat-label">Avg Room Occupancy</p>
            <h3>{formatPercent(avgRoomOccupancy)}</h3>
            <span className="muted">{rooms.length ? `${rooms.length} rooms` : "—"}</span>
          </div>
          <div className="stat-card">
            <p className="stat-label">Avg Room Noise</p>
            <h3>{formatNumber(avgRoomNoise)} dB</h3>
            <span className="muted">Quiet target &lt; 65 dB</span>
          </div>
          <div className="stat-card">
            <p className="stat-label">Avg Room Temp</p>
            <h3>{formatNumber(avgRoomTemp)}°C</h3>
            <span className="muted">Comfort band 20–23°C</span>
          </div>
        </div>

        <div className="card trend-card">
          <div className="trend-head">
            <div>
              <p className="stat-label">Room Trends</p>
              <h3>{selectedRoom ? selectedRoom.label : "Select a room"}</h3>
              <p className="muted">
                {selectedRoom
                  ? `${formatPercent(selectedRoom.occupancy_pct)} occupied · ${formatNumber(
                      selectedRoom.avg_noise_db
                    )} dB · ${formatNumber(selectedRoom.avg_temp_c)}°C`
                  : "No room selected"}
              </p>
            </div>
            <div className="trend-controls">
              <div className="segmented">
                {(["occupancy_pct", "avg_noise_db", "avg_temp_c"] as MetricKey[]).map((key) => (
                  <button
                    key={key}
                    className={metric === key ? "active" : ""}
                    onClick={() => setMetric(key)}
                    type="button"
                  >
                    {key === "occupancy_pct" ? "Occupancy" : key === "avg_noise_db" ? "Noise" : "Temp"}
                  </button>
                ))}
              </div>
              <div className="segmented">
                {(["1d", "7d", "14d"] as RangeKey[]).map((key) => (
                  <button
                    key={key}
                    className={range === key ? "active" : ""}
                    onClick={() => setRange(key)}
                    type="button"
                  >
                    {key.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="trend-body">
            {seriesLoading ? (
              <span className="muted">Loading series…</span>
            ) : (
              <Sparkline points={series} metric={metric} />
            )}
            <div className="trend-stats">
              <div>
                <p className="stat-label">Latest</p>
                <strong>
                  {series.length
                    ? metric === "occupancy_pct"
                      ? formatPercent(series[series.length - 1][metric])
                      : `${formatNumber(series[series.length - 1][metric])}${
                          metric === "avg_temp_c" ? "°C" : " dB"
                        }`
                    : "—"}
                </strong>
              </div>
              <div>
                <p className="stat-label">Range</p>
                <strong>{range.toUpperCase()}</strong>
              </div>
              <div>
                <p className="stat-label">Samples</p>
                <strong>{series.length}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card room-table-card">
        <div className="map-head">
          <h2>Room Averages</h2>
          <span className="muted">Click a room to inspect its trendline.</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Room</th>
                <th>Status</th>
                <th>Occupancy</th>
                <th>Avg Noise</th>
                <th>Avg Temp</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((room) => (
                <tr
                  key={room.room_id}
                  onClick={() => setSelectedRoomId(room.room_id)}
                  style={{
                    fontWeight: room.room_id === selectedRoomId ? 700 : 500
                  }}
                >
                  <td>{room.label}</td>
                  <td>{room.status}</td>
                  <td>{formatPercent(room.occupancy_pct)}</td>
                  <td>{formatNumber(room.avg_noise_db)} dB</td>
                  <td>{formatNumber(room.avg_temp_c)}°C</td>
                </tr>
              ))}
              {!rooms.length ? (
                <tr>
                  <td colSpan={5} className="muted">
                    No rooms available.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
