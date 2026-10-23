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
