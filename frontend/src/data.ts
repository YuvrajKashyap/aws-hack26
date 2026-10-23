import type {
  Kpi,
  Rack,
  RackStatus,
  ReplacementItem,
  SelectedComponent,
} from "./types";

export const location = {
  breadcrumb: "RACKSIGHT / DC-AUSTIN-1 / HALL 2",
  title: "Fleet health",
};

export const filters: string[] = ["Hall 2", "Next 14 days", "All component types"];

export const kpis: Kpi[] = [
  { label: "Fleet health score", value: "94.2", sub: "Sample data" },
  {
    label: "Components at risk",
    value: "4",
    sub: "2 critical, 2 watch",
    valueColor: "#FFB3AB",
  },
  { label: "Earliest predicted failure", value: "~3 days", sub: "PSU-2, rack C7" },
  { label: "Open work orders", value: "1", sub: "Drafted from alerts" },
];

/**
 * Rack map, rows A–E, racks 1–8. Rebuilt from the original mockup where
 * every cell is healthy unless listed as watch/critical below. C7 is the
 * selected cell.
 */
const watchCells = new Set([
  "A7",
  "B2",
  "B6",
  "C4",
  "D2",
  "D5",
  "D8",
  "E3",
  "E6",
]);
const criticalCells = new Set(["A3", "C7"]);

/** Rack highlighted when the dashboard first loads. */
export const defaultSelectedRackId = "C7";

export const racks: Rack[] = (() => {
  const rows = ["A", "B", "C", "D", "E"];
  const out: Rack[] = [];
  for (const row of rows) {
    for (let n = 1; n <= 8; n += 1) {
      const id = `${row}${n}`;
      let status: RackStatus = "healthy";
      if (criticalCells.has(id)) status = "critical";
      else if (watchCells.has(id)) status = "watch";
      out.push({ id, status });
    }
  }
  return out;
})();

export const replacementQueue: ReplacementItem[] = [
  {
    riskPct: 92,
    level: "critical",
    component: "PSU-2, rack C7",
    evidence: "12V rail ripple rising for 6 days",
  },
  {
    riskPct: 81,
    level: "critical",
    component: "NVMe drive 14, rack A3",
    evidence: "Reallocated sectors climbing",
  },
  {
    riskPct: 68,
    level: "watch",
    component: "Fan tray 3, rack B6",
    evidence: "RPM variance above baseline",
  },
  {
    riskPct: 54,
    level: "watch",
    component: "DIMM B4, rack D2",
    evidence: "Correctable ECC errors trending up",
  },
];

export const selectedComponent: SelectedComponent = {
  title: "PSU-2, rack C7",
  riskNote: "92% failure risk in ~3 days",
  cause:
    "Likely cause: capacitor aging under sustained load. Spare PSU in stock: 3 units.",
  chart: {
    ariaLabel:
      "Line chart showing 12V ripple climbing steadily and crossing the alert threshold",
    viewBox: "0 0 520 140",
    thresholdY: 40,
    points:
      "0,118 40,116 80,112 120,114 160,108 200,102 240,96 280,90 320,78 360,66 400,54 440,44 480,34 520,24",
    projectedPoints: "480,34 520,24",
    caption: "12V rail ripple, last 14 days (mV)",
  },
};

/** Maps a replacement-queue entry back to the rack it belongs to, e.g. "C7". */
function rackIdFromComponent(component: string): string | undefined {
  return component.match(/rack\s+([A-E]\d)/i)?.[1]?.toUpperCase();
}

/**
 * Canonical id used to key action state and inventory for a queue item.
 * Prefers the rack id (consistent with the rest of the app, e.g. "C7") and
 * falls back to the raw component string when no rack can be parsed.
 */
export function componentIdFor(component: string): string {
  return rackIdFromComponent(component) ?? component;
}

/** Mock maintenance windows an operator can schedule a swap into. */
export const maintenanceWindows: string[] = [
  "Fri 10/24, 02:00–04:00",
  "Sun 10/26, 01:00–05:00",
  "Wed 10/29, 03:00–04:30",
];

/**
 * Mock spare-part inventory keyed by component id (rack id). C7 has 3 spare
 * PSUs to match the authored "Spare PSU in stock: 3 units" narrative.
 */
export const spareInventory: Record<string, number> = {
  C7: 3,
  A3: 0,
  B6: 5,
  D2: 12,
};

const queueByRack: Record<string, ReplacementItem> = {};
for (const item of replacementQueue) {
  const rackId = rackIdFromComponent(item.component);
  if (rackId && !(rackId in queueByRack)) queueByRack[rackId] = item;
}

/** A flat, healthy baseline ripple trace used for racks with no active risk. */
const healthyChart: SelectedComponent["chart"] = {
  ariaLabel: "Line chart showing a steady 12V ripple well below the alert threshold",
  viewBox: "0 0 520 140",
  thresholdY: 40,
  points:
    "0,118 40,117 80,119 120,116 160,118 200,117 240,119 280,116 320,118 360,117 400,119 440,116 480,118 520,117",
  projectedPoints: "480,118 520,117",
  caption: "12V rail ripple, last 14 days (mV)",
};

/**
 * Builds the detail-panel content for any rack in the map. Critical/watch
 * racks reuse their ranked-queue evidence when available; healthy racks show
 * a nominal baseline. All data is simulated sample data.
 */
export function detailForRack(rackId: string): SelectedComponent {
  const rack = racks.find((r) => r.id === rackId);
  const status: RackStatus = rack?.status ?? "healthy";
  const queueItem = queueByRack[rackId];

  if (status === "critical") {
    // C7 keeps its richer, authored narrative.
    if (rackId === "C7") return selectedComponent;
    return {
      title: queueItem?.component ?? `Rack ${rackId}`,
      riskNote: queueItem ? `${queueItem.riskPct}% failure risk in ~7 days` : "Critical",
      cause: queueItem
        ? `Likely cause: ${queueItem.evidence.toLowerCase()}. Flagged for near-term replacement.`
        : "Component flagged critical. Inspect and schedule replacement.",
      chart: {
        ...selectedComponent.chart,
        ariaLabel: `Line chart for rack ${rackId} showing a measured value crossing the alert threshold`,
      },
    };
  }

  if (status === "watch") {
    return {
      title: queueItem?.component ?? `Rack ${rackId}`,
      riskNote: queueItem ? `${queueItem.riskPct}% failure risk` : "Watch: drifting from baseline",
      cause: queueItem
        ? `Likely cause: ${queueItem.evidence.toLowerCase()}. Monitoring for continued drift.`
        : "Readings drifting from baseline. Keep under observation.",
      chart: {
        ...healthyChart,
        points:
          "0,118 40,116 80,114 120,112 160,110 200,108 240,106 280,102 320,98 360,94 400,90 440,86 480,82 520,78",
        projectedPoints: "480,82 520,78",
        ariaLabel: `Line chart for rack ${rackId} showing a value drifting upward from baseline`,
      },
    };
  }

  return {
    title: `Rack ${rackId}`,
    riskNote: "Healthy",
    cause: "No active risk signals. All monitored components within baseline.",
    chart: {
      ...healthyChart,
      ariaLabel: `Line chart for rack ${rackId} showing a steady value below the alert threshold`,
    },
  };
}
