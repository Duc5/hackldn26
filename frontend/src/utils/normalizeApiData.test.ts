import { describe, expect, it } from "vitest";
import { normalizeApiData } from "./normalizeApiData";

describe("normalizeApiData", () => {
  it("normalizes tables payload shape and clamps values", () => {
    const input = {
      tables: [
        {
          table_id: "Q1",
          zone_name: "Quiet Zone",
          zone_type: "quiet",
          total_seats: 4,
          occupied_seats: 9,
          available_seats: -1
        }
      ]
    };

    const rows = normalizeApiData(input);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      table_id: "Q1",
      zone_type: "quiet",
      total_seats: 4,
      occupied_seats: 4,
      available_seats: 0,
      status: "full"
    });
  });
});
