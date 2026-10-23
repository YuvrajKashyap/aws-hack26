"""Validated artifacts exchanged by bounded roles; no provider-specific types."""
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

ChannelName = Literal['temperature', 'energy', 'vibration', 'lubricant']


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Sample(Contract):
    timestamp: AwareDatetime
    value: float


class Channel(Contract):
    unit: str
    samples: list[Sample] = Field(max_length=1000)
    original_unit: str | None = None
    original_samples: list[Sample] = Field(default_factory=list)


class SensorWindow(Contract):
    schema_version: Literal['1']
    scenario_id: str
    asset_id: str
    start: AwareDatetime
    end: AwareDatetime
    source_kind: Literal['simulated', 'measured', 'dataset', 'derived']
    provenance: str = Field(min_length=1)
    channels: dict[ChannelName, Channel]
    quality_flags: list[str] = Field(default_factory=list)
    window_id: str = ''

    @model_validator(mode='after')
    def valid_interval(self):
        if self.end <= self.start:
            raise ValueError('Window end must follow start')
        return self


class Evidence(Contract):
    evidence_id: str
    channel: ChannelName
    value: float
    unit: str
    threshold: float
    comparison: Literal['>=', '<=']
    breached: bool
    timestamp: AwareDatetime
    reference: Literal['SIM-RISK-1'] = 'SIM-RISK-1'


class RiskAssessment(Contract):
    assessment_id: str
    window_id: str
    asset_id: str
    risk_band: Literal['normal', 'watch', 'high', 'unknown']
    score: int | None = Field(default=None, ge=0, le=100)
    score_kind: Literal['illustrative_rule_score'] = 'illustrative_rule_score'
    evidence: list[Evidence]
    evidence_ids: list[str]
    predictor_version: Literal['SIM-RISK-1'] = 'SIM-RISK-1'
    limitations: list[str]
    remaining_life: None = None


class Explanation(Contract):
    mode: Literal['offline', 'fallback', 'bedrock_selection']
    evidence_ids: list[str]
    statements: list[str]
    limitations: list[str]
    fallback_reason: str | None = None


class MaintenanceProposal(Contract):
    assessment_id: str
    asset_id: str
    action: Literal['none', 'review', 'inspect_bearing']
    action_version: Literal['SIM-POLICY-1'] = 'SIM-POLICY-1'
    part_id: str | None = None
    manual_reference: str | None = None
    reason: str
    duration_minutes: int = Field(default=0, ge=0)
    candidate_slot: str | None = None
    review_required: bool
    simulation: Literal[True] = True


class WorkOrder(Contract):
    order_id: str
    idempotency_key: str
    status: Literal['reserved', 'review_required']
    reason: str
    proposal: MaintenanceProposal
    simulation: Literal[True] = True


class TraceStep(Contract):
    role: str
    status: Literal['ok', 'fallback', 'review_required', 'error']
    elapsed_ms: float
    detail: str


class ScenarioResult(Contract):
    mode: Literal['offline', 'bedrock']
    window: SensorWindow
    assessment: RiskAssessment
    explanation: Explanation
    proposal: MaintenanceProposal
    order: WorkOrder | None
    trace: list[TraceStep]
    errors: list[str] = Field(default_factory=list)
