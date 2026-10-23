# Workshop usage

Verified October 23, 2026 in the authorized Linux workshop: Python 3.11.16, 31 passing tests, compatible dependencies, direct Bedrock Converse response, and application `bedrock_selection` with no fallback and a simulated reserved order. Kiro CLI 2.33.1 was already authenticated; a no-tools chat smoke test responded successfully. This does not verify AgentCore runtime, deployment, or industrial prediction performance.

The tested inference profile is `us.openai.gpt-5.6-luna` in `us-east-1`. Availability is account-specific and may change. The profile rejected `temperature`, so our adapter omits it. The organizer kit remains unchanged and outside this repository.

## Start the dashboard

Use one designated live inference process across the team. Stop a previous dashboard in its terminal with Ctrl+C before restarting. From the workshop terminal:

```sh
cd /workshop/aws-hack26-yuvraj
git branch --show-current
git pull --ff-only origin yuvraj
.venv/bin/python -m pip install -r requirements.txt -r requirements-aws.txt
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=us.openai.gpt-5.6-luna
export BEDROCK_SINGLE_PROCESS_ACK=true
export DEMO_MODE=bedrock
export DEMO_LEDGER_PATH=data/workshop-yuvraj.sqlite
.venv/bin/python -m streamlit run app.py --server.port 8501
```

Open port 8501 through the workshop IDE's Ports panel. Environment exports apply to that terminal only; `.env.example` is documentation, not an automatically loaded file. Use `DEMO_MODE=offline` before launching to work without AWS. Never paste keys into code or Git. Existing workshop identity supplies AWS access.

Replay normal, degrading, degrading again, and missing-sensor. Inspect the explanation mode: `bedrock_selection` confirms accepted model evidence selection; a fallback message means the model path did not complete successfully. Risk and maintenance remain deterministic and all orders are simulated. Remaining useful life is unsupported.

## Use Kiro

Open a separate terminal, leaving the dashboard terminal running:

```sh
cd /workshop/aws-hack26-yuvraj
kiro-cli chat
```

Suggested first instruction: "Read AGENTS.md, CONTRIBUTING.md, .agents/skills/manufacturing-track-2/SKILL.md and docs/track-2-plan.md. Inspect Git status. Work only on yuvraj, preserve teammate work, and describe the existing architecture before editing. Do not deploy, change IAM, or copy organizer materials."

Kiro assists development; it is not the application's Bedrock adapter. Do not grant blanket tool approval. If the workshop login expires, use the organizer's authentication flow yourself.

## Git and remaining integration

GitHub collaborator access and authentication inside the workshop IDE are separate. Each teammate uses their own GitHub account and personal name branch. Public cloning alone does not establish push authentication. Use `git push --dry-run origin yuvraj` to check your session without changing a branch. Never share tokens or use another person's branch.

The offline foundation was merged through PR #1. The later Bedrock compatibility fix is on `yuvraj`; check the current PR status before expecting it on `main`.

AgentCore requires a separately verified execution role and runtime invocation following the organizer kit. S3 for approved data and CloudWatch for deployed runtime logs are later integrations. No IAM resources, S3 buckets, or AgentCore runtime were created by this setup. The current demo runs in the workshop IDE with a local simulated SQLite ledger.
