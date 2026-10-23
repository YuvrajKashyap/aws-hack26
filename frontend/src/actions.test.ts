import { describe, it, expect } from "vitest";
import {
  addAction,
  badgeLabelFor,
  openWorkOrderCount,
  badgesForComponent,
  hasAction,
} from "./actions";
import type { ComponentActionState } from "./types";

describe("badgeLabelFor", () => {
  it("labels simple actions", () => {
    expect(badgeLabelFor("dispatch_tech")).toBe("Tech dispatched");
    expect(badgeLabelFor("order_part")).toBe("Part ordered");
    expect(badgeLabelFor("hire_contractor")).toBe("Contractor hired");
    expect(badgeLabelFor("work_order")).toBe("Work order drafted");
  });

  it("includes the chosen window for schedule_window", () => {
    expect(badgeLabelFor("schedule_window", { window: "Fri 10/24" })).toBe(
      "Scheduled Fri 10/24",
    );
    expect(badgeLabelFor("schedule_window")).toBe("Scheduled");
  });

  it("produces no badge for check_inventory", () => {
    expect(badgeLabelFor("check_inventory")).toBe("");
  });
});

describe("addAction", () => {
  it("does not mutate the input state", () => {
    const state: ComponentActionState = {};
    const next = addAction(state, "C7", "order_part");
    expect(state).toEqual({});
    expect(next.C7).toHaveLength(1);
  });

  it("records each action kind", () => {
    let state: ComponentActionState = {};
    state = addAction(state, "C7", "dispatch_tech");
    state = addAction(state, "C7", "order_part");
    expect(state.C7.map((r) => r.kind)).toEqual(["dispatch_tech", "order_part"]);
  });

  it("replaces rather than duplicates the same kind", () => {
    let state: ComponentActionState = {};
    state = addAction(state, "C7", "schedule_window", { window: "Fri 10/24" });
    state = addAction(state, "C7", "schedule_window", { window: "Sun 10/26" });
    expect(state.C7).toHaveLength(1);
    expect(state.C7[0].scheduledWindow).toBe("Sun 10/26");
    expect(state.C7[0].badgeLabel).toBe("Scheduled Sun 10/26");
  });

  it("stores scheduledWindow only for schedule_window", () => {
    const state = addAction({}, "C7", "order_part");
    expect(state.C7[0].scheduledWindow).toBeUndefined();
  });
});

describe("openWorkOrderCount", () => {
  it("returns the base count when no actions taken", () => {
    expect(openWorkOrderCount(1, {})).toBe(1);
  });

  it("counts work-order-generating actions on top of the base", () => {
    let state: ComponentActionState = {};
    state = addAction(state, "C7", "dispatch_tech"); // +1
    state = addAction(state, "A3", "work_order"); // +1
    state = addAction(state, "B6", "hire_contractor"); // +1
    expect(openWorkOrderCount(1, state)).toBe(4);
  });

  it("ignores non-work-order actions", () => {
    let state: ComponentActionState = {};
    state = addAction(state, "C7", "order_part");
    state = addAction(state, "C7", "check_inventory");
    state = addAction(state, "C7", "schedule_window", { window: "Fri 10/24" });
    expect(openWorkOrderCount(1, state)).toBe(1);
  });
});

describe("badgesForComponent", () => {
  it("returns only non-empty badges", () => {
    let state: ComponentActionState = {};
    state = addAction(state, "C7", "order_part");
    state = addAction(state, "C7", "check_inventory"); // empty badge
    expect(badgesForComponent(state, "C7")).toEqual(["Part ordered"]);
  });

  it("returns an empty array for unknown components", () => {
    expect(badgesForComponent({}, "Z9")).toEqual([]);
  });
});

describe("hasAction", () => {
  it("detects recorded actions", () => {
    const state = addAction({}, "C7", "order_part");
    expect(hasAction(state, "C7", "order_part")).toBe(true);
    expect(hasAction(state, "C7", "dispatch_tech")).toBe(false);
  });
});
