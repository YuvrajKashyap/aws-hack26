import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TopBar } from "./TopBar";
import { KpiCards } from "./KpiCards";
import { RackMap } from "./RackMap";
import { ReplacementQueue } from "./ReplacementQueue";
import { ComponentDetail } from "./ComponentDetail";
import { defaultSelectedRackId, detailForRack } from "../data";
import { useActions } from "../ActionContext";

export function Dashboard() {
  const [selectedId, setSelectedId] = useState(defaultSelectedRackId);
  const { actionState, kpis, actionsFor } = useActions();
  const navigate = useNavigate();

  const detail = useMemo(() => detailForRack(selectedId), [selectedId]);

  // ACT on a row selects the component and routes to its action screen.
  function handleAct(componentId: string) {
    navigate(`/act/${encodeURIComponent(componentId)}`);
  }

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
        <ComponentDetail
          component={detail}
          componentId={selectedId}
          actions={actionsFor(selectedId)}
        />
      </div>
    </div>
  );
}
