"""Read-only operational activity and explicitly hypothetical business scenarios."""
import json
import os
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
from src.ui import console_style

st.subheader('Recorded activity and business scenarios')
st.caption('The business view: review workload, proposed decisions, and the economics of a maintenance intervention.')
st.info('RECORDED SIMULATED ACTIVITY + EDITABLE BUSINESS SCENARIOS · NO MEASURED SAVINGS CLAIM')

path = Path(os.getenv('DEMO_LEDGER_PATH', 'data/ai4i-orders.sqlite'))
orders, reviews, events = [], [], []
if path.exists():
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as con:
            con.row_factory = sqlite3.Row
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'orders' in tables:
                orders = [json.loads(r[0]) for r in con.execute('SELECT payload FROM orders')]
            if 'reviews' in tables:
                reviews = [dict(r) for r in con.execute('SELECT * FROM reviews ORDER BY updated_at DESC')]
            if 'review_events' in tables:
                events = [dict(r) for r in con.execute('SELECT * FROM review_events ORDER BY updated_at DESC LIMIT 100')]
    except (sqlite3.Error, ValueError):
        st.error('Local activity could not be read. These counters are unavailable, not confirmed zero.')
        st.stop()

by_id = {r['order_id']:r for r in reviews}
completed = sum(by_id.get(o['order_id'],{}).get('state') == 'Review completed' for o in orders)
pending = sum(by_id.get(o['order_id'],{}).get('state') == 'Inspection pending' for o in orders)
c1,c2,c3,c4 = st.columns(4)
c1.metric('Simulated review orders', len(orders))
c2.metric('Open reviews', len(orders)-completed)
c3.metric('Inspection pending', pending)
c4.metric('Reviews completed', completed)
st.caption('Counts cover this local ledger only. Repeated assessments are deduplicated; different model policies may create separate orders for one observation. Review completion is not a verified repair. Below-threshold assessments are not logged, so these counts cannot establish a fleet failure rate.')

st.subheader('Business impact scenario')
st.write('Compare a hypothetical unplanned outage with a planned intervention. Change the assumptions to match a customer discussion. These costs are not derived from AI4I, the classifier score, or real operating records.')
with st.expander('Edit cost and timing assumptions', expanded=True):
    a,b,c = st.columns(3)
    hourly = a.number_input('Downtime cost per hour ($)', min_value=0.0, value=2500.0, step=100.0)
    outage = b.number_input('Unplanned downtime (hours)', min_value=0.0, value=8.0, step=0.5)
    planned = c.number_input('Planned downtime (hours)', min_value=0.0, value=2.0, step=0.5)
    emergency = a.number_input('Emergency labor and parts ($)', min_value=0.0, value=4000.0, step=100.0)
    repair = b.number_input('Planned labor and parts ($)', min_value=0.0, value=1800.0, step=100.0)
    inspection = c.number_input('Inspection cost per reviewed alert ($)', min_value=0.0, value=150.0, step=25.0)
    scenarios = a.number_input('Hypothetical incidents in planning period', min_value=0, value=4, step=1)
    success = b.slider('Assumed share of incidents successfully mitigated (%)', 0,100,50)
    alert_count = c.number_input('Assumed alert reviews in planning period', min_value=0, value=10, step=1)
    operating = a.number_input('Software and operating cost for period ($)', min_value=0.0,value=500.0,step=100.0)

unplanned_cost = hourly*outage+emergency
planned_cost = hourly*planned+repair
opportunity = unplanned_cost-planned_cost
mitigated = scenarios*success/100
review_cost = alert_count*inspection
net = mitigated*opportunity-review_cost-operating
hours = mitigated*(outage-planned)
k1,k2,k3,k4 = st.columns(4)
k1.metric('Unplanned incident scenario', f'${unplanned_cost:,.0f}')
k2.metric('Planned intervention scenario', f'${planned_cost:,.0f}')
k3.metric('Scenario net benefit / period', f'${net:,.0f}')
k4.metric('Scenario downtime avoided', f'{hours:,.1f} h')
if net < 0:
    st.warning('Under these assumptions, the intervention program costs more than the modeled benefit. Negative outcomes are retained.')
st.caption('Hypothetical successful mitigation is a user assumption, not model recall, model confidence, or validated probability. No realized savings have been measured.')
left,right = st.columns([1.2,1])
with left:
    st.bar_chart(pd.DataFrame({'Cost ($)':[unplanned_cost,planned_cost]},index=['Unplanned incident','Planned intervention']))
with right:
    st.markdown('**Period economics**')
    st.write(f'Assumed mitigated incidents: {mitigated:g}')
    st.write(f'Gross scenario benefit: ${mitigated*opportunity:,.0f}')
    st.write(f'Alert review cost: ${review_cost:,.0f}')
    st.write(f'Software and operating cost: ${operating:,.0f}')
    st.write(f'Net scenario benefit: ${net:,.0f}')
    if opportunity > 0:
        st.write(f'Break-even successfully mitigated incidents: {(review_cost+operating)/opportunity:.2f}')
    else:
        st.write('No positive per-incident break-even under these assumptions.')
with st.expander('Formula and sensitivity'):
    st.code('Unplanned cost = downtime hours × hourly cost + emergency labor/parts\nPlanned cost = planned downtime × hourly cost + planned labor/parts\nNet benefit = incidents × assumed mitigation share × (unplanned − planned)\n              − alert reviews × inspection cost − operating cost')
    sensitivity = pd.DataFrame([{'Assumed mitigation share':f'{p}%', 'Scenario net benefit ($)':scenarios*p/100*opportunity-review_cost-operating} for p in [0,25,50,75,100]])
    st.dataframe(sensitivity,hide_index=True,width='stretch')

st.subheader('Decision and remediation register')
rows=[]
for order in orders:
    review=by_id.get(order['order_id'],{})
    proposal=order.get('proposal',{})
    rows.append({'Order':order['order_id'],'Observation / asset':proposal.get('asset_id','Unknown'),
                 'Order status':order.get('status','Unknown'), 'Review disposition':review.get('state','Not acknowledged'),
                 'Proposed action':proposal.get('action','Unknown'), 'Decision basis':order.get('reason',''),
                 'Review note and proposed follow-ups':review.get('note',''), 'Updated (UTC)':review.get('updated_at','')})
if rows:
    frame=pd.DataFrame(rows)
    st.dataframe(frame,hide_index=True,width='stretch')
    st.download_button('Export simulated decision register',frame.to_csv(index=False),'fieldwork-decisions.csv','text/csv')
else:
    st.info('No orders in this ledger yet. Open Technician console, assess record 2016 with random forest, then save an inspection-pending review. Refresh this page to see it here.')
st.caption('Remediation choices remain proposals: inspect, verify inventory, draft work scope, review a window, request specialist support, or review parts after diagnosis. No real dispatch, purchasing, or scheduling occurs.')
if events:
    with st.expander('Review activity timeline'):
        st.dataframe(pd.DataFrame(events),hide_index=True,width='stretch')
st.subheader('What this dashboard can and cannot establish')
st.write('Recorded: local simulated orders, saved review states, proposed follow-ups, and review history. Scenario-only: outage exposure, avoided downtime, and economic benefit. Not measured: real production loss, realized savings, actual repair effectiveness, fleet availability, or delivered notifications.')
st.button('Refresh activity')
