"""Technician, model research, and operations workspaces."""
import streamlit as st
st.set_page_config(page_title='Fieldwork maintenance', layout='wide')
st.navigation([
    st.Page('pages/1_AI4I_Baseline.py', title='Technician console', default=True),
    st.Page('pages/2_Model_Lab.py', title='Model lab', url_path='model-lab'),
    st.Page('pages/3_Operations.py', title='Operations dashboard', url_path='operations'),
]).run()
