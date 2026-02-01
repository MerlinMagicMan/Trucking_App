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
