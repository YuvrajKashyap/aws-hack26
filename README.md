# aws-hack26

Manufacturing Track 2: predictive maintenance from sensor evidence to simulated maintenance actions.

- [Project skill](.agents/skills/manufacturing-track-2/SKILL.md)
- [Architecture and build plan](docs/track-2-plan.md)
- [Codex starter prompt](docs/codex-starter.md)
- [Team branch workflow](CONTRIBUTING.md): personal name branches (`yuvraj`, `abhinav`, etc.), reviewed integration into `main`.
- [Workshop usage and Kiro](docs/workshop-usage.md): verified live Bedrock setup, dashboard restart, and remaining integration.
- [AI4I dataset baseline](docs/ai4i-baseline.md): measured failure classification, setup commands and honest limitations.
- [Five-model comparison](docs/model-comparison.md): reproducible benchmark, selection method and observed tradeoffs.
- [AWS service decisions](docs/aws-decisions.md): selected services, deferred choices and actual deployment status.
- [PR5 ML integration](docs/pr5-integration.md): isolated ML brain/monitor/alerts/diagnosis, the shared simulated notification outbox, and what was kept, fixed and deferred.

## Run the offline demo

Requires Python 3.11 or 3.12. Run from the repository root. No AWS SDK or credentials are needed.

Direct dependencies are pinned in `requirements.txt`; `requirements-lock.txt` records the full verified Windows/Python 3.11 environment. Use `pip install -r requirements-lock.txt` to reproduce that exact environment. Other platforms may resolve different transitive dependencies from `requirements.txt`.

Windows PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
$env:DEMO_MODE = "offline"
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m src.orchestrator degrading
.venv/Scripts/python -m streamlit run app.py
```

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export DEMO_MODE=offline
.venv/bin/python -m pytest -q
.venv/bin/python -m src.orchestrator degrading
.venv/bin/python -m streamlit run app.py
```

Open http://localhost:8501. Replay **normal**, **degrading**, repeat **degrading**, then **missing-sensor**. Expand the work order and trace to inspect the same artifacts used by the CLI and tests. The outage toggle simulates an explanation-provider timeout without making a network call. Normal creates no order; degrading reserves one fictional bearing and one slot; replay returns the same order; missing data requires review and reserves nothing.

The ledger persists in ignored `data/demo.sqlite`. For a fresh rehearsal, stop the server and set `DEMO_LEDGER_PATH` to a new filename, such as `data/rehearsal-2.sqlite`, before restarting. Do not delete a teammate's ledger. `.env.example` documents environment settings; it is not automatically loaded.

## What this demonstrates

One fictional press, `SIM-PRESS-01`, with original simulated temperature, interval energy, vibration, and lubricant-condition readings. Risk is an **illustrative rule score**, never a probability or learned prediction. No accuracy evaluation exists. Remaining useful life is unsupported and always null. The fictional maintenance rule, part, inventory, and January 2026 slots are simulation artifacts, not real manufacturer guidance or current appointments.

The bounded roles are diagnosis (rules), explanation (offline factual template; optional Bedrock evidence selection), and planning (rules). They are not autonomous agents. SQLite is the only action destination. No real order, calendar, machinery, IAM, or deployment adapter exists.

## Extension map

| Module | Boundary |
| --- | --- |
| `src/contracts.py`, `src/intake.py` | Strict typed artifacts, units, preserved originals and quality flags |
| `src/diagnosis.py` | Independent risk rule and identified evidence |
| `src/explanation.py` | Closed evidence selection, citation validation and factual fallback |
| `src/maintenance.py` | Fictional catalog, slots and deterministic policy |
| `src/ledger.py` | Atomic simulated stock + slot reservation and idempotency |
| `src/orchestrator.py` | Shared bounded flow for dashboard, CLI and tests |
| `src/bedrock.py` | Optional Converse adapter, serialized calls, caching, bounded retry |
| `app.py` | Streamlit replay, evidence, order and trace |

See [demo assumptions](docs/demo-assumptions.md) for rule definitions and [live integration](docs/live-integration.md) for the separate organizer workflow. Keep new data providers behind intake and new predictors behind diagnosis; do not mix classifier training data with these fictional replay channels.
