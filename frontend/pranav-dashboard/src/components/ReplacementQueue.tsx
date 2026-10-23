import { componentIdFor } from "../data";
import { badgesForComponent } from "../actions";
import type {
  ComponentActionState,
  ReplacementItem,
  RiskLevel,
} from "../types";

const riskColors: Record<RiskLevel, { background: string; color: string }> = {
  critical: { background: "#6B2420", color: "#FFC2BB" },
  watch: { background: "#5A4310", color: "#FFD27A" },
};

interface Props {
  /** Queue items to render (already filtered by the dashboard). */
  items: ReplacementItem[];
  /** Currently selected component id (rack id, e.g. "C7"). */
  selectedId: string;
  /** Actions taken per component, used to render row status badges. */
  actionState: ComponentActionState;
  /** Called when the ACT button on a row is clicked. */
  onAct: (componentId: string) => void;
}

export function ReplacementQueue({ items, selectedId, actionState, onAct }: Props) {
  return (
    <div className="card">
      <h2 style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 600 }}>
        Replacement queue
      </h2>
      <div className="sub" style={{ marginBottom: 8 }}>
        Ranked by failure risk
      </div>
      {items.length === 0 ? (
        <div className="sub" style={{ padding: "12px 0" }}>
          No components match the current filters.
        </div>
      ) : (
        items.map((item, i) => {
        const id = componentIdFor(item.component);
        const badges = badgesForComponent(actionState, id);
        const isSelected = id === selectedId;
        return (
          <div
            key={item.component}
            className={`item queue-row${isSelected ? " queue-row--selected" : ""}`}
            style={i === 0 ? { borderTop: 0 } : undefined}
          >
            <div className="risk" style={riskColors[item.level]}>
              {item.riskPct}%
            </div>
            <div className="queue-row__body">
              <div style={{ fontWeight: 500 }}>{item.component}</div>
              <div className="tag">{item.evidence}</div>
              {badges.length > 0 && (
                <div className="badges">
                  {badges.map((label) => (
                    <span key={label} className="badge">
                      {label}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <button
              type="button"
              className="btn2 act-btn"
              aria-label={`Act on ${item.component}`}
              onClick={() => onAct(id)}
            >
              ACT
            </button>
          </div>
        );
        })
      )}
    </div>
  );
}
