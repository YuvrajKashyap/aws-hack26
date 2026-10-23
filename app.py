"""Single-screen simulator using the same orchestrator as CLI and tests."""
import os
import pandas as pd
import streamlit as st
from src.orchestrator import SCENARIOS, configured_provider, run_scenario
from src.explanation import SimulatedOutage

st.set_page_config(page_title='Manufacturing / Track 2', page_icon='⚙', layout='wide')
from src.ui import console_style, stages
console_style()
st.title('From sensor evidence to maintenance')
st.markdown('<p class="intro">Follow a fictional press from a healthy window to a maintenance concern. Every recommendation carries its evidence; every action stays simulated.</p>', unsafe_allow_html=True)
st.markdown('[Open the 3D machine maintenance console →](AI4I_Baseline)')
stages()
mode = os.getenv('DEMO_MODE', 'offline')
st.info(f'{mode.upper()} MODE · FICTIONAL MACHINE · SIMULATED ACTIONS ONLY')
st.caption('SIM-PRESS-01 · Original simulation · Diagnosis and planning use deterministic rules. '
           'No accuracy claim or remaining useful life estimate.')


@st.cache_resource
def provider_for_mode(selected_mode):
    return configured_provider(selected_mode)


scenario = st.selectbox('Replay scenario', SCENARIOS)
outage = st.checkbox('Simulate explanation-provider outage (no network call)')
run = st.button('Replay scenario', type='primary')
if run:
    try:
        with st.spinner('Validating evidence and simulating maintenance…'):
            result = run_scenario(scenario, os.getenv('DEMO_LEDGER_PATH', 'data/demo.sqlite'), mode=mode,
                explainer=SimulatedOutage() if outage else provider_for_mode(mode))
            st.session_state['result'] = result
    except (ValueError, OSError):
        st.error('Replay rejected: invalid input or configuration. Check the selected fixture and DEMO_MODE.')
        st.session_state.pop('result', None)

result = st.session_state.get('result')
if result is None:
    st.write('Start with normal, then replay degrading. Repeat it to verify duplicate prevention; finish with missing-sensor.')
    st.stop()

st.subheader(f'Completed replay: {result.window.scenario_id}')
if scenario != result.window.scenario_id:
    st.caption('The selection changed. Press Replay scenario to update these results.')
assessment = result.assessment
col1, col2, col3 = st.columns(3)
col1.metric('Risk band', assessment.risk_band.upper())
col2.metric('Illustrative rule score / 100', 'Abstained' if assessment.score is None else str(assessment.score))
col3.metric('Remaining useful life', 'Unsupported')
st.caption(f'Replay clock: {result.window.start.isoformat()} → {result.window.end.isoformat()} · '
           'Freshness is relative to this simulated window, not the current date.')
if result.window.quality_flags:
    st.warning('Data quality: ' + ', '.join(result.window.quality_flags))

st.subheader('Sensor timeline')
rows = []
for name, channel in result.window.channels.items():
    for sample in channel.samples:
        rows.append({'timestamp': sample.timestamp, 'channel': name, 'value': sample.value, 'unit': channel.unit})
if rows:
    # Faceted panels share a time domain and keep distinct physical units on separate axes.
    import altair as alt
    frame = pd.DataFrame(rows)
    frame['sensor'] = frame['channel'] + ' (' + frame['unit'] + ')'
    chart = alt.Chart(frame).mark_line(point=True).encode(
        x=alt.X('timestamp:T', title='Simulated time (UTC)', scale=alt.Scale(type='utc'),
                axis=alt.Axis(format='%H:%M')),
        y=alt.Y('value:Q', title='Reading'),
        tooltip=['timestamp:T', 'channel:N', 'value:Q', 'unit:N'],
    ).properties(height=120).facet(row=alt.Row('sensor:N', title=None)).resolve_scale(y='independent')
    st.altair_chart(chart, use_container_width=True)
with st.expander('Accessible readings table and original values'):
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    st.json(result.window.model_dump(mode='json'))

st.subheader('Evidence and explanation')
st.caption(f'Explanation mode: {result.explanation.mode} · Rule reference: SIM-RISK-1')
if result.explanation.fallback_reason:
    st.warning(result.explanation.fallback_reason)
for statement in result.explanation.statements:
    st.write(statement)
for limitation in result.explanation.limitations:
    st.caption(limitation)

st.subheader('Simulated maintenance')
for error in result.errors:
    st.error(error)
if result.order:
    message = f'{result.order.status} · {result.order.order_id} · {result.order.reason}'
    (st.success if result.order.status == 'reserved' else st.warning)(message)
    with st.expander('Inspect simulated work order', expanded=True):
        st.json(result.order.model_dump(mode='json'))
else:
    st.write(result.proposal.reason)
with st.expander('Orchestration trace and full artifact'):
    st.dataframe([step.model_dump() for step in result.trace], hide_index=True, width='stretch')
    st.json(result.model_dump(mode='json'))
