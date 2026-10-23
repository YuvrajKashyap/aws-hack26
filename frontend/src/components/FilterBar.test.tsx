import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FilterBar } from "./FilterBar";
import { defaultFilters } from "../data";
import type { ComponentType, DashboardFilters } from "../types";

function setup(overrides?: Partial<DashboardFilters>) {
  const filters = { ...defaultFilters(), ...overrides };
  const onChange = vi.fn();
  render(<FilterBar filters={filters} onChange={onChange} />);
  return { filters, onChange };
}

describe("FilterBar", () => {
  it("shows 'All component types' when no types are selected", () => {
    setup();
    expect(screen.getByText("All component types")).toBeInTheDocument();
  });

  it("changing the hall select emits a new hallId", async () => {
    const { onChange } = setup();
    await userEvent.selectOptions(
      screen.getByRole("combobox"),
      "Hall 3",
    );
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ hallId: "hall-3" }),
    );
  });

  it("clicking a time-range option emits that range", async () => {
    const { onChange } = setup();
    await userEvent.click(screen.getByRole("radio", { name: "30 days" }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ timeRange: "30d" }),
    );
  });

  it("marks the active time range with aria-checked", () => {
    setup({ timeRange: "7d" });
    expect(screen.getByRole("radio", { name: "7 days" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("radio", { name: "14 days" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("toggling a component type adds it to the selection", async () => {
    const { onChange } = setup();
    await userEvent.click(screen.getByLabelText("PSU"));
    expect(onChange).toHaveBeenCalledTimes(1);
    const next = onChange.mock.calls[0][0] as DashboardFilters;
    expect([...next.componentTypes]).toContain<ComponentType>("psu");
  });

  it("summarizes the count when types are selected", () => {
    setup({ componentTypes: new Set<ComponentType>(["psu", "fan"]) });
    expect(screen.getByText("2 types selected")).toBeInTheDocument();
  });
});
