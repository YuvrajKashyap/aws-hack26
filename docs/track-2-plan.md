# Track 2 architecture and build plan

Design proposal. Implementation and deployment are outside this document. Workshop imports require the applicable approval.

Implementation update (October 23, 2026): the original simulation and live Bedrock evidence selection work; an AI4I classifier, held-out evaluation and dataset review-order dashboard have now been added. See [AI4I baseline](ai4i-baseline.md) and [AWS decisions](aws-decisions.md) for current state. This proposal below is historical design context, not a claim that every step remains unimplemented or that AWS runtime deployment is complete.

## Product and brief fit

Build a compact maintenance console for one simulated machine. The public [Track 2 brief](https://atx.rahman.dev/track-2.html) asks for multiple agent roles connecting sensor evidence to equipment risk, useful life, parts, and maintenance. The proposed scope makes each decision inspectable and identifies estimates the available evidence cannot support. Auto-ordering and scheduling are demonstrated entirely in a simulator.

The organizer's live baseline is the [Bedrock and AgentCore starter kit](https://atx.rahman.dev/hackathon-kit.zip). After account use and setup are authorized, follow its sequence: run the direct Bedrock Converse check in infer.py; use the documented role setup and deploy the minimal agent.py runtime to verify the separate AgentCore execution role; then adapt the handler to the maintenance workflow. Follow the kit README for invocation, troubleshooting, and cleanup. Deterministic local tests complement this live integration; they do not establish that the event runtime works.

The setup_agentcore_role.py step requires iam:CreateRole, iam:PutRolePolicy, and iam:PassRole. Runtime use may incur charges. Do not run these steps without authorization. Use Event dashboard > Event outputs > VScodeIdeURL to reach the shared /workshop workspace. Optional CLI credentials expire after 60 minutes; refresh them through the approved event flow and never commit or paste them into project documentation. Keep shared workspace changes coordinated with teammates.

The kit is linked here, not downloaded or redistributed. Do not publish its contents or restricted derivatives without redistribution permission. The richer AWS reference architectures remain optional extensions; they are not prerequisites for the first complete maintenance flow.

## Smallest coherent architecture

Default recommendation if the team has no stack: one Python process, Pydantic contracts, pytest, a Streamlit console, and SQLite for simulated order state. Add scikit-learn only for the classification experiment and the AWS SDK only for an authorized Bedrock adapter. Pin versions when building after checking compatibility. An existing team stack takes precedence.

| Module | Interface and ownership | Failure behavior |
| --- | --- | --- |
| Sensor intake | validate_window(raw) returns normalized samples with units, timestamps, provenance, and quality flags | Reject impossible units; mark missing/stale channels, never fill them silently |
| Diagnosis | assess(window) returns score type, risk band, evidence IDs, model/rule version, and unsupported claims | Abstain outside the supported feature domain |
| Explanation | explain(assessment, evidence) returns cited rationale and limitations | Reject unknown evidence IDs or changed facts; fall back to a factual template |
| Maintenance policy | propose(assessment, catalog, slots) returns a typed simulated proposal | Unknown part, missing manual, inadequate evidence, or no slot means review required |
| Work-order ledger | simulate(proposal, idempotency_key) returns the same order on replay | Transactional uniqueness prevents double reservations |
| Orchestrator | run_scenario(scenario_id) returns the full trace through these interfaces | Bounded steps; preserve completed evidence and explicit error status |

Diagnosis, explanation, and planning are distinct agent roles with inspectable handoffs; they do not require separate servers or three model calls. The policy and ledger are deterministic tools. A bounded model-backed coordinator may propose the next allowed step; validation controls execution. Use application Bedrock inference through the [Converse interface](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html) only after authorization, with a model supported by the actual account configuration. Report clearly which roles are model-backed and which are rules. No free-running agent loop.

Suggested later layout: src/intake.py, diagnosis.py, explanation.py, maintenance.py, ledger.py, orchestrator.py; app.py for UI; tests/ for interface behavior; fixtures/ for approved original simulations. Adapt these paths to the existing repository when implementation starts. Do not add a message bus, generic repository framework, microservices, vector database, or streaming platform until a concrete demo need justifies it.

## Contracts and honesty

SensorWindow: schema_version, scenario_id, asset_id, start/end UTC timestamps, channel samples, units, source_kind (measured, dataset, derived, simulated), quality flags. Four display channels cover temperature, energy, vibration, and lubricant condition. Missing channels are visible. Derived power is not energy without a duration and integration method.

RiskAssessment: assessment_id, window_id, risk_band, score, score_kind, evidence_ids, predictor_version, limitations, and optional remaining_life with method, unit, interval, and provenance. A null remaining_life is a valid and often correct answer. Use a clearly labeled illustrative wear-threshold projection only for a deliberately constructed simulation with a documented wear rate and threshold; call it a scenario estimate, not validated remaining useful life.

MaintenanceProposal: assessment_id, part_id, manual_reference or explicit simulated-rule reference, reason, duration, candidate_slot, review_required, simulation=true. The ledger enforces an idempotency key based on asset, assessment, and action version; reserve inventory and slot in one transaction. Conflicts produce a review state. Real external actions have no adapter in the demo.

## Data and evaluation

[AI4I at UCI](https://archive.ics.uci.edu/dataset/601/predictive+maintenance+dataset) is synthetic and offers machine-failure labels with temperature, speed, torque, tool wear, and type. It does not provide the complete four-channel demo stream or validated remaining-life labels. Do not present reordered rows as a real machine history. Keep any original four-channel simulation separate from classifier evaluation. Open licensing does not grant workshop import permission.

For a later approved baseline: exclude identifiers and failure-mode target columns from features; split before preprocessing; use a fixed seed and held-out test set. Explain the limitations of random splits on synthetic data; use machine/time grouping only if genuine grouping exists. Compare a simple baseline with a small classifier. Report precision, recall, PR-AUC and a confusion matrix with class counts; choose the operating threshold on validation data, not the test set. Calibration requires its own evidence. No accuracy figures exist yet.

Do not send extra simulated channels into a model trained without them. Use explicit rule evidence for those channels and label any combined score as heuristic. Manuals and parts catalogs must have an approved source; without one, use an original fictional machine and catalog visibly marked as simulated. Do not invent a real manufacturer's maintenance procedure.

## Build sequence and acceptance

1. Freeze one fictional asset, three scenarios, contracts, and permitted material provenance. Exit: everyone can identify simulated versus supported claims.
2. Build deterministic normal, degrading, and missing-sensor replays. Exit: validated evidence reaches a simulated work order without any cloud dependency.
3. Add the approved classification experiment as a separate risk adapter if time and data permission permit. Exit: a reproducible evaluation report with honest limits, no target leakage.
4. After account use, setup, and exact material import are authorized, verify the organizer's direct Bedrock check, then its separate AgentCore runtime path before adapting the handler. Add the explanation adapter with a verified model, us-east-1, bounded output, timeout, shared throttling, and fallback. Exit: record successful direct inference and runtime invocation separately; invalid citations and unavailable inference cannot change the risk or trigger actions. Follow the kit cleanup instructions. Kiro remains developer assistance.
5. Polish the console and rehearse. Exit: the same scenario reset produces the same deterministic assessment and simulated action; model wording may vary but validated facts do not.

Required tests: unit conversion and out-of-order/stale samples; missing-channel abstention; normal-to-degrading risk transition; target-column exclusion; unsupported RUL remains null; hallucinated part/citation rejection; hostile manual text cannot invoke tools; duplicate and concurrent order requests yield one reservation; unavailable part/slot leads to review; inference timeout and throttling preserve a usable result; no external write adapter is reachable. Integration tests cross the same interfaces used by the UI. Live AWS validation is deferred, not assumed.

## Demo presentation

Use one readable screen: machine state and simulation badge, aligned sensor timeline with units, risk evidence beside the marked change, explanation with source chips, and work-order drawer. Text and icons accompany color. Keep keyboard focus visible, respect reduced motion, and show missing, loading, fallback, and error states.

In a roughly three-minute rehearsal: show normal operation; replay the changing window; inspect the evidence and uncertainty; open the simulated part reservation and maintenance slot; replay the request to demonstrate duplicate prevention; finish with the missing-sensor or inference-outage case. Display original readings beside derived values. Do not invent ROI, production readiness, model accuracy, or saved downtime.

## Deferred decisions

Team stack and owners; approved datasets/manuals; permission to import original code and fixtures; actual Bedrock model availability; final event runtime requirements; whether a valid useful-life dataset exists. Resolve these before account access or deployment. Keep restricted workshop material and derivatives out of this public repository.

Workshop constraints: use us-east-1 for any authorized AWS resources. Follow the recommendation of fewer than one generative AI request per second across agents and teammates; use a shared queue with at least two seconds between request starts, concurrency one, bounded retries, and cached explanations. Only AWS-provided or written-approved material may enter the workshop account. Public licensing does not replace that approval. Never export restricted AWS workshop materials or their derivatives.
