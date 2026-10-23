import { kpis as defaultKpis } from "../data";
import type { Kpi } from "../types";

interface Props {
  /** KPI cards to render; defaults to the static sample set. */
  kpis?: Kpi[];
}

export function KpiCards({ kpis = defaultKpis }: Props) {
  return (
    <div className="kpis">
      {kpis.map((kpi) => (
        <div key={kpi.label} className="card">
          <div className="lbl">{kpi.label}</div>
          <div className="big" style={kpi.valueColor ? { color: kpi.valueColor } : undefined}>
            {kpi.value}
          </div>
          <div className="sub">{kpi.sub}</div>
        </div>
      ))}
    </div>
  );
}
