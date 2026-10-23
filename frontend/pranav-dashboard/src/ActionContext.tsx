import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { kpis as baseKpis } from "./data";
import { addAction, openWorkOrderCount, badgeLabelFor } from "./actions";
import type { ActionPayload } from "./actions";
import type {
  ActionKind,
  ActionRecord,
  ComponentActionState,
  Kpi,
} from "./types";

/** Base "Open work orders" count parsed from the static KPI sample data. */
const OPEN_WORK_ORDERS_BASE = Number(
  baseKpis.find((k) => k.label === "Open work orders")?.value ?? "0",
);

interface ActionContextValue {
  /** All actions taken, keyed by component id. */
  actionState: ComponentActionState;
  /** KPI cards with the "Open work orders" value derived from actions. */
  kpis: Kpi[];
  /** Latest status message for screen-reader announcement. */
  announcement: string;
  /** Records an action against a component (e.g. the one in the URL). */
  perform: (
    componentId: string,
    componentTitle: string,
    kind: ActionKind,
    payload?: ActionPayload,
  ) => void;
  /** Actions recorded for a single component. */
  actionsFor: (componentId: string) => ActionRecord[];
}

const ActionContext = createContext<ActionContextValue | null>(null);

export function ActionProvider({ children }: { children: ReactNode }) {
  const [actionState, setActionState] = useState<ComponentActionState>({});
  const [announcement, setAnnouncement] = useState("");

  const perform = useCallback(
    (
      componentId: string,
      componentTitle: string,
      kind: ActionKind,
      payload?: ActionPayload,
    ) => {
      setActionState((prev) => addAction(prev, componentId, kind, payload));
      const label = badgeLabelFor(kind, payload);
      setAnnouncement(
        label
          ? `${label} for ${componentTitle}.`
          : `Inventory checked for ${componentTitle}.`,
      );
    },
    [],
  );

  const kpis = useMemo<Kpi[]>(() => {
    const openCount = openWorkOrderCount(OPEN_WORK_ORDERS_BASE, actionState);
    return baseKpis.map((k) =>
      k.label === "Open work orders" ? { ...k, value: String(openCount) } : k,
    );
  }, [actionState]);

  const actionsFor = useCallback(
    (componentId: string) => actionState[componentId] ?? [],
    [actionState],
  );

  const value = useMemo<ActionContextValue>(
    () => ({ actionState, kpis, announcement, perform, actionsFor }),
    [actionState, kpis, announcement, perform, actionsFor],
  );

  return (
    <ActionContext.Provider value={value}>{children}</ActionContext.Provider>
  );
}

/** Access the shared action state. Throws if used outside the provider. */
export function useActions(): ActionContextValue {
  const ctx = useContext(ActionContext);
  if (!ctx) throw new Error("useActions must be used within an ActionProvider");
  return ctx;
}
