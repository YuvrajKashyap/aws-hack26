import json
import struct
from src.scene import ASSETS, render_3d_explorer


def test_original_asset_has_all_evidence_zones():
    raw = (ASSETS / 'machining-cell.glb').read_bytes()
    assert raw[:4] == b'glTF'
    size = struct.unpack_from('<I', raw, 12)[0]
    document = json.loads(raw[20:20+size])
    names = {n.get('name') for n in document['nodes']}
    assert {'drive', 'process_chamber', 'tool_head'} <= names


def test_viewer_escapes_payload_and_has_accessible_fallback():
    html = render_3d_explorer([{'id': 'drive', 'observations': ['</script><img src=x>']}], {})
    assert '</script><img src=x>' not in html
    assert 'prefers-reduced-motion' in html
    assert 'focus-visible' in html
    assert 'GLOBAL ASSESSMENT' in html
    assert 'data-zone="tool_head"' in html
