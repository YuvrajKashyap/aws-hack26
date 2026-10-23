import { useMemo, useRef, useState } from "react";
import { TopBar } from "./components/TopBar";
import { KpiCards } from "./components/KpiCards";
import { RackMap } from "./components/RackMap";
import { ReplacementQueue } from "./components/ReplacementQueue";
import { ComponentDetail } from "./components/ComponentDetail";
import { defaultSelectedRackId, detailForRack, kpis as baseKpis } from "./data";
import { addAction, openWorkOrderCount, badgeLabelFor } from "./actions";
import type { ActionKind, ComponentActionState, Kpi } from "./types";
import type { ActionPayload } from "./actions";

/** Base "Open work orders" count parsed from the static KPI sample data. */
const OPEN_WORK_ORDERS_BASE = Number(
  baseKpis.find((k) => k.label === "Open work orders")?.value ?? "0",
);

export default function App() {
  const [selectedId, setSelectedId] = useState(defaultSelectedRackId);
  const [actionState, setActionState] = useState<ComponentActionState>({});
  const [revealed, setRevealed] = useState(false);
  const [announcement, setAnnouncement] = useState("");

  const detail = useMemo(() => detailForRack(selectedId), [selectedId]);
  const panelRef = useRef<HTMLDivElement>(null);

  // Clicking ACT on a row selects that component, reveals the action surface,
  // and moves focus to the panel so keyboard users land on the actions.
  function handleAct(componentId: string) {
    setSelectedId(componentId);
    setRevealed(true);
    requestAnimationFrame(() => {
      panelRef.current?.focus();
      panelRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }

  function handlePerform(kind: ActionKind, payload?: ActionPayload) {
    setActionState((prev) => addAction(prev, selectedId, kind, payload));
    const label = badgeLabelFor(kind, payload);
    setAnnouncement(
      label
        ? `${label} for ${detail.title}.`
        : `Inventory checked for ${detail.title}.`,
    );
  }

  // Derive the dynamic "Open work orders" KPI from recorded actions.
  const kpis = useMemo<Kpi[]>(() => {
    const openCount = openWorkOrderCount(OPEN_WORK_ORDERS_BASE, actionState);
    return baseKpis.map((k) =>
      k.label === "Open work orders"
        ? { ...k, value: String(openCount) }
        : k,
    );
  }, [actionState]);

  return (
    <div className="shell">
      <div className="wrap">
        <TopBar />
        <KpiCards kpis={kpis} />
        <div className="grid">
          <RackMap selectedId={selectedId} onSelect={setSelectedId} />
          <ReplacementQueue
            selectedId={selectedId}
            actionState={actionState}
            onAct={handleAct}
          />
        </div>
        <div ref={panelRef} tabIndex={-1} style={{ outline: "none" }}>
          <ComponentDetail
            component={detail}
            componentId={selectedId}
            actions={actionState[selectedId] ?? []}
            revealed={revealed}
            onPerform={handlePerform}
          />
        </div>
      </div>
      <div
        aria-live="polite"
        style={{
          position: "absolute",
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: "hidden",
          clip: "rect(0 0 0 0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      >
        {announcement}
      </div>
    </div>
  );
}
