"""
Canonical data models for the optimization engine
All connectors must normalize their data into these models
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime, timezone
from uuid import UUID, uuid4


class PickupDeliveryLocation(BaseModel):
    """Location with time window for pickup or delivery"""
    city: str
    state: str
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")
    window_start: Optional[datetime] = Field(None, description="Start of time window")
    window_end: Optional[datetime] = Field(None, description="End of time window")


class CanonicalLoad(BaseModel):
    """
    Canonical load representation
    All loads from any connector must be normalized to this format
    """
    id: str = Field(..., description="Internal unique identifier")
    source: str = Field(..., description="Connector source (truckstop, dat, etc)")
    external_id: str = Field(..., description="Original ID from source system")
    posted_at: datetime = Field(..., description="When load was posted")
    equipment: Literal["reefer"] = Field(default="reefer", description="Equipment type (always reefer for MVP)")
    pickup: PickupDeliveryLocation = Field(..., description="Pickup location and window")
    delivery: PickupDeliveryLocation = Field(..., description="Delivery location and window")
    rate_total: float = Field(..., gt=0, description="Total rate in USD")
    miles: Optional[float] = Field(None, ge=0, description="Loaded miles")
    notes: Optional[str] = Field(None, description="Additional notes")

    @field_validator('equipment')
    @classmethod
    def validate_equipment(cls, v):
        if v != "reefer":
            raise ValueError("Only reefer equipment is supported in MVP")
        return v


class HOSSnapshot(BaseModel):
    """Hours of Service remaining"""
    drive_remaining_min: int = Field(..., ge=0, le=660, description="Drive time remaining (minutes, max 11 hours)")
    on_duty_remaining_min: int = Field(..., ge=0, le=840, description="On-duty time remaining (minutes, max 14 hours)")
    cycle_remaining_min: int = Field(..., ge=0, le=4200, description="70-hour cycle remaining (minutes, max 70 hours)")


class TruckSnapshot(BaseModel):
    """
    Current truck state snapshot
    Immutable point-in-time representation
    """
    snapshot_id: UUID = Field(default_factory=uuid4, description="Unique snapshot identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When snapshot was taken")
    current_lat: float = Field(..., ge=-90, le=90, description="Current truck latitude")
    current_lng: float = Field(..., ge=-180, le=180, description="Current truck longitude")
    hos: HOSSnapshot = Field(..., description="Hours of Service remaining")


class Recommendation(BaseModel):
    """
    Single load recommendation with scoring and explanations
    """
    load_id: str = Field(..., description="ID of the recommended load")
    rank: Literal[1, 2, 3] = Field(..., description="Ranking (1=best, 2=second, 3=third)")
    hos_feasible: bool = Field(..., description="Whether load is HOS-feasible")
    arrival_at_pickup: datetime = Field(..., description="Estimated arrival at pickup")
    arrival_at_delivery: datetime = Field(..., description="Estimated arrival at delivery")
    reload_score: float = Field(..., ge=0, le=100, description="Reload probability score (0-100)")
    confidence: Literal["low", "medium", "high"] = Field(..., description="Confidence level")
    explanations: List[str] = Field(..., min_length=3, description="At least 3 plain-English reasons")

    # Additional context for display
    deadhead_miles: Optional[float] = Field(None, ge=0, description="Empty miles to pickup")
    total_miles: Optional[float] = Field(None, ge=0, description="Total trip miles")
    estimated_total_time_min: Optional[int] = Field(None, ge=0, description="Total time including loading")

    # Phase 0: Delivery location for plan chaining
    delivery_lat: Optional[float] = Field(None, ge=-90, le=90, description="Delivery latitude (for plan chaining)")
    delivery_lng: Optional[float] = Field(None, ge=-180, le=180, description="Delivery longitude (for plan chaining)")

    @field_validator('reload_score')
    @classmethod
    def validate_reload_score(cls, v):
        if not (0 <= v <= 100):
            raise ValueError("reload_score must be between 0 and 100")
        return v

    @field_validator('explanations')
    @classmethod
    def validate_explanations(cls, v):
        if len(v) < 3:
            raise ValueError("At least 3 explanations are required")
        return v


class TimelineEvent(BaseModel):
    """Single event in the forward-look timeline"""
    timestamp: datetime
    event_type: Literal["current", "arrive_pickup", "depart_pickup", "arrive_delivery", "available_reload"]
    description: str
    location: Optional[str] = None


class ForwardLook(BaseModel):
    """
    Simple 24-48 hour forward-looking timeline
    Shows what happens after taking the recommended load
    """
    horizon_hours: int = Field(default=48, description="Timeline horizon in hours")
    events: List[TimelineEvent] = Field(default_factory=list, description="Timeline events")
    reload_market_assessment: Optional[str] = Field(None, description="Brief market outlook at delivery")


class OptimizeResponse(BaseModel):
    """
    Response from POST /api/optimize
    """
    snapshot_id: UUID = Field(..., description="Unique identifier for this optimization request")
    recommendations: List[Recommendation] = Field(..., description="Top 3 (or fewer) recommendations")
    forward_look: Optional[ForwardLook] = Field(None, description="Timeline projection")
    warnings: List[str] = Field(default_factory=list, description="Warnings or constraints")
    loads_analyzed: int = Field(..., ge=0, description="Total loads analyzed")
    loads_feasible: int = Field(..., ge=0, description="Loads that passed HOS check")

    @field_validator('recommendations')
    @classmethod
    def validate_recommendations(cls, v):
        if len(v) > 3:
            raise ValueError("Maximum 3 recommendations allowed")
        for rec in v:
            if not rec.hos_feasible:
                raise ValueError("Infeasible loads must never appear in recommendations")
        return v
