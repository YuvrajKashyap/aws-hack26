import { location } from "../data";

/** Breadcrumb + page title, shared by the dashboard and action screens. */
export function PageHeader() {
  return (
    <div>
      <div className="mono" style={{ fontSize: 12, color: "#3DD6C3" }}>
        {location.breadcrumb}
      </div>
      <h1 style={{ margin: "4px 0 0", fontSize: 26, fontWeight: 600 }}>
        {location.title}
      </h1>
    </div>
  );
}
