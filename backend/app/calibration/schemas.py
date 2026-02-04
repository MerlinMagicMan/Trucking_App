"""
Calibration schemas — Stratum 5B

Pydantic models for calibration profiles and calibrated plan estimates.
All money as Decimal strings — no floats cross the wire.
"""
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime


class CalibrationProfile(BaseModel):
    """Per-org, windowed calibration profile derived from completed outcomes."""
    org_id: str
    window_days: int
    sample_size: int
    bias_pct_by_metric: Dict[str, str]       # metric -> Decimal string (e.g. "6.80")
    volatility_pct_by_metric: Dict[str, str]  # metric -> Decimal string
    confidence: str                            # Decimal string 0-1
    generated_at: datetime


class PlanEstimates(BaseModel):
    """Top-line plan estimates (raw or calibrated). Money as Decimal strings."""
    revenue: str
    costs: str
    net_profit: str
    miles: str
    duration_min: str
    profit_per_day: str


class CalibrationAppliedMeta(BaseModel):
    """Metadata explaining what calibration was applied and why."""
    applied: bool
    window_days: Optional[int] = None
    sample_size: Optional[int] = None
    confidence: Optional[str] = None
    bias_pct_by_metric: Optional[Dict[str, str]] = None
    caps_applied: Optional[List[str]] = None
    explanation: List[str] = []
