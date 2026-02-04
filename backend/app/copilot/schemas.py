"""
Copilot response schemas (Phase 4)
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


class CopilotMeta(BaseModel):
    org_id: str
    plan_id: str
    as_of: datetime
    evaluated_at: datetime
    windows: Dict[str, str]
    data_sources: Dict[str, str]
    offline: bool = False
    trust: Optional[Dict[str, Any]] = None  # PlanTrustReport as dict


class Signal(BaseModel):
    kind: Literal[
        "lane_rate_shift",
        "destination_score_drop",
        "market_temp_downgrade",
        "load_unavailable",
    ]
    severity: Literal["low", "medium", "high"]
    summary: str
    details: Dict[str, Any] = {}


class Suggestion(BaseModel):
    kind: Literal[
        "take_now",
        "counter_offer",
        "alternate_destination",
        "add_buffer",
        "manual_review",
    ]
    summary: str
    rationale: str
    data: Dict[str, Any] = {}


class CopilotResponse(BaseModel):
    meta: CopilotMeta
    status: Literal["ok", "degraded", "unknown"]
    signals: List[Signal] = []
    suggestions: List[Suggestion] = []
    explanations: List[str] = []


# ---- Phase 4.1: Branch Plans ----


class BranchPlanRequest(BaseModel):
    plan_id: str
    suggestion_kind: str
    suggestion_data: Dict[str, Any] = {}
    max_plans: int = 2


class BranchPlanSummary(BaseModel):
    plan_id: str
    num_loads: int
    profit_per_day_usd: float
    net_profit_usd: float
    total_revenue_usd: float
    total_costs_usd: float
    end_location: str
    confidence: str
    plan_score: float


class BranchPlanResponse(BaseModel):
    parent_plan_id: str
    suggestion_applied: str
    constraint_changes: Dict[str, Any] = {}
    plans: List[BranchPlanSummary] = []
    evaluation_id: Optional[int] = None
    warnings: List[str] = []


# ---- Phase 4.2: Evaluation History + Replay ----


class EvaluationHistoryItem(BaseModel):
    id: int
    plan_id: str
    status: Literal["ok", "degraded", "unknown"]
    signal_count: int
    suggestion_count: int
    timestamp: datetime
    windows: Dict[str, str] = {}
    data_sources: Dict[str, str] = {}


class DriftSummary(BaseModel):
    new_signals: List[Dict[str, Any]] = []
    resolved_signals: List[Dict[str, Any]] = []
    severity_changes: List[Dict[str, Any]] = []


class EvaluationReplayResponse(BaseModel):
    evaluation_id: int
    plan_id: str
    original: CopilotResponse
    replayed: CopilotResponse
    drift: DriftSummary
    original_timestamp: datetime
    replayed_at: datetime


# ---- Phase 5: Plan Outcomes — Actuals vs Estimates (Stratum 4A) ----


class EconomicsSummary(BaseModel):
    """Canonical economics breakdown. Used in both predictions and reports."""
    gross_revenue: str  # Decimal as string to avoid float
    total_costs: str
    net_profit: str
    profit_per_day: str
    fuel_cost: Optional[str] = None
    toll_cost: Optional[str] = None
    waiting_cost: Optional[str] = None
    maintenance_reserve: Optional[str] = None
    opportunity_cost: Optional[str] = None
    deadhead_cost: Optional[str] = None


class TimeSummary(BaseModel):
    duration_min: Optional[int] = None
    drive_min: Optional[int] = None
    wait_min: Optional[int] = None
    dwell_min: Optional[int] = None


class StructureSummary(BaseModel):
    num_loads: int
    miles_loaded: Optional[int] = None
    miles_deadhead: Optional[int] = None
    total_miles: Optional[int] = None


class PredictionSnapshotCreate(BaseModel):
    plan_id: str


class PredictionSnapshotResponse(BaseModel):
    id: str
    org_id: str
    plan_id: str
    plan_generation_event_id: Optional[int] = None
    created_at: datetime
    predicted_revenue: Optional[str] = None
    predicted_costs: Optional[str] = None
    predicted_net_profit: Optional[str] = None
    predicted_profit_per_day: Optional[str] = None
    predicted_miles_total: Optional[int] = None
    predicted_miles_deadhead: Optional[int] = None
    predicted_duration_min: Optional[int] = None
    predicted_num_loads: Optional[int] = None
    predicted: Dict[str, Any] = {}


class OutcomeCreate(BaseModel):
    plan_id: str
    prediction_snapshot_id: Optional[str] = None


class OutcomeUpdate(BaseModel):
    actual_revenue: Optional[str] = None  # Decimal as string
    actual_fuel_spend: Optional[str] = None
    actual_tolls: Optional[str] = None
    actual_maintenance: Optional[str] = None
    actual_other_costs: Optional[str] = None
    actual_miles_loaded: Optional[int] = None
    actual_miles_deadhead: Optional[int] = None
    actual_drive_min: Optional[int] = None
    actual_wait_min: Optional[int] = None
    actual: Optional[Dict[str, Any]] = None  # Full JSONB override
    notes: Optional[str] = None
    status: Optional[Literal["pending", "partial", "complete"]] = None


class OutcomeResponse(BaseModel):
    id: str
    org_id: str
    plan_id: str
    prediction_snapshot_id: Optional[str] = None
    status: str
    source: str
    actual_revenue: Optional[str] = None
    actual_fuel_spend: Optional[str] = None
    actual_tolls: Optional[str] = None
    actual_maintenance: Optional[str] = None
    actual_other_costs: Optional[str] = None
    actual_miles_loaded: Optional[int] = None
    actual_miles_deadhead: Optional[int] = None
    actual_drive_min: Optional[int] = None
    actual_wait_min: Optional[int] = None
    actual: Dict[str, Any] = {}
    notes: Optional[str] = None
    recorded_at: datetime
    completed_at: Optional[datetime] = None


class VarianceDelta(BaseModel):
    field: str
    predicted: Optional[str] = None
    actual: Optional[str] = None
    delta: Optional[str] = None
    variance_pct: Optional[str] = None


class OutcomeFlag(BaseModel):
    flag: Literal[
        "cost_overrun", "profit_leakage", "time_overrun",
        "waiting_overrun", "revenue_shortfall", "revenue_surplus",
    ]
    severity: Literal["low", "medium", "high"]
    summary: str


class OutcomeReport(BaseModel):
    plan_id: str
    prediction_snapshot_id: Optional[str] = None
    outcome_id: Optional[str] = None
    predicted_summary: Dict[str, Any] = {}
    actual_summary: Dict[str, Any] = {}
    deltas: List[VarianceDelta] = []
    flags: List[OutcomeFlag] = []
    explanations: List[str] = []


class OutcomeSummaryItem(BaseModel):
    plan_id: str
    outcome_id: Optional[str] = None
    status: str
    predicted_net_profit: Optional[str] = None
    actual_net_profit: Optional[str] = None
    profit_variance_pct: Optional[str] = None
    predicted_duration_min: Optional[int] = None
    actual_duration_min: Optional[int] = None
    time_variance_pct: Optional[str] = None
    recorded_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ---- Stratum 4B: Decision Feedback Loop ----


class DecisionCreate(BaseModel):
    plan_id: str
    decision_type: Literal["accepted", "rejected", "modified"]
    reason: Optional[str] = None


class DecisionResponse(BaseModel):
    id: int
    org_id: str
    plan_id: str
    decision_type: str
    reason: Optional[str] = None
    outcome_id: Optional[str] = None
    prediction_snapshot_id: Optional[str] = None
    decision_context_snapshot_id: Optional[str] = None  # Stratum 5D: Learning Loop
    timestamp: datetime


# ---- Stratum 5A: Prediction Calibration ----


class CalibrationMetric(BaseModel):
    name: str
    predicted_avg: str  # Decimal as string
    actual_avg: str
    mean_error: str  # signed: actual - predicted
    mae: str  # mean absolute error
    mean_variance_pct: str  # signed variance %
    direction: Literal["over", "under", "accurate"]
    sample_size: int
    worst_case_pct: str


class CalibrationReport(BaseModel):
    org_id: str
    window_days: int
    computed_at: datetime
    sample_size: int
    accuracy_score: str  # Decimal as string, 0-100
    metrics: List[CalibrationMetric]
    insights: List[str]
