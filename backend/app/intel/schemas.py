"""
Response schemas for intelligence APIs (Phase 3C)

All responses include a meta block for lineage + replay support.
"""
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


class IntelMeta(BaseModel):
    """Standard metadata block on every intel response."""
    org_id: str
    window: str
    window_start: datetime
    window_end: datetime
    source: str
    computed_at: Optional[datetime] = None
    data_freshness_seconds: Optional[float] = None
    sample_size: Optional[int] = None


class LaneIntelResponse(BaseModel):
    meta: IntelMeta
    data: Optional[Dict[str, Any]] = None
    explanations: List[str] = []


class MarketIntelResponse(BaseModel):
    meta: IntelMeta
    data: Optional[Dict[str, Any]] = None
    explanations: List[str] = []


class DestinationIntelResponse(BaseModel):
    meta: IntelMeta
    data: Optional[Dict[str, Any]] = None
    explanations: List[str] = []


class NegotiationIntelResponse(BaseModel):
    meta: IntelMeta
    data: Optional[Dict[str, Any]] = None
    explanations: List[str] = []


class CorridorDestination(BaseModel):
    destination_geohash: str
    efficiency_score: Optional[float] = None
    reload_probability: Optional[float] = None
    avg_time_to_first_reload_minutes: Optional[float] = None
    market_temperature: Optional[str] = None
    active_load_count_avg: Optional[float] = None


class CorridorIntelResponse(BaseModel):
    meta: IntelMeta
    data: Optional[List[CorridorDestination]] = None
    explanations: List[str] = []


class TableHealth(BaseModel):
    table: str
    latest_computed_at: Optional[datetime] = None
    rows_last_24h: int = 0
    freshness_seconds: Optional[float] = None


class IntelHealthResponse(BaseModel):
    tables: List[TableHealth]
