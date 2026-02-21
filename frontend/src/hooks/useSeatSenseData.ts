import { useEffect, useMemo, useRef, useState } from "react";
import { APP_CONFIG } from "../config/appConfig";
import { mockTables } from "../data/mockTables";
import type { SourceMode, TableData } from "../types/seatsense";
import { mergeHybridData } from "../utils/mergeHybridData";
import { normalizeApiData } from "../utils/normalizeApiData";

interface SeatSenseDataState {
  tables: TableData[];
  sourceMode: SourceMode;
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
}

export function useSeatSenseData(): SeatSenseDataState {
  const [tables, setTables] = useState<TableData[]>(mockTables);
  const [sourceMode, setSourceMode] = useState<SourceMode>("demo");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    const poll = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), APP_CONFIG.requestTimeoutMs);

      try {
        const url = `${APP_CONFIG.apiBaseUrl}${APP_CONFIG.endpointPath}`;
        const response = await fetch(url, { signal: controller.signal });

        if (!response.ok) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const json = (await response.json()) as unknown;
        const liveRows = normalizeApiData(json);
        const merged = mergeHybridData(mockTables, liveRows);

        if (mountedRef.current) {
          setTables(merged.tables);
          setSourceMode(merged.sourceMode);
          setError(null);
          setLastUpdated(new Date().toISOString());
        }
      } catch (err) {
        if (mountedRef.current) {
          setTables(mockTables);
          setSourceMode("demo");
          setError(err instanceof Error ? err.message : "Live fetch failed, running demo mode");
          setLastUpdated(new Date().toISOString());
        }
      } finally {
        clearTimeout(timeout);
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    };

    void poll();
    const intervalId = window.setInterval(() => {
      void poll();
    }, APP_CONFIG.pollIntervalMs);

    return () => {
      mountedRef.current = false;
      window.clearInterval(intervalId);
    };
  }, []);

  return useMemo(
    () => ({ tables, sourceMode, loading, error, lastUpdated }),
    [tables, sourceMode, loading, error, lastUpdated]
  );
}
