"""Research workspace, separate from technician decisions. No AWS calls."""
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
from src.ui import console_style
from src.benchmark import compare

st.set_page_config(page_title='Fieldwork model lab', layout='wide')
console_style()
st.title('Model lab')
st.caption('Measured performance, operating tradeoffs, and experiments. Separate from the technician workspace.')
st.info('PUBLISHED SYNTHETIC AI4I DATA · EXPLORATORY HOLDOUT RESULTS · NO AWS CALLS')
path = Path(os.getenv('AI4I_CSV', 'data/ai4i/ai4i2020.csv'))
if not path.exists():
    st.warning('Install the approved AI4I CSV before opening the model lab.')
    st.stop()

@st.cache_resource
def benchmark(csv, digest):
    return compare(csv)

with st.spinner('Evaluating five model families and three operating policies. Results are cached for this dataset.'):
    report = benchmark(str(path.resolve()), hashlib.sha256(path.read_bytes()).hexdigest())

names = {'random_forest': 'Random forest', 'gradient_boosting': 'Gradient boosting',
         'hybrid_rf_gb': 'Hybrid RF + GB', 'extra_trees': 'Extra trees',
         'logistic_regression': 'Logistic regression', 'hist_gradient_boosting': 'Histogram gradient boosting'}

def row(name, entry, available):
    t = entry['test']; cm = t['confusion_matrix']
    total = sum(sum(r) for r in cm)
    return {'Model': names[name], 'Available in console': available,
            'Accuracy': (cm[0][0]+cm[1][1])/total, 'Precision': t['precision'],
            'Recall': t['recall'], 'Average precision': t['average_precision'],
            'F2': t['f2'], 'Validation F2': entry['validation']['f2'],
            'Threshold': entry['threshold'], 'False alerts': cm[0][1], 'Missed failures': cm[1][0]}

policies = report['operating_policies']['policies']
st.subheader('Three operating policies')
cards = st.columns(3)
descriptions = {'random_forest': 'Prioritize catching failure labels; accept more false alerts.',
                'gradient_boosting': 'Fewer false alerts, with more missed labels than RF on this split.',
                'hybrid_rf_gb': f"{policies['hybrid_rf_gb']['weight']:.0%} RF + {1-policies['hybrid_rf_gb']['weight']:.0%} GB. A measured compromise, not a universal winner."}
for col, (name, entry) in zip(cards, policies.items()):
    with col:
        st.markdown('**'+names[name]+'**')
        st.metric('Test recall', f"{entry['test']['recall']:.1%}")
        st.caption(descriptions[name])
active = pd.DataFrame([row(n,e,True) for n,e in policies.items()])
st.dataframe(active, hide_index=True, width='stretch', column_config={k: st.column_config.NumberColumn(format='%.3f') for k in ['Accuracy','Precision','Recall','Average precision','F2','Validation F2','Threshold']})
st.bar_chart(active.set_index('Model')[['Precision', 'Recall', 'F2']])

st.subheader('All tested model families')
st.caption('Metric columns use a 0–1 scale: 0.95 accuracy means 95%. Accuracy is derived from the held-out confusion matrix.')
families = pd.DataFrame([row(e['name'],e,e['name'] in policies) for e in report['results']])
st.dataframe(families, hide_index=True, width='stretch', column_config={k: st.column_config.NumberColumn(format='%.3f') for k in ['Accuracy','Precision','Recall','Average precision','F2','Validation F2','Threshold']})
st.write('Validation-selected benchmark candidate: **'+names[report['selected_model']]+'**.')
st.caption('Logistic regression, Extra trees, and histogram gradient boosting were evaluated but are not selectable in the technician console. Not deployed does not mean inferior: histogram gradient boosting wins the five-family validation objective. Promotion requires further validation; the console preserves its three reviewed policies.')

st.subheader('Read accuracy in context')
n_test = len(report['split_ids']['test'])
example = report['results'][0]['test']['confusion_matrix']
nonfailure = sum(example[0]); failure = sum(example[1])
c1,c2,c3 = st.columns(3)
c1.metric('Held-out observations', n_test)
c2.metric('Failure labels', failure)
c3.metric('Always nonfailure accuracy', f'{nonfailure/n_test:.1%}')
st.warning('An always-nonfailure model can look accurate while detecting zero failures. Compare recall, precision, false alerts, and missed failures; accuracy alone is misleading.')
with st.expander('Method, provenance, and limits', expanded=True):
    st.write('60% train / 20% validation / 20% test, seed 42. Preprocessing fits on training only. Thresholds and hybrid weight use validation F2. These are fixed configurations, not an exhaustive search.')
    st.write(report['test_caveat'])
    st.caption('No temporal or cross-factory validation; scores are uncalibrated. No future failure horizon, remaining-life estimate, or component diagnosis is established.')
    st.code('Dataset SHA-256: '+report['dataset_sha256'])
st.download_button('Download complete benchmark', json.dumps(report, indent=2), 'fieldwork-benchmark.json', 'application/json')
