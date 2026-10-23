import { racks } from "../data";
import type { RackStatus } from "../types";

const statusClass: Record<RackStatus, string> = {
  healthy: "o",
  watch: "w",
  critical: "c",
};

interface Props {
  selectedId: string;
  onSelect: (rackId: string) => void;
}

export function RackMap({ selectedId, onSelect }: Props) {
  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Rack map</h2>
        <span className="sub">Rows A to E, racks 1 to 8</span>
      </div>
      <div className="racks">
        {racks.map((rack) => {
          const isSelected = rack.id === selectedId;
          return (
            <button
              key={rack.id}
              type="button"
              className={`k ${statusClass[rack.status]}${isSelected ? " sel" : ""}`}
              aria-pressed={isSelected}
              aria-label={`Rack ${rack.id}, ${rack.status}`}
              onClick={() => onSelect(rack.id)}
            >
              {rack.id}
            </button>
          );
        })}
      </div>
      <div className="legend">
        <span>
          <span className="dot" style={{ background: "#3DD6C3" }} />
          Healthy
        </span>
        <span>
          <span className="dot" style={{ background: "#F5A524" }} />
          Watch: drifting from baseline
        </span>
        <span>
          <span className="dot" style={{ background: "#FF6B5E" }} />
          Critical: replace soon
        </span>
      </div>
    </div>
  );
}
