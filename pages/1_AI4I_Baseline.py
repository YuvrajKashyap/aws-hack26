"""Machine maintenance console for the AI4I dataset experiment.

Kept distinct from the fictional press simulation. The interactive machine
explorer is the primary workspace; model benchmarks live in the separate Model lab.
"""
import hashlib
import os
from pathlib import Path
import sys

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.orchestrator import configured_provider

st.set_page_config(page_title='Machine maintenance console', layout='wide')
from src.ui import console_style
console_style()
st.title('Machine maintenance console')
st.caption('Inspect the assembly. Review the evidence. Choose a proposed next step.')
mode = os.getenv('DEMO_MODE', 'offline')
# Short simulation / provenance line stays visible at all times.
st.info(f'{mode.upper()} EXPLANATIONS · PUBLISHED SYNTHETIC AI4I DATA · SIMULATED REVIEW ORDERS · '
        'illustrative schematic, not a real machine')

try:
    from src.ai4i import FEATURES, TARGET, fit_baseline, run_record
    from src.policy import POLICIES, build_policy, explorer_zones
    from src.explorer import render_machine_explorer
    from src.scene import render_3d_explorer
    from src.notifications import NotificationOutbox, build_review_message
except ImportError:
    st.warning('Install the optional dataset dependencies: python -m pip install -r requirements-ml.txt')
    st.stop()

csv = Path(os.getenv('AI4I_CSV', 'data/ai4i/ai4i2020.csv'))
if not csv.exists():
    st.warning('AI4I CSV is not installed. After dataset approval, run the setup command in your project terminal.')
    st.code('.venv/bin/python -m src.ai4i --download')
    st.stop()


@st.cache_resource
def load_baseline(path, digest):
    return fit_baseline(path)


@st.cache_resource
def provider(selected_mode):
    return configured_provider(selected_mode)


@st.cache_resource
def policy_for(path, digest, name):
    # One fitted policy per name, cached per dataset so identities stay stable.
    return build_policy(name, path, load_baseline(path, digest))


@st.cache_resource
def notification_outbox(path):
    return NotificationOutbox(path)


csv_path = str(csv.resolve())
csv_digest = hashlib.sha256(csv.read_bytes()).hexdigest()
try:
    bundle = load_baseline(csv_path, csv_digest)
except (ValueError, OSError) as exc:
    st.error(f'Dataset rejected: {exc}')
    st.stop()

report = bundle.report
if not report['matches_verified_uci_download']:
    st.warning('CSV differs from the verified UCI download. Source provenance and these results require separate review.')

# User-friendly policy labels; technical names are kept in the detail expanders.
_FRIENDLY = {'random_forest': 'Catch more failures', 'gradient_boosting': 'Fewer false alerts',
             'hybrid_rf_gb': 'Hybrid balance'}
_TECHNICAL = {'random_forest': 'Random forest', 'gradient_boosting': 'Gradient boosting',
              'hybrid_rf_gb': 'Hybrid RF + GB'}


with st.sidebar:
    st.subheader('Observation controls')
    policy_name = st.selectbox('Operating policy', POLICIES,
        format_func=lambda n: f'{_FRIENDLY[n]} ({_TECHNICAL[n]})', key='console_policy')
    heldout = bundle.heldout.set_index('UDI').sort_index()
    ids = heldout.index.tolist()
    uid = st.selectbox('Dataset record (not a machine ID or time sequence)', ids,
                      index=ids.index(2016) if 2016 in ids else 0, key='console_record')
    st.caption('Demo: record 2016 requests review; record 2 is below the RF threshold. Independent observations, not a timeline.')
    assess = st.button('Assess record', type='primary')
    def start_demo(record):
        st.session_state['console_record'] = record if record in ids else ids[0]
        st.session_state['console_policy'] = 'random_forest'
        st.session_state['run_demo_requested'] = True
    st.button('▶ Run demo · flagged case', on_click=start_demo, args=(2016,), width='stretch')
    st.button('Compare below-threshold case', on_click=start_demo, args=(2,), width='stretch')
    assess = assess or st.session_state.pop('run_demo_requested', False)
    view = st.radio('Inspection view', ['3D assembly', '2D schematic'])
    st.caption('Model evaluation and tradeoffs are in Model lab.')

row = heldout.loc[uid]
active_policy = policy_for(csv_path, csv_digest, policy_name)
if assess:
    try:
        with st.spinner('Classifying and validating evidence…'):
            result = run_record(bundle, row[FEATURES].to_dict(), str(uid),
                os.getenv('DEMO_LEDGER_PATH', 'data/ai4i-orders.sqlite'),
                provider=provider(mode), policy=active_policy)
        st.session_state['ai4i_result'] = result
        # Record exactly which selectors produced this result so a later change invalidates it.
        st.session_state['ai4i_result_key'] = (str(uid), policy_name)
    except Exception:
        st.error('Assessment or ledger failed; no completed action confirmed. Check configuration and local storage.')
        st.session_state.pop('ai4i_result', None)
        st.session_state.pop('ai4i_result_key', None)

result = st.session_state.get('ai4i_result')
result_key = st.session_state.get('ai4i_result_key')
current_key = (str(uid), policy_name)
# Stale guard: never show a result from a different record or policy as current.
stale = result is not None and result_key != current_key

zones = explorer_zones(row[FEATURES].to_dict())
current_result = result if result is not None and not stale else None
assessment = {
    'record_id': str(uid), 'policy': _TECHNICAL[policy_name],
    'decision': ('Abstained' if current_result.predicted_failure is None else
        'Review flagged' if current_result.predicted_failure else 'Below threshold') if current_result else 'Not assessed',
    'explanation_mode': current_result.explanation_mode if current_result else 'Not requested',
    'score': current_result.score if current_result else None,
    'threshold': current_result.threshold if current_result else active_policy.threshold,
}
render_explorer = render_3d_explorer if view == '3D assembly' else render_machine_explorer
# The 2D renderer expects these legacy fields too.
assessment.update(model_id=active_policy.model_id, predicted_failure=current_result.predicted_failure if current_result else None)
components.html(render_explorer(zones, assessment), height=740 if view == '3D assembly' else 560, scrolling=True)
if current_result is None:
    if stale:
        st.session_state.pop('ai4i_result', None)
        st.session_state.pop('ai4i_result_key', None)
        st.warning('Selection changed. Previous decision hidden; press Assess record for this observation.')
    st.info('Readings are ready to explore. Press Assess record in the sidebar to request a decision and explanation. No live Bedrock request or order is triggered by opening this view.')
    st.stop()

# ── Result summary + explorer as the main workspace ──
verdict = 'Abstained' if result.predicted_failure is None else \
    'Review flagged' if result.predicted_failure else 'Below threshold'
m1, m2, m3 = st.columns(3)
m1.metric('Decision', verdict)
m2.metric('Classifier score', 'Abstained' if result.score is None else f'{result.score:.4f}')
m3.metric('Decision threshold', f'{result.threshold:.2f}')
st.caption(f'Record {result.record_id} · {_FRIENDLY[policy_name]} ({_TECHNICAL[policy_name]}) · '
           f'explanation mode {result.explanation_mode}. This is a global machine-level label, not a '
           'component diagnosis or a remaining-life estimate.')
if result.explanation_mode == 'fallback':
    st.warning('Bedrock unavailable or output rejected; showing validated local evidence.')
for flag in result.quality_flags:
    st.warning(flag)

with st.expander('Explanation engine and Bedrock status'):
    st.write('Result explanation mode: **' + result.explanation_mode + '**')
    st.caption('Live Bedrock selects supporting evidence IDs from known facts. The local classifier makes the prediction; fixed policy creates a simulated review order. This is not an autonomous multi-agent maintenance decision.')
    if mode == 'offline':
        st.write('Offline: no Bedrock API request. The evidence statements below are generated locally.')
    else:
        st.write('Configured inference profile: ' + os.getenv('BEDROCK_MODEL_ID', 'not configured'))
        st.caption('A fallback result means the live request failed or its evidence selection was rejected.')

if result.order:
    st.warning('SIMULATED technician-review order created. No part or maintenance slot reserved.')
    with st.expander('Guided case walkthrough · observation to remediation review', expanded=True):
        st.markdown('''1. **Inspect the observation.** Click the assembly zones and review the measured inputs and global assessment. A dataset failure label is not a diagnosis of a particular part.
2. **Acknowledge the concern.** Save an acknowledgment with a simulation note. The order is retained for this exact assessment.
3. **Plan an inspection.** Choose Inspection pending, propose technician inspection and work scope, and describe what needs verification.
4. **Review remediation options.** Propose inventory verification, parts-request review, a maintenance window, or specialist support only as appropriate after diagnosis. No stock, part, or repair need is established by this classifier.
5. **Record the review outcome.** In this rehearsal, save Review completed with a note describing the proposed plan and unresolved checks. This completes the simulated review, not a repair or safety clearance.
6. **Preview the communication.** Inspect or record the simulated notification below. No email is delivered and no operational action is executed.''')

    # Simulated review notification. Preview is always shown; recording it routes
    # through the shared outbox in simulated mode (no publisher, no live opt-in), so
    # nothing is ever sent and a page rerun cannot trigger a real send. The outbox
    # is idempotent on the order id + content, so repeated presses do not duplicate.
    order_id = result.order.order_id
    from src.review import ReviewStore
    reviews = ReviewStore(os.getenv('DEMO_LEDGER_PATH', 'data/ai4i-orders.sqlite'))
    previous_review = reviews.get(order_id)
    st.subheader('Technician review · simulated')
    st.caption('Record a demo inspection outcome. Completion does not certify equipment safety, dispatch a technician, or alter the model result. Do not enter personal or sensitive information.')
    if previous_review:
        st.info(f"{previous_review['state']} · revision {previous_review['version']}")
        st.write(previous_review['note'])
    with st.form('review-' + order_id):
        states = ['Acknowledged', 'Inspection pending', 'Review completed']
        state = st.selectbox('Review disposition', states, index=states.index(previous_review['state']) if previous_review else 0)
        followups = st.multiselect('Proposed follow-up for human review', [
            'Request technician inspection', 'Check spare inventory after component confirmation',
            'Draft work scope', 'Review a maintenance window',
            'Evaluate specialist / contractor support', 'Review a parts request after diagnosis'])
        st.caption('Proposals only. No technician is dispatched, inventory is not verified, no window is reserved, and no part or contractor is ordered. Component diagnosis and approval come first.')
        note = st.text_area('Inspection note (simulation)', max_chars=1500)
        if st.form_submit_button('Save simulated review'):
            try:
                if not note.strip():
                    raise ValueError('Add an inspection note before saving.')
                saved_note = note + ('\nProposed follow-up (not executed): ' + '; '.join(followups) if followups else '')
                reviews.save(order_id, state, saved_note, previous_review['version'] if previous_review else 0)
                st.success('Simulated review saved. No external action was performed.')
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    subject, body = build_review_message({
        'order_id': order_id, 'record_id': result.record_id, 'model_id': result.model_id,
        'policy': f'{_FRIENDLY[policy_name]} ({_TECHNICAL[policy_name]})',
        'decision': verdict, 'score': result.score, 'threshold': result.threshold,
        'evidence': result.statements})
    st.subheader('Simulated review notification')
    st.caption('Default simulated: the message below is not sent anywhere. A real send would require '
               'a separately authorized SNS topic and explicit live opt-in, published to that topic '
               '(never to an arbitrary recipient list).')
    with st.expander('Preview notification message'):
        st.text(subject)
        st.text(body)
    outbox = notification_outbox(os.getenv('NOTIFY_OUTBOX_PATH', 'data/ai4i-notifications.sqlite'))
    existing = outbox.get(NotificationOutbox.notification_id(order_id, subject, body, ['ops (simulated)']))
    if st.button('Record simulated review notification'):
        existing = outbox.send(order_id=order_id, subject=subject, body=body,
                               recipients_display=['ops (simulated)'])
    if existing is not None:
        st.success(f'Notification {existing.notification_id}: status {existing.status} '
                   f'(mode {existing.mode}, delivered={existing.delivered}, attempts={existing.attempts}). '
                   'Accepted or simulated status never implies an email was delivered.')
else:
    st.write('No work order. A below-threshold result does not establish equipment safety.')

# ── Details below, in expanders ──
with st.expander('Evidence statements and ground truth'):
    for statement in result.statements:
        st.write(statement)
    actual = int(heldout.loc[int(result.record_id), TARGET])
    st.caption(f'Dataset ground-truth class: {actual}. Shown for inspection only; never passed to prediction or Bedrock.')

with st.expander('Detailed limitations'):
    for limitation in result.limitations:
        st.caption(limitation)

with st.expander('Raw simulated order'):
    if result.order:
        st.json(result.order.model_dump(mode='json'))
