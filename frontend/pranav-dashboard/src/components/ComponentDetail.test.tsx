import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComponentDetail } from "./ComponentDetail";
import { selectedComponent } from "../data";

describe("ComponentDetail (display-only)", () => {
  it("shows the component title and risk note", () => {
    render(
      <ComponentDetail
        component={selectedComponent}
        componentId="C7"
        actions={[]}
      />,
    );
    expect(screen.getByText(selectedComponent.title)).toBeInTheDocument();
    expect(screen.getByText(selectedComponent.riskNote)).toBeInTheDocument();
  });

  it("prompts to use ACT when no actions taken", () => {
    render(
      <ComponentDetail
        component={selectedComponent}
        componentId="C7"
        actions={[]}
      />,
    );
    expect(
      screen.getByText(/to choose a remediation/i),
    ).toBeInTheDocument();
  });

  it("summarizes taken actions as badges", () => {
    render(
      <ComponentDetail
        component={selectedComponent}
        componentId="C7"
        actions={[{ kind: "dispatch_tech", badgeLabel: "Tech dispatched" }]}
      />,
    );
    expect(screen.getByText("Tech dispatched")).toBeInTheDocument();
  });

  it("does not render any action buttons", () => {
    render(
      <ComponentDetail
        component={selectedComponent}
        componentId="C7"
        actions={[]}
      />,
    );
    expect(
      screen.queryByRole("button", { name: "Order the part" }),
    ).not.toBeInTheDocument();
  });
});
