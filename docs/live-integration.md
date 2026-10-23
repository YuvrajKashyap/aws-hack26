# Later authorized AWS integration

AWS integration has not been run. Local tests cannot establish model access or AgentCore runtime readiness. Offline mode imports no AWS SDK and never reads AWS credentials. The optional adapter is original application code; it contains no organizer-kit code or derived kit prompts.

Follow the sequence already linked in [the track plan](track-2-plan.md):

1. Obtain explicit account-use and exact material-import approval. Coordinate the shared workshop workspace and one designated inference process across teammates. Use us-east-1.
2. In the approved workshop environment, follow the organizer's [starter-kit README](https://atx.rahman.dev/hackathon-kit.zip). First verify its direct `infer.py` Bedrock Converse call with an actually permitted model or inference profile. Do not infer an allowed model ID from an example.
3. Separately authorize the role/setup steps, then verify the starter kit's minimal `agent.py` AgentCore runtime and execution role. The plan identifies `iam:CreateRole`, `iam:PutRolePolicy`, and `iam:PassRole`; this repository does not grant or exercise them.
4. Only after those checks, adapt the approved runtime handler to `run_scenario`. Do not expose arbitrary paths or unvalidated actions in the handler. Record direct inference and runtime invocation results separately. AgentCore packaging and deployment are intentionally not included in this foundation.
5. Follow kit invocation, troubleshooting, credential refresh, and cleanup instructions in that approved environment. Do not copy the kit, restricted derivatives, account outputs, credentials, or logs into this public repo.

For a later approved application test, install `requirements-aws.txt`, configure the actual authorized `BEDROCK_MODEL_ID`, `AWS_REGION=us-east-1`, `DEMO_MODE=bedrock`, and `BEDROCK_SINGLE_PROCESS_ACK=true`. `.env.example` lists timeout/rate controls. Never put credential values in that file. The current task does not authorize setting up or reading credentials.

The adapter uses [Bedrock Converse](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html) and [botocore timeout/retry configuration](https://docs.aws.amazon.com/botocore/latest/reference/config.html). SDK retries are disabled so application retries also pass through the shared gate. Defaults are two attempts, 3-second connect and 10-second read timeouts, at least two seconds between starts, concurrency one, a bounded queue wait, and a bounded process cache. Timeouts are SDK network timeouts, not a hard wall-clock deadline for arbitrary injected clients. Admission fails to deterministic explanation if the gate is busy beyond its wait budget.

The gate is process-wide, not an account-wide distributed quota. Run one designated inference process; all browser sessions in it share the gate. Multiple hosts/processes require external coordination or offline mode. No requests are sent per sensor tick. Configuration/SDK failures, provider failures, throttling, malformed JSON and invalid citations yield explicit factual fallback. Raw provider error messages are not exposed. No live adapter may alter the risk calculation or maintenance policy. Kiro is developer assistance, not the inference backend.
