"""Pranav dashboard UI with separate ledger and scenario details."""
from pathlib import Path
import runpy
import streamlit as st
import streamlit.components.v1 as components
st.set_page_config(page_title='Operations dashboard',layout='wide')
st.markdown('<style>.block-container{max-width:1600px;padding-top:1rem}</style>',unsafe_allow_html=True)
st.info('PRANAV DASHBOARD / SIMULATED SAMPLE DATA / Actions change browser-session state only. No real dispatch, ordering, or scheduling. Refresh resets prototype actions.')
root=Path(__file__).resolve().parents[1]
components.html((root/'assets/pranav-dashboard.html').read_text(encoding='utf-8'),height=1150,scrolling=True)
with st.expander('Recorded ledger activity and editable business-impact scenarios'):
    runpy.run_path(str(root/'src/business_page.py'))
