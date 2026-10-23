# Machining-cell inspection console

The primary demo user is a manufacturing technician reviewing a machining-cell observation. The original Blender asset has three selectable assemblies: drive/spindle (RPM and torque), process chamber (air and process temperatures), and tool head (tool wear). These groups organize evidence; they do not identify failed components. Product type is an input category. The AI4I data is synthetic and is not actual telemetry from this illustrative machine.

Run the existing Streamlit app, open AI4I Baseline, select a policy and record, then Assess record. Orbit, zoom, select an assembly, or use Explode view. The 2D schematic remains available for devices without WebGL. All geometry and viewer code are local; no CDN is required. Offline inference and simulated review orders remain the defaults.

## Original asset and reproducible build

`tools/build_machine.py` creates the geometry from primitives using Blender 5.0. `assets/machining-cell.blend` is the editable source; `assets/machining-cell.glb` is the runtime export. No organizer assets were reused.

```sh
blender --background --python tools/build_machine.py
cd frontend/viewer
npm ci
npm run build
```

The committed viewer bundle means Node and Blender are not needed to run the Python application. Three.js is MIT-licensed; see the accompanying third-party license. The renderer caps pixel ratio and pauses rendering when hidden. Keyboard-accessible component buttons, Escape/reset, reduced motion, and a 2D alternative provide independent navigation paths.

## Demo sequence

1. Open AI4I Baseline and choose an operating policy.
2. Assess a held-out observation. Inspect the global decision and classifier score.
3. Click Tool head or Drive/spindle to inspect the actual input values.
4. Explain that the model flags the observation, not a specific defective component.
5. Inspect evidence and any simulated technician-review order; preview the simulated notification.
   Use the review form to save an acknowledgment, pending inspection, or completed review with a simulation note. This persists locally and detects concurrent edits. It does not mark the machine safe or perform maintenance.
6. Change policies to discuss the measured tradeoff. Reassess explicitly.
7. Use the separate fictional replay to demonstrate degradation, duplicate prevention, missing sensors, and provider outage.

This remains a decision-support demo, not a production maintenance or dispatch system. No real work orders, emails, purchases, or equipment commands are sent by these screens.
