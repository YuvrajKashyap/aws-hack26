"""Self-contained interactive 2D machine schematic.

Renders a single HTML/SVG document with no remote assets and no frontend build
step. The schematic is one connected, original machine silhouette (bed and rails,
drive shaft/spindle, process chamber enclosure, tool head). Three clickable zones
map to the six AI4I inputs and the panel shows the actual observations and the
honest global assessment for the currently selected record. It never attributes
the machine-level classifier to a component or invents a component fault state.
"""
import html
import json


def _verdict_text(assessment: dict) -> tuple[str, str]:
    if assessment.get('decision') == 'Not assessed':
        return 'NOT ASSESSED', 'cyan'
    predicted = assessment.get('predicted_failure')
    if predicted is None:
        return 'ABSTAINED', 'amber'
    if predicted:
        return 'REVIEW FLAGGED', 'amber'
    return 'BELOW THRESHOLD', 'cyan'


def render_machine_explorer(zones: list[dict], assessment: dict, *, height: int = 560) -> str:
    """Return a standalone HTML string for an iframe-embedded component.

    `zones` is the output of src.policy.explorer_zones; `assessment` carries the
    actual record_id, model_id, score, threshold and predicted_failure.
    """
    verdict, accent = _verdict_text(assessment)
    data = {'zones': zones, 'assessment': {
        'record_id': str(assessment.get('record_id', '')),
        'model_id': str(assessment.get('model_id', '')),
        'policy': str(assessment.get('policy', '')),
        'score': assessment.get('score'),
        'threshold': assessment.get('threshold'),
        'verdict': verdict, 'accent': accent,
        'explanation_mode': str(assessment.get('explanation_mode', '')),
    }}
    payload = html.escape(json.dumps(data), quote=True)
    # All styling/behaviour is inline; no external fonts, scripts or images.
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg:#0a0e13; --panel:#121a25; --edge:#2a3a4d; --ink:#f2f6fb; --muted:#b4c4d6;
    --cyan:#4fe3e9; --amber:#ffc24d; --steel:#43607f; --focus:#9fe0ff;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, Helvetica, Arial, sans-serif; }}
  .wrap {{ display:grid; grid-template-columns: 1.5fr 1fr; gap:16px; padding:16px; }}
  @media (max-width:760px) {{ .wrap {{ grid-template-columns:1fr; }} }}
  .stage {{ background:
      radial-gradient(1200px 500px at 30% -10%, #16202e 0%, var(--panel) 55%);
    border:1px solid var(--edge); border-radius:14px; position:relative; overflow:hidden; min-height:430px; }}
  .toolbar {{ position:absolute; top:12px; right:12px; display:flex; gap:8px; z-index:5; }}
  button.ctl {{ background:#16222f; color:var(--ink); border:1px solid var(--edge);
    border-radius:9px; padding:8px 13px; cursor:pointer; font:inherit; font-size:14px; font-weight:600; }}
  button.ctl:hover {{ border-color:var(--cyan); color:var(--cyan); }}
  button.ctl:focus-visible {{ outline:3px solid var(--focus); outline-offset:2px; }}
  svg {{ width:100%; height:100%; display:block; }}
  #camera {{ transition: transform .6s cubic-bezier(.22,.61,.36,1); transform-origin:0 0; }}
  .frame {{ fill:#0c141d; stroke:var(--steel); stroke-width:2.5; }}
  .rail {{ stroke:var(--steel); stroke-width:6; stroke-linecap:round; opacity:.85; }}
  .part {{ fill:#17273a; stroke:var(--steel); stroke-width:2; }}
  .conduit {{ stroke:var(--steel); stroke-width:4; fill:none; opacity:.7; }}
  .zone {{ cursor:pointer; }}
  .zone .hit {{ fill:transparent; stroke:transparent; stroke-width:3; transition:stroke .2s ease; }}
  .zone .glow {{ transition: opacity .25s ease, stroke .25s ease; }}
  .zone:hover .hit {{ stroke:var(--cyan); }}
  .zone:hover .glow {{ opacity:1; }}
  .zone[aria-pressed="true"] .hit {{ stroke:var(--amber); fill:rgba(255,194,77,.07); }}
  .zone[aria-pressed="true"] .glow {{ opacity:1; stroke:var(--amber); }}
  .zone:focus-visible {{ outline:none; }}
  .zone:focus-visible .hit {{ stroke:var(--focus); stroke-width:4; }}
  .zlabel {{ fill:var(--ink); font-size:16px; font-weight:600; pointer-events:none;
    paint-order:stroke; stroke:#0a0e13; stroke-width:4px; }}
  .zsub {{ fill:var(--muted); font-size:12.5px; pointer-events:none;
    paint-order:stroke; stroke:#0a0e13; stroke-width:3px; }}
  .tag {{ fill:var(--muted); font-size:12px; letter-spacing:.09em; }}
  .panel {{ background:var(--panel); border:1px solid var(--edge); border-radius:14px; padding:18px; }}
  .badge {{ display:inline-block; font-size:12px; letter-spacing:.09em; color:var(--muted);
    border:1px solid var(--edge); border-radius:999px; padding:4px 11px; margin-bottom:12px; }}
  h2 {{ font-size:18px; margin:6px 0 4px; }}
  .verdict {{ font-size:26px; font-weight:800; margin:4px 0 10px; letter-spacing:.01em; }}
  .verdict.cyan {{ color:var(--cyan); }} .verdict.amber {{ color:var(--amber); }}
  .kv {{ color:var(--muted); font-size:13.5px; line-height:1.6; margin:2px 0; }}
  .kv b {{ color:var(--ink); font-weight:600; }}
  .mono {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size:11.5px; color:var(--muted);
    word-break:break-all; }}
  ul.obs {{ list-style:none; padding:0; margin:12px 0 0; }}
  ul.obs li {{ padding:10px 13px; border:1px solid var(--edge); border-radius:10px; margin:8px 0;
    background:#0e1824; font-size:15px; color:var(--ink); }}
  .hint {{ color:var(--muted); font-size:12.5px; margin-top:14px; line-height:1.6; }}
  .illus {{ color:var(--amber); font-weight:600; }}
  @media (prefers-reduced-motion: reduce) {{
    #camera {{ transition:none; }}
    .zone .hit, .zone .glow {{ transition:none; }}
  }}
</style></head>
<body>
<div class="wrap">
  <div class="stage">
    <div class="toolbar">
      <button class="ctl" id="reset" aria-label="Reset view">Reset view</button>
    </div>
    <svg viewBox="0 0 620 440" role="group" aria-label="Illustrative connected machine schematic">
      <g id="camera">
        <text x="26" y="26" class="tag" aria-hidden="true">ILLUSTRATIVE SCHEMATIC — NOT A REAL MACHINE</text>

        <!-- Connected silhouette: bed, rails, conduits linking the stations. -->
        <rect class="frame" x="34" y="300" width="552" height="54" rx="10"/>
        <line class="rail" x1="56" y1="300" x2="564" y2="300"/>
        <line class="rail" x1="56" y1="330" x2="564" y2="330"/>
        <path class="conduit" d="M190 250 H300"/>
        <path class="conduit" d="M410 190 C 470 220, 470 240, 492 268"/>

        <!-- Drive / spindle station -->
        <g class="zone" id="z-drive" tabindex="0" role="button" aria-pressed="false"
           aria-label="Drive and spindle zone" data-zoom="2.0" data-cx="135" data-cy="225">
          <rect class="part" x="70" y="196" width="130" height="86" rx="10"/>
          <circle class="glow" cx="135" cy="239" r="40" fill="none" stroke="var(--cyan)" stroke-width="3" opacity="0.55"/>
          <circle class="part" cx="135" cy="239" r="22"/>
          <circle cx="135" cy="239" r="7" fill="var(--cyan)"/>
          <rect class="part" x="196" y="231" width="70" height="16" rx="6"/><!-- shaft to chamber -->
          <text x="78" y="186" class="zlabel">Drive / spindle</text>
          <text x="78" y="300" class="zsub">rotation · torque</text>
          <rect class="hit" x="66" y="176" width="140" height="130" rx="12"/>
        </g>

        <!-- Process chamber enclosure -->
        <g class="zone" id="z-process_chamber" tabindex="0" role="button" aria-pressed="false"
           aria-label="Process chamber zone" data-zoom="2.0" data-cx="355" data-cy="170">
          <rect class="part" x="276" y="96" width="162" height="150" rx="12"/>
          <rect x="292" y="112" width="130" height="92" rx="8" fill="#0e1824" stroke="var(--edge)"/>
          <path class="glow" d="M300 170 q44 -50 88 0 q44 50 88 0" fill="none"
                stroke="var(--amber)" stroke-width="3" opacity="0.55"/>
          <text x="288" y="86" class="zlabel">Process chamber</text>
          <text x="288" y="226" class="zsub">air · process temperature</text>
          <rect class="hit" x="272" y="76" width="170" height="178" rx="12"/>
        </g>

        <!-- Tool head -->
        <g class="zone" id="z-tool_head" tabindex="0" role="button" aria-pressed="false"
           aria-label="Tool head zone" data-zoom="2.2" data-cx="500" data-cy="250">
          <rect class="part" x="452" y="150" width="104" height="70" rx="9"/>
          <path class="glow" d="M504 220 l20 70 l-40 0 z" fill="rgba(79,227,233,.35)"
                stroke="var(--cyan)" stroke-width="3" opacity="0.7"/>
          <text x="458" y="142" class="zlabel">Tool head</text>
          <text x="458" y="310" class="zsub">tool wear</text>
          <rect class="hit" x="448" y="128" width="112" height="180" rx="12"/>
        </g>
      </g>
    </svg>
  </div>
  <div class="panel" aria-live="polite">
    <span class="badge" id="badge">GLOBAL ASSESSMENT</span>
    <div class="verdict" id="verdict">—</div>
    <div class="kv" id="meta"></div>
    <h2 id="ztitle">Select a zone</h2>
    <ul class="obs" id="obs"></ul>
    <div class="hint">
      <span class="illus">Illustrative schematic.</span> Zones show observed readings from the
      selected dataset record as evidence only. The classifier predicts a machine-level label; it
      does not diagnose a specific component or assert a part has failed. Dataset rows are not a real
      machine timeline.<br>
      Keyboard: Tab to a zone, Enter or Space to open it, Esc or Reset to zoom out.
    </div>
  </div>
</div>
<script>
  const DATA = JSON.parse(decodeHTML("{payload}"));
  function decodeHTML(s) {{ const t = document.createElement('textarea'); t.innerHTML = s; return t.value; }}
  const camera = document.getElementById('camera');
  const zonesById = Object.fromEntries(DATA.zones.map(z => [z.id, z]));
  const a = DATA.assessment;

  function esc(s) {{ return String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c])); }}
  function renderGlobal() {{
    const v = document.getElementById('verdict');
    v.textContent = a.verdict; v.className = 'verdict ' + (a.accent || 'cyan');
    const score = (a.score === null || a.score === undefined) ? (a.verdict === 'NOT ASSESSED' ? 'not assessed' : 'abstained') : Number(a.score).toFixed(4);
    const thr = (a.threshold === null || a.threshold === undefined) ? '—' : Number(a.threshold).toFixed(2);
    document.getElementById('meta').innerHTML =
      '<b>Record</b> ' + esc(a.record_id) + ' · <b>policy</b> ' + esc(a.policy || '—') + '<br>' +
      '<b>score</b> ' + score + ' · <b>threshold</b> ' + thr + ' · <b>explanation</b> ' + esc(a.explanation_mode || '—') +
      '<br><span class="mono">' + esc(a.model_id) + '</span>';
  }}

  function selectZone(id) {{
    document.querySelectorAll('.zone').forEach(g => g.setAttribute('aria-pressed', String(g.id === 'z-' + id)));
    const z = zonesById[id];
    document.getElementById('ztitle').textContent = z ? z.label : 'Select a zone';
    const ul = document.getElementById('obs'); ul.innerHTML = '';
    (z ? z.observations : []).forEach(o => {{ const li = document.createElement('li'); li.textContent = o; ul.appendChild(li); }});
    const g = document.getElementById('z-' + id);
    if (g) {{
      const zoom = parseFloat(g.dataset.zoom), cx = parseFloat(g.dataset.cx), cy = parseFloat(g.dataset.cy);
      camera.style.transform = `translate(${{310 - cx * zoom}}px, ${{220 - cy * zoom}}px) scale(${{zoom}})`;
    }}
  }}
  function resetView() {{
    camera.style.transform = 'translate(0px,0px) scale(1)';
    document.querySelectorAll('.zone').forEach(g => g.setAttribute('aria-pressed', 'false'));
    document.getElementById('ztitle').textContent = 'Select a zone';
    document.getElementById('obs').innerHTML = '';
  }}
  document.querySelectorAll('.zone').forEach(g => {{
    const id = g.id.replace('z-', '');
    g.addEventListener('click', () => selectZone(id));
    g.addEventListener('keydown', e => {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); selectZone(id); }}
      if (e.key === 'Escape') {{ resetView(); }}
    }});
  }});
  document.getElementById('reset').addEventListener('click', resetView);
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') resetView(); }});
  renderGlobal();
</script>
</body></html>"""
