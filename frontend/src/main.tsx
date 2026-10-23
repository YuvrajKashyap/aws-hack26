import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ActionProvider } from "./ActionContext";
import "./index.css";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element #root not found");

// The app may be served under a sub-path (e.g. "/ports/5173/") behind the
// code-editor proxy. Vite exposes that as BASE_URL; strip the trailing slash
// so React Router's basename matches ("" when served at root).
const basename = import.meta.env.BASE_URL.replace(/\/$/, "");

createRoot(rootEl).render(
  <StrictMode>
    <BrowserRouter
      basename={basename}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <ActionProvider>
        <App />
      </ActionProvider>
    </BrowserRouter>
  </StrictMode>,
);
