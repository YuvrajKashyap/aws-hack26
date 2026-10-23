# Repository working instructions

Read `.agents/skills/manufacturing-track-2/SKILL.md`, `docs/track-2-plan.md`, and `CONTRIBUTING.md` before making changes. Preserve teammate work and inspect Git status first.

## Branch ownership

- Each teammate works on their own lowercase name branch. Yuvraj uses `yuvraj`; Abhinav uses `abhinav`. Other teammates use their own names.
- Pull and push only the current teammate's own branch. Check the branch before every commit or push. Do not push another teammate's branch or push directly to `main`.
- Bring `main` updates into the personal branch explicitly. Integrate personal-branch changes into `main` through a reviewed pull request. Do not merge or force-push without explicit authorization.
- When acting for Yuvraj, use `yuvraj`. Creating the local branch does not authorize publishing changes.

## Verification and boundaries

Use the documented offline stack and shared orchestration interface. Run the focused tests and `python -m pytest -q` before reporting completion. Keep simulation labels, evidence provenance, unsupported RUL, and model failure behavior visible. Never access AWS credentials, deploy, change IAM, or create real operational actions without separately authorized work.

This is a public repository. Do not import or publish restricted workshop materials, their derivatives, credentials, account outputs, or personal data. The organizer kit remains linked, not copied.
