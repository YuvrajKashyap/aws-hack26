import { describe, it, expect } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { renderWithProviders } from "./test/renderWithProviders";

describe("App ACT navigation flow (integration)", () => {
  it("routes ACT to the action screen, syncs state back to the dashboard", async () => {
    renderWithProviders(<App />, { route: "/" });

    // Dashboard baseline: Open work orders = 1, no action buttons visible.
    const kpiCard = screen.getByText("Open work orders").closest(".card")!;
    expect(within(kpiCard as HTMLElement).getByText("1")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Dispatch technician" }),
    ).not.toBeInTheDocument();

    // Click ACT on the PSU-2 (rack C7) row -> navigate to the action screen.
    await userEvent.click(
      screen.getByRole("button", { name: "Act on PSU-2, rack C7" }),
    );
    expect(screen.getByText("Act on component")).toBeInTheDocument();

    // Perform an action; screen stays open.
    await userEvent.click(
      screen.getByRole("button", { name: "Dispatch technician" }),
    );
    expect(screen.getByText("Act on component")).toBeInTheDocument();

    // Back to dashboard: row badge present and KPI incremented 1 -> 2.
    await userEvent.click(
      screen.getByRole("button", { name: /Back to dashboard/ }),
    );
    expect(screen.getAllByText("Tech dispatched").length).toBeGreaterThan(0);
    const kpiCardAfter = screen.getByText("Open work orders").closest(".card")!;
    expect(
      within(kpiCardAfter as HTMLElement).getByText("2"),
    ).toBeInTheDocument();
  });

  it("announces the action via an aria-live region", async () => {
    renderWithProviders(<App />, { route: "/act/C7" });
    await userEvent.click(
      screen.getByRole("button", { name: "Order the part" }),
    );
    expect(screen.getByText(/Part ordered for/i)).toBeInTheDocument();
  });
});
