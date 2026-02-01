"""
Pydantic schemas for multi-tenant endpoints (Phase 2A)
"""
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    created_at: datetime


class CreateTruckRequest(BaseModel):
    name: str
    equipment_type: str = "reefer"
    home_base_city: Optional[str] = None
    home_base_state: Optional[str] = None


class TruckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    org_id: UUID
    name: str
    equipment_type: str
    home_base_city: Optional[str] = None
    home_base_state: Optional[str] = None
    created_at: datetime


class RouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    org_id: UUID
    source: str
    external_id: Optional[str] = None
    pickup_city: str
    pickup_state: str
    delivery_city: str
    delivery_state: str
    rate_total: float
    miles: Optional[float] = None
    posted_at: Optional[datetime] = None
    created_at: datetime


class PlanHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    snapshot_id: UUID
    planning_horizon_days: int
    plans_generated: int
    loads_analyzed: Optional[int] = None
    execution_time_ms: Optional[int] = None
    warnings: Optional[Any] = None


class PlanHistoryDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    snapshot_id: UUID
    planning_horizon_days: int
    plans_generated: int
    loads_analyzed: Optional[int] = None
    execution_time_ms: Optional[int] = None
    warnings: Optional[Any] = None
    full_payload: Any
