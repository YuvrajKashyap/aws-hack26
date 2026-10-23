# aws-hack26

Manufacturing Track 2: predictive maintenance from sensor evidence to simulated maintenance actions.

Start with the [numbered code and user walkthrough](docs/00-code-walkthrough.md) to read both workflows in execution order.

- [Project skill](.agents/skills/manufacturing-track-2/SKILL.md)
- [Architecture and build plan](docs/track-2-plan.md)
- [Codex starter prompt](docs/codex-starter.md)
- [Team branch workflow](CONTRIBUTING.md): personal name branches (`yuvraj`, `abhinav`, etc.), reviewed integration into `main`.
- [Workshop usage and Kiro](docs/workshop-usage.md): verified live Bedrock setup, dashboard restart, and remaining integration.
- [AI4I dataset baseline](docs/ai4i-baseline.md): measured failure classification, setup commands and honest limitations.
- [Five-model comparison](docs/model-comparison.md): reproducible benchmark, selection method and observed tradeoffs.
- [AWS service decisions](docs/aws-decisions.md): selected services, deferred choices and actual deployment status.

## Run the offline demo

Requires Python 3.11 or 3.12. Run from the repository root. No AWS SDK or credentials are needed.

Direct dependencies are pinned in `requirements.txt`; `requirements-lock.txt` records the full verified Windows/Python 3.11 environment. Use `pip install -r requirements-lock.txt` to reproduce that exact environment. Other platforms may resolve different transitive dependencies from `requirements.txt`.

Windows PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
$env:DEMO_MODE = "offline"
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m src.orchestrator degrading
.venv/Scripts/python -m streamlit run app.py
```

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export DEMO_MODE=offline
.venv/bin/python -m pytest -q
.venv/bin/python -m src.orchestrator degrading
.venv/bin/python -m streamlit run app.py
```

Open http://localhost:8501. Replay **normal**, **degrading**, repeat **degrading**, then **missing-sensor**. Expand the work order and trace to inspect the same artifacts used by the CLI and tests. The outage toggle simulates an explanation-provider timeout without making a network call. Normal creates no order; degrading reserves one fictional bearing and one slot; replay returns the same order; missing data requires review and reserves nothing.

The ledger persists in ignored `data/demo.sqlite`. For a fresh rehearsal, stop the server and set `DEMO_LEDGER_PATH` to a new filename, such as `data/rehearsal-2.sqlite`, before restarting. Do not delete a teammate's ledger. `.env.example` documents environment settings; it is not automatically loaded.

## What this demonstrates

One fictional press, `SIM-PRESS-01`, with original simulated temperature, interval energy, vibration, and lubricant-condition readings. Risk is an **illustrative rule score**, never a probability or learned prediction. No accuracy evaluation exists. Remaining useful life is unsupported and always null. The fictional maintenance rule, part, inventory, and January 2026 slots are simulation artifacts, not real manufacturer guidance or current appointments.

The bounded roles are diagnosis (rules), explanation (offline factual template; optional Bedrock evidence selection), and planning (rules). They are not autonomous agents. SQLite is the only action destination. No real order, calendar, machinery, IAM, or deployment adapter exists.

## Extension map

| Module | Boundary |
| --- | --- |
| `src/contracts.py`, `src/intake.py` | Strict typed artifacts, units, preserved originals and quality flags |
| `src/diagnosis.py` | Independent risk rule and identified evidence |
| `src/explanation.py` | Closed evidence selection, citation validation and factual fallback |
| `src/maintenance.py` | Fictional catalog, slots and deterministic policy |
| `src/ledger.py` | Atomic simulated stock + slot reservation and idempotency |
| `src/orchestrator.py` | Shared bounded flow for dashboard, CLI and tests |
| `src/bedrock.py` | Optional Converse adapter, serialized calls, caching, bounded retry |
| `app.py` | Streamlit replay, evidence, order and trace |

See [demo assumptions](docs/demo-assumptions.md) for rule definitions and [live integration](docs/live-integration.md) for the separate organizer workflow. Keep new data providers behind intake and new predictors behind diagnosis; do not mix classifier training data with these fictional replay channels.

---

The following walkthrough is preserved verbatim as requested. It describes the pre-notification-integration state; see [PR5 integration notes](docs/pr5-integration.md) for subsequent changes. The portable code guide is [here](docs/00-code-walkthrough.md).

Our product is a **maintenance decision-support demo**. It takes a set of machine observations, assesses whether they warrant attention, shows the supporting evidence, and creates a **simulated technician-review order** when appropriate.

I added a numbered [code walkthrough](C:/Users/ykyuv/dev/aws-hack26/docs/00-code-walkthrough.md) and linked it from the README. It gives you an execution-order reading path without renaming modules or breaking teammates’ imports. These documentation changes are currently local and uncommitted; the code is unchanged.

**The important distinction: we have two separate experiences.**

| Experience | What it demonstrates |
|---|---|
| AI4I machine console | Trained models, model comparison, evidence inspection, simulated review orders |
| Fictional machine replay | Normal → degrading → missing-sensor scenarios, simulated parts and slot reservations |

They share supporting infrastructure, but the fictional readings are **not** fed into the AI4I models.

**1. The application starts**

You launch Streamlit with `app.py` in the workshop environment.

Streamlit provides the web interface and discovers the AI4I page under `pages/1_AI4I_Baseline.py`. Configuration determines:

- Whether explanations run offline or through Bedrock.
- Which Bedrock model ID to use.
- Where the dataset and SQLite ledger live.

The CloudFront address provides access to the organizer’s workshop. Our Python application runs inside that environment; we haven’t deployed a separate production website.

**Code to read:** `app.py`, then `pages/1_AI4I_Baseline.py`.

**2. The application loads and checks the dataset**

The AI4I console reads the approved CSV containing 10,000 synthetic observations.

Each observation has six model inputs:

| Input | Meaning |
|---|---|
| Product type | Category L, M, or H |
| Air temperature | Kelvin |
| Process temperature | Kelvin |
| Rotational speed | RPM |
| Torque | Newton-metres |
| Tool wear | Minutes |

That is **five numeric measurements plus one category**, rather than four sensors.

The dataset also contains failure labels used for training and evaluation. Those labels and record identifiers are excluded from model inputs.

The software checks required columns, valid values, unique record IDs, and binary labels. It also records a dataset checksum so results can be traced to a particular dataset.

**Code:** `src/ai4i.py`, particularly `Observation` and `fit_baseline`.

**3. We train the models and choose their operating settings**

The dataset is split reproducibly:

- **6,000 training records:** fit the models.
- **2,000 validation records:** choose decision thresholds and hybrid weights.
- **2,000 test records:** measure results after those settings are frozen.

Our three selectable models are:

- Random forest.
- Gradient boosting.
- Hybrid, combining their scores.

For the hybrid:

```text
hybrid score = 0.25 × random-forest score
             + 0.75 × gradient-boosting score
```

The weight was selected from a predefined validation search. Thresholds were selected using validation F2, which emphasizes catching failures more than precision.

The models currently fit when the Streamlit resource cache is empty. Subsequent interactions reuse cached models. We are **not training on every button click**, but we also don’t yet have a separately deployed model-serving endpoint.

The five-model benchmark is a separate experiment, not another step in every assessment.

**Code:** `src/ai4i.py` → `src/policy.py`. Read `src/benchmark.py` for the broader experiment.

**4. The user selects a policy and an observation**

The user chooses a model policy and a dataset record, then presses **Assess record**.

The dashboard passes the selected record’s six inputs to `run_record`.

At this point, the application is assessing an individual dataset observation. It is not receiving a continuous factory stream, and the record number is not a real machine ID.

**Code:** `pages/1_AI4I_Baseline.py` → `src/ai4i.py:run_record`.

**5. The software validates the observation before predicting**

It checks the observation’s schema and compares numeric inputs with ranges seen during training.

There are three possible outcomes:

| Outcome | Meaning |
|---|---|
| Below threshold | The classifier did not flag this observation |
| Review flagged | The score crossed the chosen threshold |
| Abstained | The observation falls outside supported training ranges |

Abstention matters: unfamiliar input should not receive a confident-looking prediction.

For supported input, the chosen model produces a score. The code compares it with that model’s validation-selected threshold.

**The score is not a calibrated real-world failure probability.** For example, `0.38` should not be presented as “a 38% chance this machine fails tomorrow.” We have neither that calibration nor a future failure horizon.

**6. The application constructs the evidence**

The code creates factual statements covering:

- The score and threshold.
- Air and process temperatures.
- Rotation and torque.
- Tool wear and product type.

These are observations and model results. They do not establish that a particular bearing or tool caused the prediction.

Each statement has an evidence identifier, allowing the explanation to point back to an existing fact.

**Code:** the evidence-building section of `src/ai4i.py:run_record`.

**7. Amazon Bedrock helps select evidence**

This is where **Amazon Bedrock** enters the running application.

The classifier has already made its prediction. Bedrock receives the bounded evidence and selects evidence IDs to display. It does not train our classifier, change its score, invent replacement parts, or independently approve maintenance.

The adapter provides:

- A configurable model ID.
- Timeouts and bounded retries.
- Cached responses.
- Serialized requests with pacing.
- Response validation.

Returned evidence IDs must be valid and include the prediction evidence. Invalid responses or inference failures trigger a factual local fallback.

The request gate is shared inside one Python process. It does not coordinate every teammate’s separate process, which is why we use one designated live inference process.

**Code:** `src/bedrock.py`, followed by response validation in `run_record`.

**8. A deterministic rule decides whether to create a simulated order**

The AI4I path uses a deliberately limited action policy:

| Assessment | Action |
|---|---|
| Below threshold | No order |
| Review flagged | Simulated technician-review order |
| Abstained | Simulated technician-review order |

We don’t automatically order a bearing or reserve a maintenance slot from an AI4I prediction. The dataset does not provide a verified failed component, repair manual, or parts mapping.

The software therefore says, effectively: **“This observation needs review; here is the evidence.”**

**Code:** the proposal-building section of `run_record`.

**9. SQLite records the simulated action**

The proposal reaches `src/ledger.py`.

SQLite stores the order using an identity derived from the assessment. Repeating the same assessment returns the existing order rather than creating another one.

Different model policies have different identities, so comparing models does not accidentally reuse an order from another model.

That is useful for this experiment, but it is not yet a complete real-world incident-deduplication system. A production version would need to recognize that several alerts can relate to the same ongoing equipment incident.

**Code:** `src/ledger.py:Ledger.simulate`.

**10. The dashboard renders the result**

The page shows the decision, score, threshold, explanation mode, and any quality warnings.

The interactive 2D schematic groups readings into:

- Drive/spindle.
- Process chamber.
- Tool head.

Clicking a zone zooms into it and displays the relevant readings. Keyboard controls and reset let the user navigate back.

The schematic is an illustrative way to explore evidence. It is **not a component-level diagnostic model**.

Additional panels contain evidence statements, evaluation results, limitations, and simulated order details. If the user changes the selected record or policy, the previous result is hidden until they reassess.

**Code:** `src/policy.py:explorer_zones` → `src/explorer.py` → the page’s result-rendering section.

**11. The separate fictional replay demonstrates maintenance mechanics**

This is the other route, starting from `app.py`:

```text
Original JSON fixture
    ↓
Validate sensors, units, timestamps and quality
    ↓
Apply fictional risk rules
    ↓
Explain the evidence
    ↓
Apply fictional maintenance policy
    ↓
Record simulated reservation or review
```

Its execution-order files are:

1. `src/orchestrator.py`
2. `src/intake.py`
3. `src/diagnosis.py`
4. `src/explanation.py`
5. `src/maintenance.py`
6. `src/ledger.py`

Here, a degrading fictional press can reserve a fictional bearing and a fixed simulated maintenance slot. Missing data or unavailable resources produce review-required behavior.

This demonstrates the action mechanics. It does not mean our AI4I model identified a bearing failure.

**Now, purely from the user’s perspective**

Imagine you are the person reviewing equipment concerns:

1. **Open the console.** You can see that this is a synthetic-data demonstration and actions are simulated.
2. **Choose your operating preference.** Random forest catches more failures but raises more false alerts; gradient boosting raises fewer alerts; hybrid sits between them on this experiment.
3. **Choose an observation.** In the demo, this is a dataset record. In a future customer version, it would be an actual asset and its latest supported readings.
4. **Press Assess.** The console gives you “below threshold,” “review flagged,” or “abstained.”
5. **Inspect the readings.** Click a machine zone to see its measurements.
6. **Read the evidence and limitations.** Understand what the result supports and what it does not.
7. **Inspect the simulated review order.** If the observation needs attention, the application records a review request.
8. **Compare another policy or record.** Reassess explicitly; the console won’t present the previous selection’s result as current.

**That is where the implemented customer journey currently ends.**

A complete customer product would continue with technician assignment, acknowledgment, inspection findings, approved maintenance, completion, and feedback. Those screens and operational integrations are not implemented yet.

The next useful product step is that **review-to-completion workflow**, together with actual asset ingestion and durable shared storage. The 3D visualization can improve presentation later, but it won’t replace those operational steps.
