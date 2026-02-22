export interface GlobalSummary {
  total_desks: number;
  occupied_desks: number;
  available_desks: number;
  occupancy_pct: number;
  avg_noise_db: number;
  avg_temp_c: number;
  real_sensor_count: number;
  mock_desk_count: number;
  room_count: number;
}

export interface RoomSummary {
  room_id: string;
  label: string;
  status: string;
  avg_noise_db: number;
  avg_temp_c: number;
  occupancy_pct: number;
  total_desks: number;
  occupied_desks: number;
  suggestion?: string | null;
}

export interface RoomSeriesPoint {
  room_id: string;
  status: string;
  avg_noise_db: number;
  avg_temp_c: number;
  occupancy_pct: number;
  total_desks: number;
  occupied_desks: number;
  recorded_at: string;
}
