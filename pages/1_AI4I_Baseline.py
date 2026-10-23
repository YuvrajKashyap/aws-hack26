"""Dataset experiment kept distinct from the fictional press simulation."""
import hashlib
import os
from pathlib import Path
import sys
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.orchestrator import configured_provider

st.set_page_config(page_title='AI4I / Measured baseline', layout='wide')
st.title('AI4I: dataset-based failure classification')
mode = os.getenv('DEMO_MODE', 'offline')
st.info(f'{mode.upper()} EXPLANATIONS · PUBLISHED SYNTHETIC DATA · SIMULATED REVIEW ORDERS')
st.write('Classify one dataset observation, inspect its evidence, and route flagged results to technician review.')
st.caption('This is a separate dataset experiment. These rows are not the fictional press timeline or a live machine stream.')

try:
    from src.ai4i import FEATURES, TARGET, fit_baseline, run_record
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


try:
    bundle = load_baseline(str(csv.resolve()), hashlib.sha256(csv.read_bytes()).hexdigest())
except (ValueError, OSError) as exc:
    st.error(f'Dataset rejected: {exc}')
    st.stop()

report = bundle.report
if not report['matches_verified_uci_download']:
    st.warning('CSV differs from the verified UCI download. Source provenance and these results require separate review.')
st.subheader('Held-out evaluation')
st.caption('Fixed 60/20/20 stratified split. Threshold selected on validation F2; test data never used to choose it.')
c1, c2, c3 = st.columns(3)
c1.metric('Test precision', f"{report['test']['precision']:.1%}")
c2.metric('Test recall', f"{report['test']['recall']:.1%}")
c3.metric('Test average precision', f"{report['test']['average_precision']:.3f}")
st.caption('These are synthetic-dataset classification results, not factory performance or future failure forecasting.')
with st.expander('Confusion matrix, baseline and reproducibility'):
    st.dataframe(pd.DataFrame(report['test']['confusion_matrix'],
        index=['Actual nonfailure', 'Actual failure'], columns=['Predicted nonfailure', 'Predicted failure']))
    st.write('Always-nonfailure baseline', report['most_frequent_baseline'])
    st.json({key: value for key, value in report.items() if key != 'split_ids'})
    st.download_button('Download evaluation including split IDs',
        data=__import__('json').dumps(report, indent=2), file_name='ai4i-evaluation.json', mime='application/json')

st.subheader('Assess a held-out record')
heldout = bundle.heldout.set_index('UDI').sort_index()
uid = st.selectbox('Dataset record ID (not a machine ID or time sequence)', heldout.index.tolist())
row = heldout.loc[uid]
st.dataframe(pd.DataFrame([row[FEATURES].to_dict()]), hide_index=True)
st.caption('Model input contains only these six features. Ground-truth and failure-mode labels are excluded.')
if st.button('Assess record', type='primary'):
    try:
        with st.spinner('Classifying and validating evidence…'):
            result = run_record(bundle, row[FEATURES].to_dict(), str(uid),
                os.getenv('DEMO_LEDGER_PATH', 'data/ai4i-orders.sqlite'), provider=provider(mode))
        st.session_state['ai4i_result'] = result
    except Exception:
        st.error('Assessment or ledger failed; no completed action confirmed. Check configuration and local storage.')
        st.session_state.pop('ai4i_result', None)

result = st.session_state.get('ai4i_result')
if result is not None:
    st.subheader(f'Completed dataset assessment: {result.record_id}')
    if str(uid) != result.record_id:
        st.caption('Selection changed. Press Assess record to update the result.')
    verdict = 'Abstained' if result.predicted_failure is None else 'Review flagged' if result.predicted_failure else 'Below threshold'
    st.metric('Decision', verdict)
    st.write('Uncalibrated classifier score:', result.score, '· Decision threshold:', result.threshold)
    st.caption(f'Explanation mode: {result.explanation_mode}')
    if result.explanation_mode == 'fallback':
        st.warning('Bedrock unavailable or output rejected; showing validated local evidence.')
    for flag in result.quality_flags:
        st.warning(flag)
    for statement in result.statements:
        st.write(statement)
    actual = int(heldout.loc[int(result.record_id), TARGET])
    st.caption(f'Dataset ground-truth class: {actual}. Shown for inspection only; never passed to prediction or Bedrock.')
    for limitation in result.limitations:
        st.caption(limitation)
    if result.order:
        st.warning('SIMULATED technician-review order. No part or maintenance slot reserved.')
        st.json(result.order.model_dump(mode='json'))
    else:
        st.write('No work order. A below-threshold result does not establish equipment safety.')
