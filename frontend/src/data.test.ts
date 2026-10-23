import { describe, it, expect } from "vitest";
import {
  maintenanceWindows,
  spareInventory,
  componentIdFor,
} from "./data";

describe("test harness smoke", () => {
  it("runs", () => {
    expect(true).toBe(true);
  });
});

describe("action mock data", () => {
  it("exposes at least one maintenance window", () => {
    expect(maintenanceWindows.length).toBeGreaterThan(0);
  });

  it("returns a numeric spare count for PSU-2 / rack C7", () => {
    const id = componentIdFor("PSU-2, rack C7");
    expect(id).toBe("C7");
    expect(typeof spareInventory[id]).toBe("number");
    expect(spareInventory[id]).toBe(3);
  });
});
