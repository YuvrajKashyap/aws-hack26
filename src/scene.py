"""Offline, original Blender asset with a locally bundled Three.js viewer."""
import base64
import json
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'assets'

@lru_cache(maxsize=1)
def _assets():
    return (base64.b64encode((ASSETS/'machining-cell.glb').read_bytes()).decode(),
            (ASSETS/'viewer.js').read_text(encoding='utf-8'))

def render_3d_explorer(zones, assessment):
    asset, script = _assets()
    payload = json.dumps({'zones': zones, 'assessment': assessment, 'asset': asset}).replace('<','\\u003c')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{box-sizing:border-box}body{margin:0;background:#111b23;color:#eff1eb;font:14px 'Segoe UI',sans-serif}
.shell{display:grid;grid-template-columns:minmax(0,1fr) 245px;min-height:720px;border:1px solid #33424d;border-radius:12px;overflow:hidden}
#viewport{position:relative;height:720px;min-width:0;overflow:hidden}canvas{width:100%;height:100%;touch-action:none;opacity:0;transition:opacity .8s cubic-bezier(.16,1,.3,1)}.ready canvas{opacity:1}
.eyebrow{position:absolute;left:24px;top:24px;font:11px Consolas,monospace;letter-spacing:1.7px;color:#aebfc8;pointer-events:none}.eyebrow strong{display:block;color:#fff;font:24px 'Segoe UI',sans-serif;letter-spacing:-.7px;margin-top:8px}
.bottom{position:absolute;bottom:22px;left:24px;right:24px;display:flex;justify-content:space-between;gap:10px;color:#a9bac4;font-size:11px;pointer-events:none}
.controls{position:absolute;top:22px;right:22px;display:flex;gap:6px}button{font:12px 'Segoe UI',sans-serif;color:#e9eee9;background:#1e2c35;border:1px solid #44545e;padding:10px 13px;border-radius:5px;cursor:pointer;transition:transform .25s cubic-bezier(.16,1,.3,1),background .25s,border-color .25s}button:hover{transform:translateY(-2px);background:#35454e;border-color:#e2ad80}button:focus-visible{outline:2px solid #e2ad80;outline-offset:3px}button[aria-pressed=true]{background:#744124;border-color:#e2ad80}
aside{padding:24px 20px;background:#17232c;border-left:1px solid #33424d;display:flex;flex-direction:column}.label{font:10px Consolas,monospace;letter-spacing:1.4px;color:#b9c6ce}.zone-list{display:grid;gap:8px;margin:18px 0 30px}.zone-list button{text-align:left;padding:14px}.zone-list button span{float:right;color:#e2ad80}h2{font-size:21px;letter-spacing:-.6px;font-weight:500;margin:12px 0 16px}p,#detail-note{font-size:12px;line-height:1.7;color:#b7c5cc}.reading{padding:12px 0;border-bottom:1px solid #34424a;font-size:13px;line-height:1.5}.foot{margin-top:auto;padding-top:25px;font:10px Consolas,monospace;color:#9bafb9;line-height:1.6}#detail-note{margin-top:14px}.unavailable{background:repeating-linear-gradient(45deg,#14212a,#14212a 20px,#192832 20px,#192832 40px)}
@media(max-width:700px){.shell{grid-template-columns:1fr}#viewport{height:360px}.eyebrow{top:18px;left:16px}.eyebrow strong{font-size:20px}.controls{top:auto;bottom:55px;right:12px}.bottom{left:16px;right:16px;font-size:10px}aside{border-left:0;border-top:1px solid #33424d;padding:18px}.zone-list{grid-template-columns:repeat(3,1fr);gap:5px;margin:12px 0}.zone-list button{padding:10px 7px;font-size:11px}.zone-list span{display:none}.foot{padding-top:12px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style></head><body><div class="shell"><div id="viewport"><div class="eyebrow">ILLUSTRATIVE ASSET / M-01<strong>Machining cell</strong></div><div class="controls"><button id="explode" aria-pressed="false">Explode view</button><button id="reset-view">Reset view</button></div><div class="bottom"><span id="hover-label">Drag to orbit · scroll to zoom</span><span id="scene-status" role="status">LOADING GEOMETRY</span></div></div><aside><div class="label">EXPLORE THE ASSEMBLY</div><div class="zone-list"><button data-zone="drive" aria-pressed="false">Drive / spindle <span>↗</span></button><button data-zone="process_chamber" aria-pressed="false">Process chamber <span>↗</span></button><button data-zone="tool_head" aria-pressed="false">Tool head <span>↗</span></button></div><div class="label">RECORDED EVIDENCE</div><h2 id="detail-title">Machine overview</h2><div id="details"></div><div id="detail-note"></div><div class="foot">GLOBAL ASSESSMENT<br><div id="assessment-detail" style="white-space:pre-line;color:#e2ad80;margin:9px 0;font-size:12px"></div>Geometry is illustrative. Sensor readings do not identify a failed component.</div></aside></div><script id="scene-data" type="application/json">'''+payload+'''</script><script>'''+script.replace('</script','<\\/script')+'''</script></body></html>'''
