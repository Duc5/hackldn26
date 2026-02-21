import type { TableStatus } from "../types/seatsense";

export function computeStatus(availableSeats: number, totalSeats: number): TableStatus {
  if (availableSeats <= 0) {
    return "full";
  }
  if (availableSeats >= totalSeats) {
    return "available";
  }
  return "partial";
}

export function statusLabel(status: TableStatus): string {
  if (status === "available") return "Available";
  if (status === "partial") return "Partially Available";
  return "Full";
}
