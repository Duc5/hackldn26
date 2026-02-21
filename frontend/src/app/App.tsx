import { useMemo, useState } from "react";
import { ErrorBanner } from "../components/common/ErrorBanner";
import { LoadingState } from "../components/common/LoadingState";
import { GroupSizeSelector } from "../components/controls/GroupSizeSelector";
import { StudyModeToggle } from "../components/controls/StudyModeToggle";
import { ZoneFilterChips } from "../components/controls/ZoneFilterChips";
import { TableDetailsCard } from "../components/details/TableDetailsCard";
import { FallbackListView } from "../components/fallback/FallbackListView";
import { Header } from "../components/layout/Header";
import { LiveStatusBadge } from "../components/layout/LiveStatusBadge";
import { LibraryMap } from "../components/map/LibraryMap";
import { RecommendationPanel } from "../components/recommendations/RecommendationPanel";
import { useSeatSenseData } from "../hooks/useSeatSenseData";
import type { StudyMode, TableData, ZoneType } from "../types/seatsense";
import { getRecommendations, tableMatchesMode } from "../utils/recommendationEngine";

function toggleZone(current: ZoneType[], zone: ZoneType): ZoneType[] {
  return current.includes(zone) ? current.filter((z) => z !== zone) : [...current, zone];
}

function applyZoneFilters(tables: TableData[], filters: ZoneType[]): TableData[] {
  if (filters.length === 0) return tables;
  return tables.filter((table) => filters.includes(table.zone_type));
}

export default function App(): JSX.Element {
  const [studyMode, setStudyMode] = useState<StudyMode>("solo");
  const [groupSize, setGroupSize] = useState<number>(3);
  const [zoneFilters, setZoneFilters] = useState<ZoneType[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null);

  const { tables, sourceMode, loading, error, lastUpdated } = useSeatSenseData();

  const filteredTables = useMemo(() => applyZoneFilters(tables, zoneFilters), [tables, zoneFilters]);

  const recommendations = useMemo(
    () => getRecommendations({ tables: filteredTables, studyMode, groupSize, zoneFilters }),
    [filteredTables, studyMode, groupSize, zoneFilters]
  );

  const recommendedTableIds = useMemo(
    () => new Set(recommendations.map((rec) => rec.table.table_id)),
    [recommendations]
  );

  const dimmedTableIds = useMemo(() => {
    const ids = new Set<string>();
    for (const table of tables) {
      const zoneMismatch = zoneFilters.length > 0 && !zoneFilters.includes(table.zone_type);
      const modeMismatch = !tableMatchesMode(table, studyMode, groupSize);
      if (zoneMismatch || modeMismatch) {
        ids.add(table.table_id);
      }
    }
    return ids;
  }, [tables, zoneFilters, studyMode, groupSize]);

  const selectedTable = useMemo(
    () => tables.find((table) => table.table_id === selectedTableId) ?? null,
    [tables, selectedTableId]
  );

  return (
    <main className="page-shell">
      <div className="top-grid">
        <Header />
        <LiveStatusBadge sourceMode={sourceMode} loading={loading} error={error} lastUpdated={lastUpdated} />
      </div>

      <section className="card controls-card">
        <StudyModeToggle value={studyMode} onChange={setStudyMode} />
        {studyMode === "group" ? <GroupSizeSelector value={groupSize} onChange={setGroupSize} /> : null}
        <ZoneFilterChips selected={zoneFilters} onToggle={(zone) => setZoneFilters((prev) => toggleZone(prev, zone))} />
      </section>

      {loading ? <LoadingState /> : null}
      {error ? <ErrorBanner message="Using demo data fallback while backend reconnects." /> : null}

      <section className="content-grid">
        <LibraryMap
          tables={tables}
          dimmedTableIds={dimmedTableIds}
          recommendedTableIds={recommendedTableIds}
          selectedTableId={selectedTableId}
          onSelectTable={setSelectedTableId}
        />

        <div className="side-stack">
          <RecommendationPanel
            recommendations={recommendations}
            studyMode={studyMode}
            groupSize={groupSize}
            onSelectTable={setSelectedTableId}
          />
          <TableDetailsCard table={selectedTable} />
        </div>
      </section>

      <FallbackListView
        tables={filteredTables}
        studyMode={studyMode}
        groupSize={groupSize}
        onSelectTable={setSelectedTableId}
      />
    </main>
  );
}
