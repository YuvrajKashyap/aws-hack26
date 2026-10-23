# Start here: execution-order walkthrough

This is a reading order, not a request to rename modules. Python imports and teammate integrations retain their existing paths. There are two separate workflows: dataset classification and fictional sensor replay. Neither is a production maintenance system.

## 1. Launch and configuration

Run Streamlit with `app.py` from the repository root. Streamlit discovers `pages/1_AI4I_Baseline.py` as the dataset page. Environment settings select offline or Bedrock explanations and the SQLite ledger path. `.env.example` documents settings; it is not loaded automatically.

Read `src/contracts.py` for shared typed artifacts. Read `src/orchestrator.py:configured_provider` for provider selection. Offline returns no provider. Live configuration failures produce a failing provider so the assessment can visibly fall back.

## 2. Dataset preparation and training

Read `src/ai4i.py` in this order: `FEATURES`, `Observation`, `download_dataset`, `fit_baseline`, `metrics`.

The approved UCI AI4I CSV is published synthetic data. Download is explicit, size bounded, checksum checked, and refuses overwrites. The six allowed inputs are product type, air temperature, process temperature, rotation speed, torque, and tool wear. IDs and failure labels are excluded from model inputs.

`fit_baseline` validates rows and binary labels, creates seed-42 stratified 60/20/20 splits, fits preprocessing and random forest on training rows, and selects a threshold on validation F2. It records test metrics, source/hash, split IDs, training-range bounds, and unsupported claims. Classifier scores are uncalibrated. Rows are observations, not a machine timeline.

Read `src/policy.py`: `build_policy` fits RF, gradient boosting, or both. The hybrid averages RF and GB scores; weight and threshold are selected on validation data. `compare_policies` evaluates frozen operating points on test rows. The previously inspected test set makes the comparison exploratory. `src/benchmark.py` is the separate five-model experiment, not a step performed for every assessment.

## 3. Dataset page initialization

Read `pages/1_AI4I_Baseline.py` top to bottom. It checks dependencies and CSV availability, hashes the data, loads the baseline and three-policy comparison, and caches fitted resources in the Streamlit process. Training currently occurs on cache misses; there is no deployed model endpoint or persisted model-serving service. First load can therefore be slower.

## 4. One assessment

The user selects an operating policy and a held-out dataset record, then presses Assess record. `src/ai4i.py:run_record` validates the observation, compares numeric features with training bounds, and abstains outside those bounds. Otherwise it obtains the selected policy score and compares it with the frozen threshold. Its assessment identity includes model identity, record ID, and values.

## 5. Grounded explanation

`run_record` creates fixed evidence statements for the prediction and observed thermal, mechanical, and wear values. Offline mode displays those statements. Live mode calls `src/bedrock.py:BedrockExplainer.generate` through Bedrock Converse to select evidence IDs, not to predict failure or write unrestricted maintenance advice.

The adapter uses configurable model ID, us-east-1, timeouts, bounded attempts, caching, and a process-shared request gate. It does not coordinate separate workshop processes. Returned IDs must be known, unique, and include the prediction. Errors or invalid selection trigger local factual fallback. Out-of-range abstention skips inference.

## 6. Simulated action

`run_record` constructs a typed review proposal for flagged or abstained observations. Below-threshold observations create no order and are not declared safe. AI4I has no verified parts/manual mapping, so this path reserves no part or maintenance slot.

`src/ledger.py:Ledger.simulate` validates the proposal and uses a SQLite transaction and unique key to prevent duplicate orders for the same assessment. Model-specific keys intentionally distinguish policy comparisons; this is not fleet-wide incident deduplication. Storage failure is surfaced by the page, with no completed action confirmed.

## 7. Render the result

The page stores the result with its record/policy selection key and hides it when those selections change. `src/policy.py:explorer_zones` groups observed values; `src/explorer.py:render_machine_explorer` renders the illustrative SVG with zone selection, zoom, keyboard controls, reset, and reduced-motion handling. The image does not diagnose a component. Evidence, comparison, limitations, and order JSON are in detail panels. Ground truth is displayed only for inspection, never passed to the predictor or Bedrock.

## 8. Separate fictional replay

Read these files in execution order:

1. `app.py`: select normal, degrading, or missing-sensor replay.
2. `src/orchestrator.py:run_scenario`: load the corresponding original JSON fixture and record workflow timing.
3. `src/intake.py:validate_window`: validate units, timestamps, readings and quality.
4. `src/diagnosis.py:assess`: apply documented fictional rules, not a trained model.
5. `src/explanation.py:explain`: validate evidence selection or use factual fallback.
6. `src/maintenance.py:propose`: no action, review, or an explicitly fictional bearing inspection.
7. `src/ledger.py:simulate`: atomically reserve fictional inventory and a fixed fictional slot when supported; conflicts require review.
8. `app.py`: display readings, evidence, proposal, order, errors and trace.

This route demonstrates missing-sensor handling and reservation mechanics separately from the AI4I experiment. Its slot is a fixed simulation artifact, not a current appointment.

## 9. AWS boundaries

Bedrock is used for live evidence selection. The workshop provides the environment and browser access; the application runs in its Streamlit process. Kiro is developer assistance. AgentCore hosting, S3 storage and application CloudWatch integration are not deployed by this code. SQLite and CSV remain workshop-local. CloudFront workshop access is not our own production frontend deployment.

## 10. User-only walkthrough

Open the machine maintenance console, compare policy tradeoffs, choose a dataset record, assess it, inspect the decision and quality warnings, click a schematic zone to inspect its readings, expand the evidence, and inspect the simulated review order if present. Changing a record or policy requires reassessment. Repeating the same assessment returns the existing order.

For the fictional workflow, replay normal, degrading, degrading again, then missing-sensor. Inspect the transition, simulated reservation, duplicate prevention, and review-required state. The outage control demonstrates fallback without a network request.

## 11. Customer workflow still to build

A real deployment needs asset registration and actual sensor ingestion; source/unit/time validation; durable model artifacts and independent validation; access control; shared incident deduplication; a technician queue with assignment, acknowledgment and completion; approved manuals/catalogs; and operational audit/monitoring. Actual purchasing, machinery commands and scheduling are absent. RUL remains unsupported. Do not present the current assessment viewer as a completed maintenance-management system.

## 12. Verification reading order

`tests/test_ai4i.py` covers dataset contracts and flow; `tests/test_policy.py` covers selection, identity and explorer behavior; `tests/test_benchmark.py` covers experiments; `tests/test_bedrock.py` covers provider failure and gating; `tests/test_flow.py` covers fictional orchestration and ledger safety; dashboard tests exercise the UI. The last workshop run passed 61 tests. This documentation change does not constitute a new test run.
