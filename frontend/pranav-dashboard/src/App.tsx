import { Routes, Route } from "react-router-dom";
import { Dashboard } from "./components/Dashboard";
import { ActionScreen } from "./components/ActionScreen";
import { useActions } from "./ActionContext";

/** Visually-hidden styling for the shared screen-reader live region. */
const srOnly: React.CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
};

export default function App() {
  const { announcement } = useActions();

  return (
    <>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/act/:componentId" element={<ActionScreen />} />
      </Routes>
      <div aria-live="polite" style={srOnly}>
        {announcement}
      </div>
    </>
  );
}
