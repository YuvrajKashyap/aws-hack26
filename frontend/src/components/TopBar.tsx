import { filters, location } from "../data";

export function TopBar() {
  return (
    <div className="top">
      <div>
        <div className="mono" style={{ fontSize: 12, color: "#3DD6C3" }}>
          {location.breadcrumb}
        </div>
        <h1 style={{ margin: "4px 0 0", fontSize: 26, fontWeight: 600 }}>
          {location.title}
        </h1>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {filters.map((f) => (
          <button key={f} className="pill">
            {f}
          </button>
        ))}
      </div>
    </div>
  );
}
