# PR5 integration: ML brain, monitor, alerts, diagnosis, notifications

This records the reviewed integration of teammate PR5 (`ml/`) into `yuvraj`, and the
fixes applied on top. Nothing here was pushed or merged to `main` during this work;
it is staged for review. Offline is the default throughout; no AWS calls are made.

## Chronological workflow

1. Confirmed branch `yuvraj`, clean tree, and the remote had not diverged.
2. Fetched read-only refs: `origin/main` (`4706a18`) and `refs/pull/5/head` (`035943a`).
   Confirmed PR5 is based on current `main`.
3. Merged `origin/main` into `yuvraj` (brings PR3/PR4 merge history), then merged the
   reviewed PR5 head into `yuvraj` with `--no-ff`, preserving the teammate's authorship
   (commits `035943a`/`f6e27e7`, "Workshop Participant", remain in history). `ml/` landed
   with no file conflicts.
4. Isolated `ml/` as a package and fixed imports/optional-dependency handling.
5. Built a shared notification outbox in `src/notifications.py` and wired a simulated
   preview/status into the AI4I console review-order flow.
6. Audited and fixed `ml/diagnosis.py` and `ml/alerts.py` for safety.
7. Added focused tests; ran the full offline suite, `pip check`, and Streamlit smoke tests.

## Kept (teammate work preserved)

- The whole `ml/` experiment: `simulator.py`, `monitor.py`, `alerts.py`, `predict.py`,
  `train.py`, `compare.py`, `diagnosis.py`, plus `model.joblib`, `metrics.json`,
  `diagnosis_cache.json`.
- The honesty labels in the original contribution: the HGB risk model is trained on
  AI4I using rpm/torque/temperatures mapped from CRAC signals by an explicit analogy;
  vibration and lube are not in AI4I and feed a rule-based heuristic; `rul_hours` is a
  wear-threshold projection, not a validated remaining-useful-life model.
- The deterministic monitor/alerts pipeline, the tool-calling Bedrock diagnosis agent,
  and its cited-evidence validation (numbers come from `predict.py`, not the LLM).

## Fixed on integration

- **Package isolation.** Added `ml/__init__.py`. Cross-module imports are now relative
  (`from .train import ...`). `joblib`, `lightgbm` and `xgboost` are imported lazily
  inside the functions that train or score. Importing any `ml` module — and running the
  test suite — never requires those packages and never loads `model.joblib`. The
  serialized model stays behind an explicit `predict()`/`_bundle()` call pending separate
  provenance review.
- **Monitor stability (reviewer request).** Replaced the global `alert_no` with a stable
  per-unit/episode `alert_id` (`ALT-<unit>-<NNN>`), so an alert opening on one unit no
  longer changes another unit's alert identity. Readings with missing or non-finite
  channels are now rejected *before* any smoothing or alert state is mutated. The
  predictor is injectable (`Monitor(predictor=...)`) so tests score without the model.
- **Shared notification outbox (`src/notifications.py`).** SQLite-persisted, simulated by
  default. A real send requires explicit live opt-in *and* an injected publisher; the
  module never constructs an AWS client on its own. Idempotency and status are persisted
  so a review order never produces two notifications and a page rerun cannot re-send.
  Concurrency safety is enforced, not assumed: for an automatic call a row that is
  `simulated`, `accepted`, or in-flight `sending` is terminal and is **not** reclaimed, so
  two concurrent callers can never both publish (covered by a deterministic
  blocked-publisher test that asserts exactly one publish across two outbox instances).
  Only `failed` auto-retries. A crash can leave a `sending` row whose real outcome is
  unknown; it is reclaimed only by an explicit `recover=True` call — we document this
  ambiguity and do not promise exactly-once. A stable semantic `dedupe_key` (e.g.
  unit|alert_id|severity), independent of the changing subject/body/timestamp, persists the
  first payload and dedupes later ticks to one notification. "Accepted" (SNS accepted the
  publish) is distinguished from delivery — we never claim an email reached a person.
  Errors are redacted to a safe category. The intended recipient list is display-only; a
  real send publishes to a configured SNS topic ARN, never to an arbitrary to-list.
  Messages carry order/model/evidence identity, are review-only, and make no deadline,
  replacement-certainty, or approval-link claim.

  **The SNS adapter (`SNSPublisher`) exists but its live path is unverified.** No real
  publish has been exercised against an AWS account in this work; tests use an injected
  fake client. Treat live SNS as untested until separately validated with an authorized
  topic and subscription.
- **Teammate notifier routed through shared safety.** `ml/alerts.py`'s `Notifier` now
  delegates to the shared outbox with the stable key as its semantic dedupe key, and can no
  longer send for real just because an SNS topic environment variable is set — live
  requires `allow_live=True` plus an injected publisher. Its event is reported as a
  status (`accepted`/`simulated`/`failed`, with `delivered`), never a misleading "emailed
  to" line, and the old crashing `.jsonl` demo reader was replaced with SQLite inspection.
  `build_email` was reworded to drop the `{APPROVAL_URL}` placeholder, the "act within N h"
  deadline subject, and "approve the plan"/replacement-certainty phrasing; it is now
  review-only.
- **Diagnosis agent.** Defaults to offline: the live model runs only with explicit
  `DIAG_MODE=live`; anything else falls back deterministically with no network. It uses the
  process-wide `src.bedrock.SHARED_GATE`: the gate lock is acquired with a bounded timeout
  and held across the whole multi-turn request loop (so this agent and the evidence selector
  are serialized and paced together), releasing in a `finally`; if the gate is busy beyond
  the budget it falls back. The disk cache key hashes the **full tool-visible context** —
  the complete prediction and its evidence, the recommendation, the recent history samples
  (including the smoothed channels the model can read), and a manual/parts version — so a
  changed input cannot serve a stale diagnosis. Calls remain bounded (max 6 turns). Raw SDK
  errors are redacted to a safe category.
- **Diagnosis output is deterministic.** The rendered diagnosis does **not** surface model
  free text. Root cause is the predictor's failure-mode label; the numbers, summary and
  next steps are templated from `predict.py` values and the deterministic recommendation;
  evidence is a validated subset of the predictor's evidence; citations must be manual
  sections returned by `search_manual` in this run; the part comes from the recommendation
  or a validated id. The model contributes only tool selection, a validated `confidence`
  enum, and those validated selections — it cannot inject fabricated numbers, parts, prose
  or actions (covered by a hostile-model test).

## Deferred

- **Serialized model provenance.** `ml/model.joblib` is committed but is not loaded by the
  integration, tests, or the running app. Loading it needs a separate provenance review.
- **Retraining dependencies.** `ml/train.py` and `ml/compare.py` need `lightgbm` (and
  optionally `xgboost`), which are not in any requirements file. We did not add them: the
  task does not require retraining or promoting the model. To reproduce training later,
  install those separately in the approved environment.
- **Live SNS sending / AgentCore / S3 / CloudWatch.** Not implemented or verified. No IAM,
  deployment, or real send was performed.

## Teammate model metrics — reported as unverified

`ml/metrics.json` (from the contribution) reports, for a 6000/2000/2000 split on AI4I,
hist-gradient-boosting PR-AUC ≈ 0.906, precision ≈ 0.535, recall ≈ 0.897 at
threshold ≈ 0.049. These numbers are **unverified by this integration** — we did not
retrain or re-evaluate the model, and did not load the serialized artifact. They are
**not directly comparable** to the `src/ai4i.py` / `src/policy.py` results: that pipeline
uses a different six-feature allowlist, a different split helper, different estimators and
calibration, and a validation-F2 threshold objective. Treat the two as separate
experiments, not a head-to-head benchmark. The scores are on synthetic data and are not a
claim of factory performance, future-failure forecasting, component diagnosis, or RUL.

## Unresolved limitations

- Notification delivery is never asserted — only acceptance. A crash after a real publish
  but before the result is persisted leaves a recoverable `sending` row; the design is
  at-most-once-intended, not exactly-once.
- The `ml` CRAC telemetry, failure modes, parts catalog and manual are all simulated and
  original; the AI4I→CRAC mapping is an analogy.
- `ml/` is not wired into the production demo flow; it is an isolated experiment reachable
  via its own module entry points.
