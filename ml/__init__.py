"""Isolated ML experiment (teammate PR5), integrated for review.

This package is a separate experiment from the fictional press simulation (`src/`,
`app.py`) and the AI4I dataset console (`pages/`, `src/ai4i.py`). It is NOT wired
into production inference and makes no claims of validated performance.

Honesty boundaries, preserved from the original contribution:
  - The HistGradientBoosting risk model is trained on AI4I 2020 using only rpm,
    torque and temperatures, mapped from CRAC signals by an explicit analogy.
  - vibration and lube are NOT in AI4I; they feed a rule-based heuristic.
  - rul_hours is a wear-threshold projection (heuristic), not a validated RUL.

Integration safety:
  - Importing any module here never imports joblib, lightgbm or xgboost and never
    loads `ml/model.joblib`. Those are deferred to the functions that actually
    train or score, pending separate provenance review of the serialized model.
  - The Bedrock diagnosis agent defaults to offline and routes notifications
    through the shared, simulated-by-default outbox in `src/notifications.py`.
"""
