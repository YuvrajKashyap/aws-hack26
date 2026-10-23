"""Render facts locally. An optional model can select evidence, never invent text."""
from typing import Protocol
from pydantic import Field
from .contracts import Contract, Explanation, RiskAssessment


class EvidenceSelector(Protocol):
    def generate(self, payload: dict) -> str: ...


class Selection(Contract):
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class SimulatedOutage:
    def generate(self, payload: dict) -> str:
        raise TimeoutError('Simulated provider outage')


class ProviderConfigurationError(RuntimeError):
    """A safe category, never raw SDK or credential error text."""


class UnconfiguredProvider:
    def generate(self, payload: dict) -> str:
        raise ProviderConfigurationError()


def explain(assessment: RiskAssessment, provider: EvidenceSelector | None = None) -> Explanation:
    selected = list(assessment.evidence_ids)
    mode, reason = 'offline', None
    if provider is not None:
        try:
            output = provider.generate({'assessment_id': assessment.assessment_id,
                'risk_band': assessment.risk_band, 'evidence': [e.model_dump(mode='json') for e in assessment.evidence]})
            selection = Selection.model_validate_json(output)
            ids = selection.evidence_ids
            required = {e.evidence_id for e in assessment.evidence if e.breached}
            if len(set(ids)) != len(ids) or not set(ids) <= set(selected) or not required <= set(ids):
                raise ValueError('Invalid or incomplete evidence selection')
            selected, mode = ids, 'bedrock_selection'
        except ProviderConfigurationError:
            mode, reason = 'fallback', 'Bedrock configuration or SDK initialization unavailable; using validated local facts.'
        except Exception:
            mode, reason = 'fallback', 'Explanation provider unavailable or output rejected; using validated local facts.'
    facts = {e.evidence_id: e for e in assessment.evidence}
    statements = []
    for evidence_id in selected:
        e = facts[evidence_id]
        state = 'crosses' if e.breached else 'does not cross'
        statements.append(f'{e.channel}: {e.value:g} {e.unit} {state} the fictional rule '
            f'{e.comparison} {e.threshold:g} {e.unit} [{e.evidence_id}; {e.reference}].')
    if assessment.risk_band == 'unknown':
        statements.insert(0, 'Risk assessment abstained because sensor evidence is incomplete or outside the supported domain.')
    return Explanation(mode=mode, evidence_ids=selected, statements=statements,
        limitations=assessment.limitations, fallback_reason=reason)
