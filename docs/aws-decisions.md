# Service decisions and dataset transition

Decision date: October 23, 2026. This records choices, not deployment claims.

The [Track 2 brief](https://atx.rahman.dev/track-2.html) links AI4I/UCI and industrial downtime datasets and directs teams to establish a dataset baseline. The three original fixtures remain regression/demo scenarios, not the dataset-based predictor. The organizer how-to catalog is a menu of service references, not a requirement to deploy every listed service. Account availability and deployment permissions must be checked separately.

## Selected direction

| Service | Purpose and decision | Actual state |
| --- | --- | --- |
| Amazon Bedrock | Bounded evidence selection for both simulation and dataset assessments. Preserve validation, cache and rate gate. | Original simulation verified live; dataset path uses the same adapter. |
| Amazon S3 | Next storage integration for approved CSV, references and evaluation artifacts. Keep access private. | Local ignored data files today; no bucket created. |
| Bedrock AgentCore Runtime | Target host for the bounded workflow after organizer starter/runtime verification. | Not deployed; execution-role setup remains separately authorized. |
| AWS IAM | Least-privilege runtime access to Bedrock and explicitly selected data. | Existing workshop identity used; no new role or policy. |
| CloudWatch / AgentCore Observability | Runtime failures, request latency and traces; instrument important workflow boundaries. | Local trace/UI today; no new logging resources. |
| SageMaker AI | Optional next host for the reproducible training job or inference endpoint if required by judging or justified by scale. | scikit-learn training in the IDE/local process now. No hosted endpoint needed for this small baseline. |
| Bedrock Knowledge Bases | Conditional: retrieve approved manuals with citations when those documents exist. | Deferred; AI4I has no repair manual or parts mapping. |
| Bedrock Guardrails | Conditional additional content filtering if we allow free-form text. Does not replace feature validation or deterministic action policy. | Closed evidence-ID schema currently limits model output. |
| Agents for Amazon Bedrock | Alternative managed orchestration approach; do not add a second orchestration stack without a requirement. | Existing Python orchestrator retained. |
| Amazon S3 Vectors | Conditional backing for document retrieval if supported by the chosen knowledge-base setup. | No embeddings or document corpus yet; deferred. |
| Amazon S3 Tables | Tabular analytics at larger scale; unnecessary for one 10,000-row CSV. | Deferred. |
| Amazon CloudFront | Potential frontend distribution if the frontend hosting design needs it. | Workshop-provided browser access is not our own CloudFront deployment. |
| Amazon Q / Kiro / Modernization Assistance | Developer assistance, not a production dependency. Use the already working Kiro CLI. | Kiro signed in and tested. |

No additional service was provisioned by this decision. Before moving the ledger into AgentCore, select durable shared storage with atomic idempotency and inventory/slot transactions. The workshop-local SQLite file is not a fleet-wide cloud ledger.

## Why AI4I

Use the organizer-linked [UCI AI4I 2020 dataset](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset), attributed to Stephan Matzka, DOI 10.24432/C5HS5C, CC BY 4.0. It is published synthetic data. Six features are type, air/process temperature, rotation, torque and tool wear. The target is machine failure at the observation, not a future failure horizon.

It does not contain the fictional press's vibration/lubricant/interval-energy streams, a supported RUL target, actual equipment manuals or a parts catalog. Never map its rows to invented timestamps, combine its classifier with unsupported sensor features, or infer a failed bearing from its binary label.

The dataset path therefore produces a simulated technician-review order for flagged or out-of-range observations. It reserves no part or slot. Existing fictional maintenance reservations remain in the separate simulation page. Genuine part identification, useful-life estimation and model-backed planning remain track-scope gaps requiring evidence and organizer clarification.

## Primary references

- [SageMaker training](https://docs.aws.amazon.com/sagemaker/latest/dg/how-it-works-training.html)
- [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
- [AgentCore Observability and CloudWatch](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
- [Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)

These describe service capabilities, not verified access in this workshop account.
