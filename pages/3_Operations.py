"""Pranav dashboard UI with separate ledger and scenario details."""
from pathlib import Path
import runpy
import json
import os
import sqlite3
import streamlit as st
import streamlit.components.v1 as components
st.set_page_config(page_title='Operations dashboard',layout='wide')
st.markdown('<style>.block-container{max-width:1600px;padding-top:1rem}</style>',unsafe_allow_html=True)
st.info('PRANAV’S DASHBOARD DESIGN / SHARED ASSESSMENT AND LOCAL LEDGER / Synthetic data, simulated actions. No component fault or replacement is established.')
root=Path(__file__).resolve().parents[1]
result=st.session_state.get('ai4i_result')
rows=[]
path=Path(os.getenv('DEMO_LEDGER_PATH','data/ai4i-orders.sqlite'))
if path.exists():
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as con:
            con.row_factory=sqlite3.Row
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            reviews={r['order_id']:dict(r) for r in con.execute('SELECT * FROM reviews')} if 'reviews' in tables else {}
            if 'orders' in tables:
                for record in con.execute('SELECT payload FROM orders'):
                    order=json.loads(record[0]);review=reviews.get(order['order_id'],{})
                    rows.append(dict(id=order['order_id'],asset=order['proposal']['asset_id'],status=order['status'],reason=order['reason'],review=review.get('state','Not acknowledged'),note=review.get('note','')))
    except (sqlite3.Error,ValueError):
        st.error('Ledger unavailable; no synchronized dashboard shown.')
        st.stop()
payload=json.dumps({'result':result.model_dump(mode='json') if result else None,'orders':rows}).replace('<','\\u003c')
html=(root/'assets/pranav-dashboard.html').read_text(encoding='utf-8')
html=html.replace('<script>', '<script>window.__FIELDWORK__='+payload+';</script><script>',1)
components.html(html,height=1150,scrolling=True)
st.button('Refresh synchronized activity')
with st.expander('Recorded ledger activity and editable business-impact scenarios'):
    runpy.run_path(str(root/'src/business_page.py'))
