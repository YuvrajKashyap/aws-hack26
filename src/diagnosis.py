"""An illustrative rule score, independent of language-model output."""
from .contracts import Evidence, RiskAssessment, SensorWindow

RULES = {'temperature': (80, '>='), 'energy': (0.65, '>='), 'vibration': (4.5, '>='), 'lubricant': (60, '<=')}
LIMITATIONS = [
    'Original fictional simulation; thresholds are not validated industrial limits.',
    'Rule score is not a failure probability. No model accuracy evaluation exists.',
    'Remaining useful life is unsupported; no time-to-failure estimate is available.',
]


def assess(window: SensorWindow) -> RiskAssessment:
    evidence = []
    for name, (threshold, comparison) in RULES.items():
        channel = window.channels.get(name)
        if channel and channel.samples:
            last = channel.samples[-1]
            breached = last.value >= threshold if comparison == '>=' else last.value <= threshold
            evidence.append(Evidence(evidence_id=f'{window.window_id}:{name}', channel=name,
                value=last.value, unit=channel.unit, threshold=threshold, comparison=comparison,
                breached=breached, timestamp=last.timestamp))
    score = None if window.quality_flags else sum(e.breached for e in evidence) * 25
    band = 'unknown' if score is None else 'high' if score >= 50 else 'watch' if score else 'normal'
    return RiskAssessment(assessment_id=f'{window.window_id}:SIM-RISK-1', window_id=window.window_id,
        asset_id=window.asset_id, risk_band=band, score=score, evidence=evidence,
        evidence_ids=[e.evidence_id for e in evidence],
        limitations=LIMITATIONS + [f'Data quality: {f}' for f in window.quality_flags])
