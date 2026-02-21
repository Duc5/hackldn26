export type TableStatus = "available" | "partial" | "full";
export type ZoneType = "quiet" | "group" | "mixed";
export type StudyMode = "solo" | "group";
export type SourceMode = "live" | "hybrid" | "demo";

export interface TableData {
  table_id: string;
  zone_name: string;
  zone_type: ZoneType;
  total_seats: number;
  occupied_seats: number;
  available_seats: number;
  status: TableStatus;
  last_updated: string;
}

export interface MapZone {
  id: string;
  name: string;
  zone_type: ZoneType;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface MapTableLayout {
  table_id: string;
  zone_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface MapLayout {
  zones: MapZone[];
  tables: MapTableLayout[];
}

export interface Recommendation {
  table: TableData;
  score: number;
  reason: string;
  secondaryTag?: string;
}
