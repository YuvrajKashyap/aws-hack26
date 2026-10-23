# Pranav dashboard integration

Operations now embeds Pranav's actual React UI from PR6 commit `390146077780bf1edfda70849a7b468a67bdcf2a`, retaining its layout, filters, rack map, component detail, charts, and remediation screens. Source: `frontend/pranav-dashboard/src`.

MemoryRouter replaces BrowserRouter for navigation inside the Streamlit iframe. The workshop-specific Vite host configuration is unnecessary. The build bundles the application into `assets/pranav-dashboard.html`; the original Google Fonts links remain with system-font fallbacks.

This is the simulated data-center prototype, not live machining-cell telemetry. Its actions are browser-session state, not SQLite review records. The page labels that distinction. The prior recorded-ledger and hypothetical-cost dashboard remains in the expander below it.

Rebuild with `npm ci` in `frontend/viewer` and `frontend/pranav-dashboard`, then `npm run build` in `frontend/pranav-dashboard`. Node is not required to serve the committed HTML. Tests were skipped at the user's explicit request.
