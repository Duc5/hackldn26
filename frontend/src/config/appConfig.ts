export const APP_CONFIG = {
  appName: "SeatSense",
  pollIntervalMs: 2000,
  apiBaseUrl: import.meta.env.VITE_SEATSENSE_API_URL ?? "http://localhost:8000",
  endpointPath: import.meta.env.VITE_SEATSENSE_ENDPOINT_PATH ?? "/api/tables",
  requestTimeoutMs: 2500
};
