import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { renderWithProviders } from "../test/renderWithProviders";
import { maintenanceWindows, spareInventory } from "../data";

describe("ActionScreen", () => {
  it("renders component context and all six actions", () => {
    renderWithProviders(<App />, { route: "/act/C7" });

    expect(screen.getByText("Act on component")).toBeInTheDocument();
    // PSU-2, rack C7 is the authored title for C7.
    expect(screen.getByText("PSU-2, rack C7")).toBeInTheDocument();

    for (const name of [
      "Dispatch technician",
      "Order the part",
      "Hire contractor",
      "Create work order",
      "Schedule window",
      "Check spare inventory",
    ]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("marks an action done and stays on the screen", async () => {
    renderWithProviders(<App />, { route: "/act/C7" });
    await userEvent.click(screen.getByRole("button", { name: "Order the part" }));
    // Still on the action screen; action now shows as done.
    expect(screen.getByText("Act on component")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "✓ Order the part" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("lets the user pick a maintenance window and records it", async () => {
    renderWithProviders(<App />, { route: "/act/C7" });
    await userEvent.click(screen.getByRole("button", { name: "Schedule window" }));
    await userEvent.click(
      screen.getByRole("button", { name: maintenanceWindows[0] }),
    );
    // Window chooser closes; still on the action screen.
    expect(
      screen.queryByRole("button", { name: maintenanceWindows[1] }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Act on component")).toBeInTheDocument();
    // Navigating back shows the scheduled badge on the dashboard.
    await userEvent.click(
      screen.getByRole("button", { name: /Back to dashboard/ }),
    );
    expect(
      screen.getAllByText(`Scheduled ${maintenanceWindows[0]}`).length,
    ).toBeGreaterThan(0);
  });

  it("shows the per-component spare count", async () => {
    renderWithProviders(<App />, { route: "/act/C7" });
    await userEvent.click(
      screen.getByRole("button", { name: "Check spare inventory" }),
    );
    expect(
      screen.getByText(new RegExp(`${spareInventory.C7} in stock`)),
    ).toBeInTheDocument();
  });

  it("navigates back to the dashboard", async () => {
    renderWithProviders(<App />, { route: "/act/C7" });
    await userEvent.click(
      screen.getByRole("button", { name: /Back to dashboard/ }),
    );
    // Dashboard-only UI appears.
    expect(screen.getByText("Replacement queue")).toBeInTheDocument();
  });
});
