import { useState } from "react";
import type { ActionKind, ActionRecord } from "../types";
import { maintenanceWindows, spareInventory } from "../data";
import type { ActionPayload } from "../actions";

interface Props {
  /** Canonical id (rack id) of the component, e.g. "C7". */
  componentId: string;
  /** Display title, used in the inventory readout. */
  componentTitle: string;
  /** Actions already taken for this component. */
  actions: ActionRecord[];
  /** Reports a performed action up to the owner. */
  onPerform: (kind: ActionKind, payload?: ActionPayload) => void;
}

/** The four non-interactive actions, rendered as a simple button grid. */
const SIMPLE_ACTIONS: { kind: ActionKind; label: string; primary?: boolean }[] = [
  { kind: "dispatch_tech", label: "Dispatch technician" },
  { kind: "order_part", label: "Order the part" },
  { kind: "hire_contractor", label: "Hire contractor" },
  { kind: "work_order", label: "Create work order", primary: true },
];

/**
 * The remediation action surface: four simple actions plus two interactive
 * expanders (schedule a maintenance window, check spare inventory). Shared by
 * the dedicated action screen.
 */
export function ActionPanel({
  componentId,
  componentTitle,
  actions,
  onPerform,
}: Props) {
  const [openPanel, setOpenPanel] = useState<null | "schedule" | "inventory">(
    null,
  );
  const takenKinds = new Set(actions.map((a) => a.kind));
  const spareCount = spareInventory[componentId];

  return (
    <div className="actions">
      <div className="lbl">Remediation actions</div>
      <div className="actions__grid">
        {SIMPLE_ACTIONS.map((a) => {
          const done = takenKinds.has(a.kind);
          return (
            <button
              key={a.kind}
              type="button"
              className={`${a.primary ? "btn" : "btn2"}${
                done ? " action-done" : ""
              }`}
              aria-pressed={done}
              onClick={() => onPerform(a.kind)}
            >
              {done ? `✓ ${a.label}` : a.label}
            </button>
          );
        })}

        <button
          type="button"
          className="btn2"
          aria-expanded={openPanel === "schedule"}
          onClick={() =>
            setOpenPanel(openPanel === "schedule" ? null : "schedule")
          }
        >
          Schedule window
        </button>

        <button
          type="button"
          className="btn2"
          aria-expanded={openPanel === "inventory"}
          onClick={() =>
            setOpenPanel(openPanel === "inventory" ? null : "inventory")
          }
        >
          Check spare inventory
        </button>
      </div>

      {openPanel === "schedule" && (
        <div className="action-expand" role="group" aria-label="Maintenance windows">
          <div className="sub">Choose a maintenance window:</div>
          {maintenanceWindows.map((w) => (
            <button
              key={w}
              type="button"
              className="btn2"
              onClick={() => {
                onPerform("schedule_window", { window: w });
                setOpenPanel(null);
              }}
            >
              {w}
            </button>
          ))}
        </div>
      )}

      {openPanel === "inventory" && (
        <div className="action-expand" aria-label="Spare inventory">
          <div className="sub">
            {typeof spareCount === "number"
              ? `${componentTitle}: ${spareCount} in stock`
              : "No inventory data for this component."}
          </div>
          <button
            type="button"
            className="btn2"
            onClick={() => {
              onPerform("check_inventory");
              setOpenPanel(null);
            }}
          >
            Acknowledge
          </button>
        </div>
      )}
    </div>
  );
}
