"""Machine maintenance console for the AI4I dataset experiment.

Kept distinct from the fictional press simulation. The interactive machine
explorer is the primary workspace; measured evaluation, full policy comparison,
model identities, detailed limitations and raw order JSON live in expanders below.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.orchestrator import configured_provider

st.set_page_config(page_title='Machine maintenance console', layout='wide')
st.title('Machine maintenance console')
mode = os.getenv('DEMO_MODE', 'offline')
# Short simulation / provenance line stays visible at all times.
st.info(f'{mode.upper()} EXPLANATIONS · PUBLISHED SYNTHETIC AI4I DATA · SIMULATED REVIEW ORDERS · '
        'illustrative schematic, not a real machine')

try:
    from src.ai4i import FEATURES, TARGET, fit_baseline, run_record
    from src.policy import POLICIES, build_policy, compare_policies, explorer_zones
    from src.explorer import render_machine_explorer
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
def policy_comparison(path, digest):
    # Validation-selected RF/GB/hybrid operating points; measured on the existing split.
    return compare_policies(path, load_baseline(path, digest))


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
    comparison = policy_comparison(csv_path, csv_digest)
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


def _tradeoff(name):
    e = comparison['policies'][name]
    cm = e['test']['confusion_matrix']
    return (f"recall {e['test']['recall']:.0%} · precision {e['test']['precision']:.0%} · "
            f"{cm[0][1]} false alerts · {cm[1][0]} missed")


# ── Primary controls: compact selectors + Assess, then the explorer workspace ──
left, right = st.columns([1, 1])
with left:
    policy_name = st.selectbox('Operating policy', POLICIES,
        format_func=lambda n: f'{_FRIENDLY[n]} ({_TECHNICAL[n]})')
    st.caption('Measured tradeoff — ' + _tradeoff(policy_name))
with right:
    heldout = bundle.heldout.set_index('UDI').sort_index()
    uid = st.selectbox('Dataset record (not a machine ID or time sequence)', heldout.index.tolist())

row = heldout.loc[uid]
active_policy = policy_for(csv_path, csv_digest, policy_name)
assess = st.button('Assess record', type='primary')

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

if result is None or stale:
    if stale:
        st.warning('Selection changed since the last assessment. Press **Assess record** to evaluate '
                   f'record {uid} with “{_FRIENDLY[policy_name]}”.')
    else:
        st.info('Choose a policy and a record, then press **Assess record** to populate the machine explorer.')
    st.caption('Global machine-level classifier result. Zones below show observed readings as evidence; '
               'they are not a component-level diagnosis.')
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

zones = explorer_zones(result.observation.model_dump(by_alias=True))
explorer_html = render_machine_explorer(zones, {
    'record_id': result.record_id, 'model_id': result.model_id,
    'policy': f'{_FRIENDLY[policy_name]} ({_TECHNICAL[policy_name]})',
    'score': result.score, 'threshold': result.threshold,
    'predicted_failure': result.predicted_failure,
    'explanation_mode': result.explanation_mode})
components.html(explorer_html, height=560, scrolling=False)

if result.order:
    st.warning('SIMULATED technician-review order created. No part or maintenance slot reserved.')

    # Simulated review notification. Preview is always shown; recording it routes
    # through the shared outbox in simulated mode (no publisher, no live opt-in), so
    # nothing is ever sent and a page rerun cannot trigger a real send. The outbox
    # is idempotent on the order id + content, so repeated presses do not duplicate.
    order_id = result.order.order_id
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

with st.expander('Held-out evaluation (validation-selected baseline)'):
    st.caption('Fixed 60/20/20 stratified split. Threshold selected on validation F2; test data never used to choose it.')
    c1, c2, c3 = st.columns(3)
    c1.metric('Test precision', f"{report['test']['precision']:.1%}")
    c2.metric('Test recall', f"{report['test']['recall']:.1%}")
    c3.metric('Test average precision', f"{report['test']['average_precision']:.3f}")
    st.dataframe(pd.DataFrame(report['test']['confusion_matrix'],
        index=['Actual nonfailure', 'Actual failure'], columns=['Predicted nonfailure', 'Predicted failure']))
    st.write('Always-nonfailure baseline', report['most_frequent_baseline'])
    st.caption('Synthetic-dataset classification results, not factory performance or future failure forecasting.')

with st.expander('Full policy comparison and model identities'):
    tech_rows = []
    for name in POLICIES:
        entry = comparison['policies'][name]
        cm = entry['test']['confusion_matrix']
        tech_rows.append({'Policy': _TECHNICAL[name], 'Preset': _FRIENDLY[name],
                          'Weight (RF share)': '—' if entry['weight'] is None else f"{entry['weight']:.2f}",
                          'Threshold': entry['threshold'],
                          'Validation F2': round(entry['validation']['f2'], 4),
                          'Test precision': round(entry['test']['precision'], 4),
                          'Test recall': round(entry['test']['recall'], 4),
                          'Test AP': round(entry['test']['average_precision'], 4),
                          'Test F2': round(entry['test']['f2'], 4),
                          'False alerts': cm[0][1], 'Missed failures': cm[1][0],
                          'Model ID': entry['model_id']})
    st.dataframe(pd.DataFrame(tech_rows), hide_index=True, width='stretch')
    st.caption('Weight and threshold are chosen on validation F2 only, frozen before test scoring. '
               'Each model identity embeds the recipe, weight and threshold so cached explanations and '
               'ledger orders cannot be confused between policies. No policy is claimed best.')

with st.expander('Detailed limitations'):
    for limitation in result.limitations:
        st.caption(limitation)

with st.expander('Raw simulated order and evaluation JSON'):
    if result.order:
        st.json(result.order.model_dump(mode='json'))
    st.download_button('Download evaluation including split IDs',
        data=json.dumps(report, indent=2), file_name='ai4i-evaluation.json', mime='application/json')
