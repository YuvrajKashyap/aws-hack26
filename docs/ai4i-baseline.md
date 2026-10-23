# AI4I baseline: reproducible dataset experiment

This is separate from the three original fictional press fixtures. No dataset CSV or serialized model is committed. The explicit download command fetches the organizer-linked UCI archive, reads only ai4i2020.csv, checks its SHA-256, and stores it under ignored data/. Subsequent training and offline inference need no network or AWS credentials. It never loads a pickle from disk.

Attribution: Stephan Matzka (2020), AI4I 2020 Predictive Maintenance Dataset, UCI Machine Learning Repository, DOI 10.24432/C5HS5C, CC BY 4.0. [Source and license](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset).

## Run

Linux workshop, from your own clean branch checkout:

```sh
.venv/bin/python -m pip install -r requirements-ml.txt
.venv/bin/python -m src.ai4i --download
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run app.py
```

On Windows replace .venv/bin/python with .venv/Scripts/python. Omit --download when the CSV already exists. The existing dashboard picks up the new **AI4I Baseline** page; do not launch a second live inference process if it is already running. DEMO_MODE=offline makes no model calls. DEMO_MODE=bedrock uses the existing configured, rate-limited evidence selector; all normal AWS configuration still applies. AI4I_CSV optionally selects a CSV; a changed checksum is visibly flagged as unverified provenance.

The CLI writes data/ai4i/evaluation.json with all split IDs, the dataset hash, fixed recipe, threshold, baseline and model metrics. The dashboard trains the small fixed model once per dataset/process cache and lets you inspect any held-out record. The displayed ground-truth label is never passed to the predictor or Bedrock.

## Method

- 10,000 published synthetic observations; six explicitly allowlisted inputs. UDI, Product ID, Machine failure and all failure-mode labels are excluded from the model inputs.
- Fixed seed 42, stratified 60% train / 20% validation / 20% test. Preprocessing fits only on training data. This random split does not establish temporal or cross-factory generalization.
- Random forest, 200 trees, minimum leaf size 2, balanced_subsample class weights, one CPU worker. scikit-learn 1.7.2. No test-set hyperparameter search.
- Threshold selected using maximum validation F2 on a fixed 0.05-to-0.95 grid, with higher-threshold tie break. F2 weights recall more heavily than precision. Test results are evaluated only after that selection.
- Compare with an always-nonfailure baseline. Report precision, recall, average precision (AP, not trapezoidal PR-AUC), F2, class counts and confusion matrix. Scores are uncalibrated, not validated real-world probabilities.
- Runtime abstains for numeric inputs outside training min/max; invalid/missing/target-containing inputs are rejected. Range checks do not guarantee that all other out-of-distribution combinations can be detected.
- A flagged observation creates only a simulated human-review order through the existing idempotent ledger. No verified maintenance procedure, component diagnosis, part reservation or RUL estimate is inferred.

## Measured result, October 23, 2026

CSV SHA-256: dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e

Local Python 3.11 / scikit-learn 1.7.2 run; threshold 0.15 selected on validation. Test set: 2,000 rows, 68 failure labels, 1,932 nonfailure labels. No runtime range abstentions on this test split.

| Metric | Random forest | Always nonfailure |
| --- | ---: | ---: |
| Precision | 0.397351 | 0 |
| Recall | 0.882353 | 0 |
| Average precision | 0.686015 | 0.034 |
| F2 | 0.709220 | 0 |

Confusion matrix (rows actual 0/1, columns predicted 0/1): [[1841, 91], [8, 60]]. That is 60 detected failure labels, 8 missed failures and 91 false alerts. These false positives are a concrete reason to require review. Do not market the result as factory accuracy, future failure forecasting, prevented downtime or validated useful-life estimation.

## Extension boundaries

src/ai4i.py owns dataset intake, training, evaluation and one-record orchestration. pages/1_AI4I_Baseline.py owns display. src/bedrock.py still owns all model networking. src/ledger.py remains the sole action destination. Tests use a small original test dataset, not the real held-out set; reported metrics come only from the actual UCI run.

See [AWS service decisions](aws-decisions.md) before adding infrastructure. Keep the organizer kit separate and preserve teammate frontend work.
