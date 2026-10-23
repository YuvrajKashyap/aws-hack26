import type { ActionRecord, SelectedComponent } from "../types";
import { RippleChart } from "./RippleChart";
import { badgesForComponentRecords } from "../actions";

interface Props {
  component: SelectedComponent;
  /** Canonical id (rack id) of the selected component, e.g. "C7". */
  componentId: string;
  /** Actions already taken for this component, summarized as badges. */
  actions: ActionRecord[];
}

/**
 * Read-only detail panel for the selected component. Remediation actions now
 * live on the dedicated action screen (reached via the ACT button); this panel
 * summarizes any actions already taken.
 */
export function ComponentDetail({ component, actions }: Props) {
  const c = component;
  const badges = badgesForComponentRecords(actions);

  return (
    <div className="card">
      <div className="lbl">Selected component</div>
      <h2 style={{ margin: "4px 0 12px", fontSize: 20, fontWeight: 600 }}>
        {c.title}{" "}
        <span
          className="mono"
          style={{ fontSize: 13, color: "#FFB3AB", fontWeight: 400 }}
        >
          {c.riskNote}
        </span>
      </h2>
      <div className="detail">
        <div>
          <div className="sub" style={{ marginBottom: 6 }}>
            {c.chart.caption}
          </div>
          <RippleChart chart={c.chart} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="sub">{c.cause}</div>
          {badges.length > 0 ? (
            <div className="badges">
              {badges.map((label) => (
                <span key={label} className="badge">
                  {label}
                </span>
              ))}
            </div>
          ) : (
            <div className="sub">
              Select <strong>ACT</strong> on a queue item to choose a remediation
              action.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
