"""Original fictional maintenance policy. No external actions are defined."""
from .contracts import MaintenanceProposal, RiskAssessment

PART = 'SIM-BEARING-01'
REFERENCE = 'SIM-RULE-1'
SLOT = '2026-01-01T13:00:00Z/2026-01-01T14:00:00Z'


def default_catalog() -> dict:
    return {PART: {'reference': REFERENCE, 'quantity': 2, 'duration_minutes': 60}}


def default_slots() -> list[str]:
    return [SLOT]


def propose(assessment: RiskAssessment, catalog: dict | None = None,
            slots: list[str] | None = None) -> MaintenanceProposal:
    catalog = default_catalog() if catalog is None else catalog
    slots = default_slots() if slots is None else slots
    base = dict(assessment_id=assessment.assessment_id, asset_id=assessment.asset_id)
    if assessment.risk_band == 'normal':
        return MaintenanceProposal(**base, action='none', reason='No fictional risk threshold crossed.', review_required=False)
    breached = {e.channel for e in assessment.evidence if e.breached}
    part = catalog.get(PART, {})
    supported = (assessment.asset_id == 'SIM-PRESS-01' and assessment.risk_band == 'high'
        and {'temperature', 'vibration'} <= breached and part.get('reference') == REFERENCE
        and part.get('quantity', 0) > 0 and part.get('duration_minutes') == 60 and SLOT in slots)
    if not supported:
        return MaintenanceProposal(**base, action='review', review_required=True,
            reason='Review required: insufficient evidence, unsupported rule/reference, part unavailable, or no simulated slot.')
    return MaintenanceProposal(**base, action='inspect_bearing', part_id=PART,
        manual_reference=REFERENCE, reason='Fictional temperature and vibration thresholds crossed; reserve a simulated bearing inspection.',
        duration_minutes=60, candidate_slot=SLOT, review_required=False)
