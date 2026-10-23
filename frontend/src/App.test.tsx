import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";

describe("App ACT flow (integration)", () => {
  it("reveals actions, badges the row, and bumps the Open work orders KPI", async () => {
    render(<App />);

    // Baseline KPI value is 1.
    const kpiCard = screen.getByText("Open work orders").closest(".card")!;
    expect(within(kpiCard as HTMLElement).getByText("1")).toBeInTheDocument();

    // Actions are hidden until ACT is clicked.
    expect(
      screen.queryByRole("button", { name: "Dispatch technician" }),
    ).not.toBeInTheDocument();

    // Click ACT on the PSU-2 (rack C7) row.
    await userEvent.click(
      screen.getByRole("button", { name: "Act on PSU-2, rack C7" }),
    );

    // Panel reveals the six actions.
    const dispatch = await screen.findByRole("button", {
      name: "Dispatch technician",
    });
    await userEvent.click(dispatch);

    // Row shows the status badge.
    expect(screen.getByText("Tech dispatched")).toBeInTheDocument();

    // Open work orders KPI incremented 1 -> 2.
    expect(within(kpiCard as HTMLElement).getByText("2")).toBeInTheDocument();
  });

  it("announces the action via an aria-live region", async () => {
    render(<App />);
    await userEvent.click(
      screen.getByRole("button", { name: "Act on PSU-2, rack C7" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Order the part" }),
    );
    expect(screen.getByText(/Part ordered for/i)).toBeInTheDocument();
  });
});
