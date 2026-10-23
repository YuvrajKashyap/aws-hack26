# Five-model AI4I comparison

Measured October 23, 2026 using all 10,000 rows of the checksum-verified UCI CSV.
Run `.venv/bin/python -m src.benchmark` from the repository root (Windows:
`.venv/Scripts/python -m src.benchmark`). Requires requirements-ml.txt.
Full parameters, split IDs, metrics and provenance are saved to ignored
`data/ai4i/model-comparison.json`. No AWS calls are made.

Five practical scikit-learn families, one fixed configuration each, share the
existing seed-42 stratified 6,000/2,000/2,000 split and six-feature allowlist.
Preprocessing fits on training only. Each threshold maximizes validation F2 on
the same 0.05..0.95 grid. Model selection uses validation F2, breaking ties with
validation average precision. F2 favors recall; this is a demo objective, not a
measured factory cost function. The existing test set has already been inspected:
these are exploratory comparisons, not new external validation.

| Model | Threshold | Validation F2 | Test precision | Test recall | Test AP | Test F2 | False alerts | Missed failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic regression | .80 | .4897 | .3478 | .5882 | .4087 | .5168 | 75 | 28 |
| Random forest | .15 | .6905 | .3974 | .8824 | .6860 | .7092 | 91 | 8 |
| Extra trees | .40 | .6130 | .4333 | .7647 | .6344 | .6633 | 68 | 16 |
| Gradient boosting | .15 | .7584 | .6548 | .8088 | .8304 | .7725 | 29 | 13 |
| Histogram gradient boosting | .20 | .7803 | .7083 | .7500 | .7926 | .7413 | 21 | 17 |

Histogram gradient boosting is the validation-selected candidate. Ordinary
gradient boosting has the strongest observed test F2/AP, while random forest has
the highest test recall. Do not silently select by test scores or claim one is
best for every deployment. Cross-validation on development data and an agreed
false-alarm/missed-failure tradeoff should precede promotion. The dashboard still
uses the verified random forest; this experiment does not change runtime behavior.

All test rows total 2,000, with 68 failures. The always-nonfailure comparator has
zero recall and AP .034. No identifiers or failure-mode labels enter training.
Scores remain uncalibrated; synthetic labels do not establish future failure
forecasting, component diagnosis, RUL or real-world accuracy. See
[baseline provenance](ai4i-baseline.md) for the checksum and source attribution.


## Three selectable operating policies (RF, GB, hybrid)

Measured October 23, 2026 on all 10,000 rows of the checksum-verified CSV
(SHA-256 `dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e`),
seed 42, scikit-learn 1.7.2. The same `python -m src.benchmark` run now also emits
an `operating_policies` block; the Streamlit **AI4I Baseline** page lets you pick
one policy for a record assessment. Reproduce offline from the repository root:

```sh
.venv/bin/python -m pip install -r requirements-ml.txt
.venv/bin/python -m src.ai4i --download        # omit --download if the CSV exists
DEMO_MODE=offline .venv/bin/python -m src.benchmark
DEMO_MODE=offline .venv/bin/python -m pytest -q
DEMO_MODE=offline .venv/bin/python -m streamlit run app.py
```

On Windows replace `.venv/bin/python` with `.venv/Scripts/python`. No AWS calls
are made. Do not start a second live inference process if one is already running.

`src/policy.py` builds three usable policies that share the existing seed-42
60/20/20 split, the six-feature allowlist, and the fixed 0.05..0.95 validation-F2
threshold grid. Base models fit on the 60% training split only.

- **Random forest** — the verified baseline estimator and threshold.
- **Gradient boosting** — ordinary `GradientBoostingClassifier`, same recipe as the benchmark family.
- **Hybrid RF + GB** — weighted probability average `w·p_rf + (1−w)·p_gb`. The
  weight is chosen from the fixed grid `[0.25, 0.5, 0.75]` and the threshold from
  the 0.05..0.95 grid, both by **validation F2 only** (ties prefer higher average
  precision, then higher threshold). The chosen `(weight, threshold)` is frozen
  before any test score is computed.

Each policy carries a distinct `model_id` of the form `AI4I-RF…`, `AI4I-GB…`,
`AI4I-HYB…`. The identity hash embeds the dataset digest, recipe, seed, threshold
(and, for the hybrid, the weight), so cached explanations and ledger idempotency
keys can never confuse one policy for another. A flagged record still creates only
a simulated technician-review order through the existing idempotent ledger.

Measured on the held-out test set (2,000 rows, 68 failures):

| Policy | Weight (RF share) | Threshold | Validation F2 | Test precision | Test recall | Test AP | Test F2 | False alerts | Missed failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Random forest | — | .15 | .6905 | .3974 | .8824 | .6860 | .7092 | 91 | 8 |
| Gradient boosting | — | .15 | .7584 | .6548 | .8088 | .8304 | .7725 | 29 | 13 |
| Hybrid RF + GB | .25 | .20 | .7407 | .6364 | .8235 | .8295 | .7778 | 32 | 12 |

The hybrid's validation search selected weight 0.25 / threshold 0.20; the other
weights scored lower validation F2 (0.5 → .7280, 0.75 → .7256). **The hybrid is
not the validation-selected winner** — gradient boosting has the highest
validation F2 (.7584 vs .7407), so by the stated objective GB is the stronger
single model. On the previously-inspected (exploratory) test set the hybrid edges
GB on F2 (.7778 vs .7725) with near-identical AP, while random forest keeps the
highest recall and the most false alerts. These differences are small and on
synthetic data; no policy is claimed best for any real deployment. Choose a policy
by an agreed false-alarm/missed-failure tradeoff, not by test F2 alone.

Limitations from the baseline still apply in full: synthetic labels, uncalibrated
scores, a random (not temporal or cross-factory) split, no RUL, and observed
inputs that are evidence, not component attribution. The runtime production model
is unchanged (`production_model_changed: false`).

## Machine maintenance console and interactive explorer

The AI4I page is the **Machine maintenance console**. Compact operating-policy and
record selectors plus an **Assess record** button sit at the top; the interactive
machine explorer is the primary workspace immediately below. Measured baseline
evaluation, the full policy comparison with technical model IDs, detailed
limitations, and the raw simulated-order JSON are collapsed into expanders beneath
it. A short simulation/provenance banner and the global-versus-component note stay
visible at all times. Changing either the record or the policy retracts the
previous result immediately — a stale assessment is never shown as current; the
console prompts for a fresh **Assess record**.

Policy presets use plain-language labels with the measured tradeoff shown beside
the selection: **Catch more failures** (random forest, highest recall, most false
alerts), **Fewer false alerts** (gradient boosting, more precise), and **Hybrid
balance** (RF + GB). Technical model names and identities remain in the detail
expanders.

The explorer (`src/explorer.py`, inline SVG/HTML, no remote assets or new build
stack) draws one connected, original machine silhouette — bed and rails, drive
shaft/spindle, process-chamber enclosure, and tool head linked by conduits — with
three clickable zones. Click or keyboard-focus a zone to smoothly zoom in and read
that zone's observations for the **currently selected record**: rotation/torque and
type on the drive, air/process temperatures in the chamber, tool wear at the head.
A side panel shows the honest global assessment (verdict, policy, score, threshold,
model identity).

The schematic is explicitly labelled illustrative with high-contrast, legible
sans-serif type. Zone readings are observed evidence only; the classifier produces
a machine-level label and the explorer does not attribute it to a component or
assert a part has failed. Dataset rows are not a real machine timeline. Zoom/pan
use a CSS transform that respects `prefers-reduced-motion`; zones are keyboard
reachable with visible focus, and Esc or Reset returns to the full view. The
original fictional press replay remains a separate page (`app.py`), unchanged.
