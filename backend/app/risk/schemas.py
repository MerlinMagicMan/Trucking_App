"""
Risk Schemas — Stratum 5D: Learning Loop

Pydantic models for risk outcome reports and post-mortem analysis.
"""
from pydantic import BaseModel
from typing import Dict, List, Optional, Literal
from datetime import datetime


class WarningOutcomeCorrelation(BaseModel):
    """Maps a pre-decision warning to what actually happened."""
    warning_kind: str
    warning_severity: str
    warning_title: str
    warning_message: str

    # What actually happened
    outcome_verified: bool  # Did the warning prove accurate?
    outcome_variance_field: Optional[str] = None  # Which metric had variance
    outcome_variance_pct: Optional[str] = None  # Actual variance percentage

    # Assessment
    assessment: Literal["correct", "false_alarm", "partially_correct", "unverifiable"]
    assessment_explanation: str


class DecisionContextSummary(BaseModel):
    """Summary of what we knew at decision time."""
    captured_at: datetime

    # Trust at decision time
    trust_score: Optional[int] = None  # 0-100
    trust_label: Optional[str] = None  # high/medium/low/unknown
    trust_warning_count: int = 0

    # Copilot at decision time
    copilot_status: Optional[str] = None  # ok/degraded/unknown
    copilot_signal_count: int = 0
    copilot_high_severity_count: int = 0

    # Calibration at decision time
    calibration_sample_size: Optional[int] = None
    calibration_applied: Optional[str] = None  # yes/no/partial

    # Plan estimates at decision time
    plan_revenue: Optional[str] = None
    plan_costs: Optional[str] = None
    plan_net_profit: Optional[str] = None


class OutcomeActualSummary(BaseModel):
    """Summary of what actually happened."""
    status: str  # pending/partial/complete
    completed_at: Optional[datetime] = None

    actual_revenue: Optional[str] = None
    actual_costs: Optional[str] = None
    actual_net_profit: Optional[str] = None

    revenue_variance_pct: Optional[str] = None
    costs_variance_pct: Optional[str] = None
    profit_variance_pct: Optional[str] = None

    major_variance_fields: List[str] = []  # Fields with variance > 15%


class RiskOutcomeReport(BaseModel):
    """
    Full risk outcome report: what we knew vs what happened.

    Deterministically computed on read from:
      - DecisionContextSnapshot (what we knew)
      - PlanOutcome (what happened)
    """
    org_id: str
    plan_id: str
    computed_at: datetime

    # What we knew at decision time
    decision_context: Optional[DecisionContextSummary] = None
    pre_decision_warnings: List[Dict] = []  # Original RiskWarning dicts

    # What actually happened
    outcome_summary: Optional[OutcomeActualSummary] = None

    # How warnings correlated to outcomes
    warning_correlations: List[WarningOutcomeCorrelation] = []

    # Overall learning insights
    accuracy_assessment: Literal["accurate", "partially_accurate", "inaccurate", "insufficient_data"]
    accuracy_score: int  # 0-100: how well warnings predicted outcomes

    # Plain English explanations (≥3)
    explanations: List[str]

    # Meta
    has_decision_context: bool
    has_completed_outcome: bool


class RiskOutcomeReportMeta(BaseModel):
    """Metadata for risk outcome report."""
    decision_context_snapshot_id: Optional[str] = None
    prediction_snapshot_id: Optional[str] = None
    outcome_id: Optional[str] = None
    decision_event_id: Optional[int] = None
