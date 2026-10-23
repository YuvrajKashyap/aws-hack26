# Codex starter prompt

Paste this into a Codex task opened on this repository, then replace the final line with the requested work.

```text
Work in this repository using .agents/skills/manufacturing-track-2/SKILL.md and docs/track-2-plan.md.

Read applicable AGENTS.md instructions, inspect the current code and Git status, and preserve teammate edits. Complete only the requested change. Prefer a small, testable implementation that fits the existing stack; avoid speculative infrastructure and broad rewrites.

Keep sensor provenance, units, risk assumptions, and simulation labels explicit. Do not invent accuracy, remaining-life estimates, model IDs, or citations. Keep work orders, parts orders, and maintenance scheduling simulated. Test changed behavior and relevant failure cases, and report actual results and remaining limitations.

This repository is public. Exclude secrets, personal material, AWS account identifiers, and restricted workshop materials or derivatives. Only AWS-provided or written-approved material may enter the workshop account. Do not access AWS, deploy, change IAM, or perform external operational actions without authorization. For authorized AWS work, use us-east-1 and coordinate generative requests below one per second across the application. Distinguish Bedrock application inference from Kiro coding assistance.

Before committing or pushing when requested, inspect the diff, check for sensitive or restricted content, and fetch the current remote state. Preserve concurrent work; never force-push over teammate changes. Summarize the change, verification, and any blockers.

Task: [describe the specific change and acceptance criteria]
```
