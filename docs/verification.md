# Local verification

Verified on October 23, 2026, Windows with Python 3.11.9. This record covers the original offline foundation, not live AWS integration.

Commands run from the repository root:

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pip check
.venv/Scripts/python -m src.orchestrator degrading --ledger data/cli-verification.sqlite
.venv/Scripts/python -m streamlit run app.py --server.port 8501
git diff --check
```

Results: 31 tests passed, dependency compatibility check passed, CLI produced a high illustrative rule score with cited evidence and a reserved simulated work order, and the dashboard launched at http://127.0.0.1:8501. The complete dependency snapshot is `requirements-lock.txt`.

Automated checks cover normal/degrading/missing-sensor replay, UTC chart scale, unit normalization, unknown units even on empty channels, invalid timestamps and nonfinite values, stale/out-of-order/domain rejection, target-field exclusion, unsupported RUL, malformed and hostile model output, unknown citations/parts/references, provider configuration failure, timeouts, simulated throttling, shared-gate spacing, cache reuse, bounded queue admission, empty inventory/slot conflicts, ledger failure with retained evidence, and concurrent/idempotent reservation. Network connections are blocked in an offline-flow test; no AWS SDK is required by the offline suite. Provider tests use injected fake clients, not an AWS account.

Browser verification exercised normal operation, degrading reservation, a repeated degrading replay returning the same order ID, and missing vibration producing unknown risk and a review-only order. Keyboard arrow/Enter scenario selection and keyboard replay activation worked with visible focus. At 390 × 844, the scenario controls, stacked risk metrics, missing-data result and simulated outage fallback remained usable; document width was 390 with no page-level horizontal overflow. The mobile maintenance result was inspected, then the viewport override was reset. Tables and full JSON are expandable inspection views.

Failures found and fixed during implementation included invalid proposals poisoning valid reservation keys, an incorrectly localized chart axis labeled UTC, empty-channel invalid units bypassing validation, and live-mode direct calls silently using offline explanations. Cold Streamlit imports needed a longer bounded test startup allowance. No tests remain failing.

Not verified: real Bedrock inference/model access, AWS credential setup, AgentCore execution role/runtime, deployment, or industrial predictive performance. See `live-integration.md` for the separately authorized organizer workflow. No AWS calls, IAM changes, real orders, or kit downloads were performed. Branch instructions are documented, not GitHub branch-protection enforcement. Changes are local on `yuvraj` and have not been pushed.
