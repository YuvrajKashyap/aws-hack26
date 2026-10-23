import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageHeader } from "./PageHeader";
import { RippleChart } from "./RippleChart";
import { ActionPanel } from "./ActionPanel";
import { detailForRack } from "../data";
import { useActions } from "../ActionContext";
import type { ActionKind } from "../types";
import type { ActionPayload } from "../actions";

export function ActionScreen() {
  const { componentId = "" } = useParams();
  const navigate = useNavigate();
  const { perform, actionsFor } = useActions();

  const detail = useMemo(() => detailForRack(componentId), [componentId]);
  const actions = actionsFor(componentId);

  function handlePerform(kind: ActionKind, payload?: ActionPayload) {
    // Stay on the screen so multiple actions can be taken in one visit.
    perform(componentId, detail.title, kind, payload);
  }

  return (
    <div className="shell">
      <div className="wrap">
        <PageHeader />

        <nav aria-label="Breadcrumb">
          <button
            type="button"
            className="btn2 back-btn"
            onClick={() => navigate("/")}
          >
            ← Back to dashboard
          </button>
        </nav>

        <div className="card">
          <div className="lbl">Act on component</div>
          <h1 style={{ margin: "4px 0 12px", fontSize: 24, fontWeight: 600 }}>
            {detail.title}{" "}
            <span
              className="mono"
              style={{ fontSize: 14, color: "#FFB3AB", fontWeight: 400 }}
            >
              {detail.riskNote}
            </span>
          </h1>

          <div className="detail">
            <div>
              <div className="sub" style={{ marginBottom: 6 }}>
                {detail.chart.caption}
              </div>
              <RippleChart chart={detail.chart} />
              <div className="sub" style={{ marginTop: 10 }}>
                {detail.cause}
              </div>
            </div>

            <ActionPanel
              componentId={componentId}
              componentTitle={detail.title}
              actions={actions}
              onPerform={handlePerform}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
