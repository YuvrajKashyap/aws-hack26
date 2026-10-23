"""Bounded local workflow shared by UI and CLI; failures retain completed artifacts."""
import argparse
import json
import os
import sqlite3
from pathlib import Path
from time import perf_counter
from .contracts import ScenarioResult, TraceStep
from .intake import validate_window
from .diagnosis import assess
from .explanation import explain, EvidenceSelector
from .maintenance import propose
from .ledger import Ledger

SCENARIOS = ('normal', 'degrading', 'missing-sensor')
FIXTURES = Path(__file__).resolve().parent.parent / 'fixtures'


def load_scenario(scenario_id: str) -> dict:
    if scenario_id not in SCENARIOS:
        raise ValueError('Unknown demo scenario')
    return json.loads((FIXTURES / f'{scenario_id}.json').read_text(encoding='utf-8'))


def run_scenario(scenario_id: str, ledger_path: str | Path = 'data/demo.sqlite', *,
                 explainer: EvidenceSelector | None = None, mode: str = 'offline') -> ScenarioResult:
    if mode not in ('offline', 'bedrock'):
        raise ValueError('Mode must be offline or bedrock')
    if mode == 'bedrock' and explainer is None:
        explainer = configured_provider(mode)
    trace = []
    def step(role, fn):
        start = perf_counter()
        value = fn()
        trace.append(TraceStep(role=role, status='ok', elapsed_ms=round((perf_counter()-start)*1000, 3), detail='Validated artifact'))
        return value
    window = step('Sensor intake', lambda: validate_window(load_scenario(scenario_id)))
    assessment = step('Diagnosis / deterministic rules', lambda: assess(window))
    explanation = step('Evidence explanation', lambda: explain(assessment, explainer))
    if explanation.mode == 'fallback':
        trace[-1].status, trace[-1].detail = 'fallback', explanation.fallback_reason
    proposal = step('Maintenance / deterministic policy', lambda: propose(assessment))
    if proposal.review_required:
        trace[-1].status, trace[-1].detail = 'review_required', proposal.reason
    errors, order = [], None
    try:
        order = step('SQLite simulated ledger', lambda: Ledger(ledger_path).simulate(proposal))
        if order and order.status == 'review_required':
            trace[-1].status, trace[-1].detail = 'review_required', order.reason
    except (OSError, sqlite3.Error):
        errors.append('Local ledger unavailable; no reservation confirmed. Earlier evidence is preserved.')
        trace.append(TraceStep(role='SQLite simulated ledger', status='error', elapsed_ms=0, detail=errors[-1]))
    return ScenarioResult(mode=mode, window=window, assessment=assessment, explanation=explanation,
        proposal=proposal, order=order, trace=trace, errors=errors)


def configured_provider(mode: str):
    if mode == 'offline':
        return None
    if mode != 'bedrock':
        raise ValueError('DEMO_MODE must be offline or bedrock')
    try:
        from .bedrock import from_environment
        return from_environment()
    except Exception:
        from .explanation import UnconfiguredProvider
        return UnconfiguredProvider()


def main():
    parser = argparse.ArgumentParser(description='Original simulated maintenance replay; offline by default')
    parser.add_argument('scenario', choices=SCENARIOS)
    parser.add_argument('--ledger', default=os.getenv('DEMO_LEDGER_PATH', 'data/demo.sqlite'))
    parser.add_argument('--mode', choices=['offline', 'bedrock'], default=os.getenv('DEMO_MODE', 'offline'))
    args = parser.parse_args()
    result = run_scenario(args.scenario, args.ledger, mode=args.mode, explainer=configured_provider(args.mode))
    print(result.model_dump_json(indent=2))
    return 1 if result.errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
