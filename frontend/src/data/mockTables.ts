import type { TableData } from "../types/seatsense";

const now = () => new Date().toISOString();

export const mockTables: TableData[] = [
  { table_id: "Q1", zone_name: "Quiet Zone", zone_type: "quiet", total_seats: 4, occupied_seats: 1, available_seats: 3, status: "available", last_updated: now() },
  { table_id: "Q2", zone_name: "Quiet Zone", zone_type: "quiet", total_seats: 4, occupied_seats: 2, available_seats: 2, status: "partial", last_updated: now() },
  { table_id: "Q3", zone_name: "Quiet Zone", zone_type: "quiet", total_seats: 2, occupied_seats: 2, available_seats: 0, status: "full", last_updated: now() },
  { table_id: "R1", zone_name: "Reading Room", zone_type: "mixed", total_seats: 6, occupied_seats: 4, available_seats: 2, status: "partial", last_updated: now() },
  { table_id: "R2", zone_name: "Reading Room", zone_type: "mixed", total_seats: 6, occupied_seats: 5, available_seats: 1, status: "partial", last_updated: now() },
  { table_id: "R3", zone_name: "Reading Room", zone_type: "mixed", total_seats: 6, occupied_seats: 2, available_seats: 4, status: "available", last_updated: now() },
  { table_id: "G1", zone_name: "Group Area", zone_type: "group", total_seats: 6, occupied_seats: 1, available_seats: 5, status: "available", last_updated: now() },
  { table_id: "G2", zone_name: "Group Area", zone_type: "group", total_seats: 6, occupied_seats: 4, available_seats: 2, status: "partial", last_updated: now() },
  { table_id: "G3", zone_name: "Group Area", zone_type: "group", total_seats: 8, occupied_seats: 8, available_seats: 0, status: "full", last_updated: now() },
  { table_id: "G4", zone_name: "Group Area", zone_type: "group", total_seats: 8, occupied_seats: 3, available_seats: 5, status: "available", last_updated: now() },
  { table_id: "O1", zone_name: "Open Study", zone_type: "mixed", total_seats: 4, occupied_seats: 2, available_seats: 2, status: "partial", last_updated: now() },
  { table_id: "O2", zone_name: "Open Study", zone_type: "mixed", total_seats: 4, occupied_seats: 1, available_seats: 3, status: "available", last_updated: now() },
  { table_id: "O3", zone_name: "Open Study", zone_type: "mixed", total_seats: 4, occupied_seats: 4, available_seats: 0, status: "full", last_updated: now() },
  { table_id: "O4", zone_name: "Open Study", zone_type: "mixed", total_seats: 6, occupied_seats: 2, available_seats: 4, status: "available", last_updated: now() },
  { table_id: "O5", zone_name: "Open Study", zone_type: "mixed", total_seats: 4, occupied_seats: 3, available_seats: 1, status: "partial", last_updated: now() },
  { table_id: "O6", zone_name: "Open Study", zone_type: "mixed", total_seats: 4, occupied_seats: 0, available_seats: 4, status: "available", last_updated: now() },
  { table_id: "O7", zone_name: "Open Study", zone_type: "mixed", total_seats: 4, occupied_seats: 2, available_seats: 2, status: "partial", last_updated: now() },
  { table_id: "O8", zone_name: "Open Study", zone_type: "mixed", total_seats: 6, occupied_seats: 5, available_seats: 1, status: "partial", last_updated: now() },
  { table_id: "O9", zone_name: "Open Study", zone_type: "mixed", total_seats: 6, occupied_seats: 1, available_seats: 5, status: "available", last_updated: now() }
];
