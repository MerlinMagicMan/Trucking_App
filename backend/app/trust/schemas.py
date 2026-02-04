"""
Trust Layer schemas — Stratum 5C

Pydantic models for trust/confidence reporting.
"""
from pydantic import BaseModel
from typing import Dict, List, Literal, Optional
from datetime import datetime


ConfidenceLabel = Literal["high", "medium", "low", "unknown"]
WarningSeverity = Literal["low", "medium", "high"]

WarningKind = Literal[
    "low_sample_size",
    "low_confidence",
    "high_volatility",
    "metric_skipped_by_volatility",
    "large_calibration_adjustment",
    "offline_intel",
    "missing_intel_inputs",
    "long_horizon_uncertainty",
    "multi_load_complexity",
    "market_cold_risk",
    "lane_rate_instability",
    "destination_reload_risk",
    "load_unavailable",
]


class TrustMeta(BaseModel):
    org_id: str
    plan_id: str
    computed_at: datetime
    window_days: int
    offline: bool
    sample_size: int
    profile_confidence: str  # Decimal string 0-1
    volatility_pct: Dict[str, str]  # per metric
    used_calibrated: bool


class RiskWarning(BaseModel):
    kind: str  # WarningKind value
    severity: WarningSeverity
    title: str
    message: str
    suggested_action: Optional[str] = None
    details: Dict[str, object] = {}


class PlanTrustReport(BaseModel):
    confidence_score: int  # 0-100
    confidence_label: ConfidenceLabel
    warnings: List[RiskWarning]
    explanations: List[str]
    meta: TrustMeta
