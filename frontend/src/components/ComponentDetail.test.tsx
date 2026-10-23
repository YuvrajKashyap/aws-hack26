import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ComponentDetail } from "./ComponentDetail";
import { selectedComponent, maintenanceWindows, spareInventory } from "../data";

function renderDetail(
  overrides: Partial<React.ComponentProps<typeof ComponentDetail>> = {},
) {
  const onPerform = vi.fn();
  render(
    <ComponentDetail
      component={selectedComponent}
      componentId="C7"
      actions={[]}
      revealed
      onPerform={onPerform}
      {...overrides}
    />,
  );
  return { onPerform };
}

describe("ComponentDetail actions", () => {
  it("hides actions until revealed", () => {
    renderDetail({ revealed: false });
    expect(
      screen.queryByRole("button", { name: "Order the part" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/to choose a remediation/i),
    ).toBeInTheDocument();
  });

  it("renders all six actions when revealed", () => {
    renderDetail();
    expect(screen.getByRole("button", { name: "Dispatch technician" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Order the part" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hire contractor" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create work order" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schedule window" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check spare inventory" })).toBeInTheDocument();
  });

  it("fires onPerform for a simple action", async () => {
    const { onPerform } = renderDetail();
    await userEvent.click(screen.getByRole("button", { name: "Order the part" }));
    expect(onPerform).toHaveBeenCalledWith("order_part");
  });

  it("lets the user pick a maintenance window", async () => {
    const { onPerform } = renderDetail();
    await userEvent.click(screen.getByRole("button", { name: "Schedule window" }));
    const window = maintenanceWindows[1];
    await userEvent.click(screen.getByRole("button", { name: window }));
    expect(onPerform).toHaveBeenCalledWith("schedule_window", { window });
  });

  it("shows the per-component spare count on inventory check", async () => {
    renderDetail();
    await userEvent.click(
      screen.getByRole("button", { name: "Check spare inventory" }),
    );
    expect(
      screen.getByText(new RegExp(`${spareInventory.C7} in stock`)),
    ).toBeInTheDocument();
  });

  it("records a check_inventory action on acknowledge", async () => {
    const { onPerform } = renderDetail();
    await userEvent.click(
      screen.getByRole("button", { name: "Check spare inventory" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    expect(onPerform).toHaveBeenCalledWith("check_inventory");
  });

  it("marks already-taken actions as done", () => {
    renderDetail({
      actions: [{ kind: "order_part", badgeLabel: "Part ordered" }],
    });
    expect(
      screen.getByRole("button", { name: "✓ Order the part" }),
    ).toHaveAttribute("aria-pressed", "true");
  });
});
