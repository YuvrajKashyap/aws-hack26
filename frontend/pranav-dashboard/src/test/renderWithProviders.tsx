import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ActionProvider } from "../ActionContext";

/** Renders UI inside the router + shared action-state providers. */
export function renderWithProviders(
  ui: ReactElement,
  { route = "/" }: { route?: string } = {},
) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ActionProvider>{ui}</ActionProvider>
    </MemoryRouter>,
  );
}
