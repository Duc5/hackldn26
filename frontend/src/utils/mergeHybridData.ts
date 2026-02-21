import type { SourceMode, TableData } from "../types/seatsense";

export function mergeHybridData(mock: TableData[], live: TableData[]): { tables: TableData[]; sourceMode: SourceMode } {
  if (live.length === 0) {
    return { tables: mock, sourceMode: "demo" };
  }

  const liveById = new Map(live.map((table) => [table.table_id, table]));
  let matchedCount = 0;
  const merged = mock.map((table) => {
    const liveRow = liveById.get(table.table_id);
    if (liveRow) {
      matchedCount += 1;
      return liveRow;
    }
    return table;
  });

  if (matchedCount === mock.length) {
    return { tables: merged, sourceMode: "live" };
  }

  if (matchedCount > 0) {
    return { tables: merged, sourceMode: "hybrid" };
  }

  return { tables: mock, sourceMode: "demo" };
}
