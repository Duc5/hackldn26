import { useEffect, useMemo, useRef, useState } from "react";
import { ErrorBanner } from "../components/common/ErrorBanner";
import { LoadingState } from "../components/common/LoadingState";
import { GroupSizeSelector } from "../components/controls/GroupSizeSelector";
import { StudyModeToggle } from "../components/controls/StudyModeToggle";
import { ZoneFilterChips } from "../components/controls/ZoneFilterChips";
import { TableDetailsCard } from "../components/details/TableDetailsCard";
import { FallbackListView } from "../components/fallback/FallbackListView";
import { LiveStatusBadge } from "../components/layout/LiveStatusBadge";
import { LibraryMap } from "../components/map/LibraryMap";
import { RecommendationPanel } from "../components/recommendations/RecommendationPanel";
import { DashboardPage } from "./DashboardPage";
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
  const [activePage, setActivePage] = useState<"live" | "dashboard">("live");
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

  const dashboardRef = useRef<HTMLElement | null>(null);
  const [heroDismissed, setHeroDismissed] = useState<boolean>(false);

  const scrollToDashboard = (): void => {
    dashboardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setHeroDismissed(true);
  };

  useEffect(() => {
    if (heroDismissed) return;

    let touchStartY = 0;
    const onWheel = (event: WheelEvent): void => {
      if (window.scrollY > 8 || event.deltaY <= 0) return;
      event.preventDefault();
      scrollToDashboard();
    };
    const onKeyDown = (event: KeyboardEvent): void => {
      if (window.scrollY > 8 || event.key !== "ArrowDown") return;
      event.preventDefault();
      scrollToDashboard();
    };

    const onTouchStart = (event: TouchEvent): void => {
      touchStartY = event.touches[0]?.clientY ?? 0;
    };

    const onTouchEnd = (event: TouchEvent): void => {
      if (window.scrollY > 8) return;
      const touchEndY = event.changedTouches[0]?.clientY ?? touchStartY;
      if (touchStartY - touchEndY > 24) scrollToDashboard();
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchend", onTouchEnd);
    };
  }, [heroDismissed]);

  return (
    <>
      <section className="hero-section">
        <div className="hero-inner">
          <h1 className="hero-title">Atmosense</h1>
          <button className="hero-scroll" type="button" aria-label="Scroll to dashboard" onClick={scrollToDashboard}>
            <span>Enter Dashboard</span>
            <span className="hero-arrow" aria-hidden="true">
              ↓
            </span>
          </button>
        </div>
      </section>

      <main ref={dashboardRef} className="page-shell dashboard-section">
        <section className="card controls-card">
          <div className="controls-main">
            <StudyModeToggle value={studyMode} onChange={setStudyMode} />
            {studyMode === "group" ? <GroupSizeSelector value={groupSize} onChange={setGroupSize} /> : null}
            <ZoneFilterChips
              selected={zoneFilters}
              onToggle={(zone) => setZoneFilters((prev) => toggleZone(prev, zone))}
            />
          </div>
          <LiveStatusBadge sourceMode={sourceMode} loading={loading} error={error} lastUpdated={lastUpdated} embedded />
        </section>

        <section className="card page-toggle">
          <div className="segmented">
            <button
              type="button"
              className={activePage === "live" ? "active" : ""}
              onClick={() => setActivePage("live")}
            >
              Live Map
            </button>
            <button
              type="button"
              className={activePage === "dashboard" ? "active" : ""}
              onClick={() => setActivePage("dashboard")}
            >
              Analytics
            </button>
          </div>
        </section>

        {activePage === "dashboard" ? (
          <DashboardPage />
        ) : (
          <>
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
          </>
        )}
      </main>
    </>
  );
}
