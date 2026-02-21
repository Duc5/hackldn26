import type { MapLayout } from "../types/seatsense";

export const mapLayout: MapLayout = {
  zones: [
    { id: "quiet", name: "Quiet Zone", zone_type: "quiet", x: 3, y: 8, width: 38, height: 38 },
    { id: "reading", name: "Reading Room", zone_type: "mixed", x: 44, y: 8, width: 25, height: 38 },
    { id: "group", name: "Group Area", zone_type: "group", x: 71, y: 8, width: 26, height: 52 },
    { id: "open", name: "Open Study", zone_type: "mixed", x: 3, y: 49, width: 66, height: 43 }
  ],
  tables: [
    { table_id: "Q1", zone_id: "quiet", x: 7, y: 16, width: 10, height: 11 },
    { table_id: "Q2", zone_id: "quiet", x: 20, y: 16, width: 10, height: 11 },
    { table_id: "Q3", zone_id: "quiet", x: 32, y: 16, width: 8, height: 11 },
    { table_id: "R1", zone_id: "reading", x: 47, y: 16, width: 9, height: 11 },
    { table_id: "R2", zone_id: "reading", x: 58, y: 16, width: 9, height: 11 },
    { table_id: "R3", zone_id: "reading", x: 52, y: 31, width: 9, height: 11 },
    { table_id: "G1", zone_id: "group", x: 74, y: 16, width: 10, height: 11 },
    { table_id: "G2", zone_id: "group", x: 86, y: 16, width: 9, height: 11 },
    { table_id: "G3", zone_id: "group", x: 74, y: 31, width: 10, height: 11 },
    { table_id: "G4", zone_id: "group", x: 86, y: 31, width: 9, height: 11 },
    { table_id: "O1", zone_id: "open", x: 8, y: 58, width: 12, height: 12 },
    { table_id: "O2", zone_id: "open", x: 24, y: 58, width: 12, height: 12 },
    { table_id: "O3", zone_id: "open", x: 40, y: 58, width: 12, height: 12 },
    { table_id: "O4", zone_id: "open", x: 56, y: 58, width: 10, height: 12 },
    { table_id: "O5", zone_id: "open", x: 8, y: 74, width: 10, height: 12 },
    { table_id: "O6", zone_id: "open", x: 20, y: 74, width: 10, height: 12 },
    { table_id: "O7", zone_id: "open", x: 32, y: 74, width: 10, height: 12 },
    { table_id: "O8", zone_id: "open", x: 44, y: 74, width: 10, height: 12 },
    { table_id: "O9", zone_id: "open", x: 56, y: 74, width: 10, height: 12 }
  ]
};
