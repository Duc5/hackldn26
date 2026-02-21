import type { Recommendation, StudyMode, TableData, ZoneType } from "../types/seatsense";

interface RecommendationParams {
  tables: TableData[];
  studyMode: StudyMode;
  groupSize: number;
  zoneFilters: ZoneType[];
}

function qualifies(table: TableData, studyMode: StudyMode, groupSize: number): boolean {
  if (studyMode === "solo") {
    return table.available_seats >= 1;
  }
  return table.available_seats >= groupSize;
}

function scoreTable(table: TableData, studyMode: StudyMode, groupSize: number, zoneFilters: ZoneType[]): number {
  let score = table.available_seats * 10;

  if (studyMode === "group") {
    const oversupply = table.available_seats - groupSize;
    score += Math.max(0, 8 - oversupply * 2);
    if (table.zone_type === "group") {
      score += 10;
    }
  }

  if (studyMode === "solo" && table.zone_type === "quiet") {
    score += 6;
  }

  if (zoneFilters.length > 0 && zoneFilters.includes(table.zone_type)) {
    score += 8;
  }

  return score;
}

function buildReason(
  studyMode: StudyMode,
  groupSize: number,
  isTopFreeSeats: boolean
): { reason: string; secondaryTag?: string } {
  if (studyMode === "solo") {
    return {
      reason: "Best for solo study",
      secondaryTag: isTopFreeSeats ? "Most free seats" : "Quiet and focused"
    };
  }

  return {
    reason: `Good for group of ${groupSize}`,
    secondaryTag: isTopFreeSeats ? "Most free seats" : "Fits your group size"
  };
}

export function getRecommendations(params: RecommendationParams): Recommendation[] {
  const { tables, studyMode, groupSize, zoneFilters } = params;

  const zoneFiltered = zoneFilters.length
    ? tables.filter((table) => zoneFilters.includes(table.zone_type))
    : tables;

  const qualified = zoneFiltered.filter((table) => qualifies(table, studyMode, groupSize));
  if (qualified.length === 0) {
    return [];
  }

  const maxFreeSeats = Math.max(...qualified.map((table) => table.available_seats));

  return qualified
    .map((table) => {
      const score = scoreTable(table, studyMode, groupSize, zoneFilters);
      const reason = buildReason(studyMode, groupSize, table.available_seats === maxFreeSeats);
      return { table, score, ...reason };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);
}

export function tableMatchesMode(table: TableData, studyMode: StudyMode, groupSize: number): boolean {
  return qualifies(table, studyMode, groupSize);
}
