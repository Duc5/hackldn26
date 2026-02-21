import { describe, expect, it } from "vitest";
import { mockTables } from "../data/mockTables";
import { mergeHybridData } from "./mergeHybridData";

describe("mergeHybridData", () => {
  it("stays in demo mode when no table ids match", () => {
    const live = [{ ...mockTables[0], table_id: "X1" }];
    const merged = mergeHybridData(mockTables, live);
    expect(merged.sourceMode).toBe("demo");
    expect(merged.tables).toEqual(mockTables);
  });

  it("returns hybrid mode when only subset matches", () => {
    const live = [mockTables[0], mockTables[1]];
    const merged = mergeHybridData(mockTables, live);
    expect(merged.sourceMode).toBe("hybrid");
    expect(merged.tables[0].table_id).toBe(mockTables[0].table_id);
  });
});
