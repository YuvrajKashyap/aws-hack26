import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReplacementQueue } from "./ReplacementQueue";
import { replacementQueue, componentIdFor } from "../data";
import { addAction } from "../actions";

describe("ReplacementQueue", () => {
  it("renders an ACT button for every queue row", () => {
    render(
      <ReplacementQueue selectedId="C7" actionState={{}} onAct={() => {}} />,
    );
    const buttons = screen.getAllByRole("button", { name: /^Act on / });
    expect(buttons).toHaveLength(replacementQueue.length);
  });

  it("calls onAct with the component id when ACT is clicked", async () => {
    const onAct = vi.fn();
    render(
      <ReplacementQueue selectedId="C7" actionState={{}} onAct={onAct} />,
    );
    const first = replacementQueue[0];
    await userEvent.click(
      screen.getByRole("button", { name: `Act on ${first.component}` }),
    );
    expect(onAct).toHaveBeenCalledWith(componentIdFor(first.component));
  });

  it("shows a status badge when the component has an action", () => {
    const id = componentIdFor(replacementQueue[0].component);
    const state = addAction({}, id, "dispatch_tech");
    render(
      <ReplacementQueue selectedId="C7" actionState={state} onAct={() => {}} />,
    );
    expect(screen.getByText("Tech dispatched")).toBeInTheDocument();
  });

  it("does not show a badge for inventory-only checks", () => {
    const id = componentIdFor(replacementQueue[0].component);
    const state = addAction({}, id, "check_inventory");
    render(
      <ReplacementQueue selectedId="C7" actionState={state} onAct={() => {}} />,
    );
    // check_inventory has an empty badge label, so no badge pill appears.
    expect(screen.queryByText("Tech dispatched")).not.toBeInTheDocument();
  });
});
