"""
Phase 0 canonical models for Plan-based decision system
Plans are the primary decision unit (not loads)
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.models.canonical import CanonicalLoad, TruckSnapshot


class TimeBlock(BaseModel):
    """
    A time-based segment within a plan
    Explicit modeling of drive, load, unload, wait, rest
    """
    start_time: datetime = Field(..., description="Block start time (UTC)")
    end_time: datetime = Field(..., description="Block end time (UTC)")
    duration_min: int = Field(..., ge=0, description="Duration in minutes")
    block_type: Literal[
        "drive_empty",      # Deadhead to pickup
        "drive_loaded",     # Loaded miles
        "loading",          # At pickup location
        "unloading",        # At delivery location
        "waiting",          # Waiting for appointment window
        "rest_break",       # HOS-mandated rest (10 hours)
        "available"         # Available for next load
    ] = Field(..., description="Type of time block")
    location_lat: Optional[float] = Field(None, ge=-90, le=90, description="Location latitude")
    location_lng: Optional[float] = Field(None, ge=-180, le=180, description="Location longitude")
    location_name: Optional[str] = Field(None, description="Human-readable location (e.g., 'Dallas, TX')")
    related_load_id: Optional[str] = Field(None, description="Link to CanonicalLoad if applicable")
    notes: Optional[str] = Field(None, description="Additional context")


class FinancialEvent(BaseModel):
    """
    A financial transaction within a plan
    Every cost and revenue is explicitly modeled
    """
    timestamp: datetime = Field(..., description="When this event occurs (UTC)")
    event_type: Literal[
        "revenue",              # Load revenue
        "fuel_cost",            # Fuel expense
        "toll_cost",            # Toll expense
        "waiting_cost",         # Cost of waiting time
        "maintenance_reserve",  # Reserve for future maintenance
        "opportunity_cost"      # Cost of idle time
    ] = Field(..., description="Type of financial event")
    amount_usd: float = Field(..., description="Amount in USD (positive = revenue, negative = cost)")
    description: str = Field(..., description="Plain-English description")
    related_load_id: Optional[str] = Field(None, description="Link to load if applicable")
    calculation_details: Optional[dict] = Field(None, description="Formula/inputs for audit trail")


class MaintenanceEvent(BaseModel):
    """
    Scheduled maintenance checkpoints
    Predicts when truck needs service
    """
    timestamp: datetime = Field(..., description="When maintenance occurs (UTC)")
    odometer_miles: float = Field(..., ge=0, description="Odometer reading at this point")
    event_type: Literal[
        "scheduled",    # Known upcoming PM
        "predicted",    # Predicted based on mileage
        "due"           # Currently due
    ] = Field(..., description="Maintenance event type")
    description: str = Field(..., description="What maintenance is needed")
    estimated_cost_usd: Optional[float] = Field(None, ge=0, description="Estimated cost if known")
    estimated_downtime_hours: Optional[float] = Field(None, ge=0, description="Estimated downtime if known")


class RiskSignal(BaseModel):
    """
    Risk indicators within a plan
    Surfaces potential issues for driver awareness
    """
    timestamp: datetime = Field(..., description="When this risk occurs (UTC)")
    risk_type: Literal[
        "hos_tight",            # HOS margin is low
        "weather",              # Weather-related risk
        "market_weak",          # Weak reload market at delivery
        "appointment_tight",    # Tight delivery window
        "deadhead_high"         # High empty miles
    ] = Field(..., description="Type of risk")
    severity: Literal["low", "medium", "high"] = Field(..., description="Risk severity")
    description: str = Field(..., description="Plain-English explanation of risk")
    impact_score: int = Field(..., ge=0, le=100, description="Impact score (0-100)")


class LoadInPlan(BaseModel):
    """
    A load within a plan, with contextual metadata
    Enriches CanonicalLoad with plan-specific information
    """
    load: CanonicalLoad = Field(..., description="The canonical load")
    sequence_number: int = Field(..., ge=1, le=3, description="Position in plan (1, 2, or 3)")
    deadhead_miles: float = Field(..., ge=0, description="Empty miles to pickup")
    revenue_usd: float = Field(..., gt=0, description="Gross revenue from load")
    estimated_fuel_cost_usd: float = Field(..., ge=0, description="Estimated fuel cost")
    estimated_toll_cost_usd: float = Field(..., ge=0, description="Estimated toll cost")
    net_revenue_usd: float = Field(..., description="Revenue minus direct costs")
    time_blocks: List[TimeBlock] = Field(..., min_length=1, description="TimeBlocks for this load")


class Plan(BaseModel):
    """
    Complete multi-day, multi-load plan
    PRIMARY DECISION UNIT for Phase 0

    Plans answer: "If I execute this strategy, what happens to my time and money?"
    """
    # Identity
    plan_id: UUID = Field(default_factory=uuid4, description="Unique plan identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When plan was generated (UTC)"
    )

    # Context
    truck_snapshot: TruckSnapshot = Field(..., description="Truck state at plan generation")
    planning_horizon_days: int = Field(..., ge=7, le=14, description="Planning horizon (7-14 days)")

    # Load sequence (1-3 loads; production plans typically have 2-3)
    loads: List[LoadInPlan] = Field(..., min_length=1, max_length=3, description="Chained loads (1-3)")

    # Timeline (complete chronological sequence)
    time_blocks: List[TimeBlock] = Field(..., min_length=1, description="Complete timeline")
    end_location_lat: float = Field(..., ge=-90, le=90, description="Final delivery latitude")
    end_location_lng: float = Field(..., ge=-180, le=180, description="Final delivery longitude")
    end_location_name: str = Field(..., description="Final delivery location name")

    # Financial summary (KEY METRICS)
    total_revenue_usd: float = Field(..., ge=0, description="Total revenue from all loads")
    total_costs_usd: float = Field(..., ge=0, description="Total costs (fuel, tolls, waiting, etc.)")
    net_profit_usd: float = Field(..., description="Net profit (revenue - costs)")
    profit_per_day_usd: float = Field(..., description="Net profit / planning_horizon_days (KEY METRIC)")
    financial_events: List[FinancialEvent] = Field(default_factory=list, description="All financial transactions")

    # Risk & maintenance
    risk_signals: List[RiskSignal] = Field(default_factory=list, description="Identified risks")
    maintenance_events: List[MaintenanceEvent] = Field(default_factory=list, description="Maintenance checkpoints")

    # Scoring
    plan_score: float = Field(..., ge=0, le=100, description="Overall plan quality (0-100)")
    confidence: Literal["low", "medium", "high"] = Field(..., description="Confidence level")

    # Explanations (why this plan?)
    explanations: List[str] = Field(..., min_length=3, description="At least 3 plain-English reasons")
    warnings: List[str] = Field(default_factory=list, description="Warnings or caveats")

    # Metadata
    loads_analyzed: int = Field(..., ge=0, description="Total loads analyzed")
    plans_generated: int = Field(..., ge=1, description="Total plans generated in this request")

    # Calibration (Stratum 5B) — optional, attached during plan generation
    estimates_raw: Optional[dict] = Field(None, description="Raw predicted estimates (Decimal strings)")
    estimates_calibrated: Optional[dict] = Field(None, description="Calibrated estimates or null")
    calibration_meta: Optional[dict] = Field(None, description="Calibration metadata and explanations")


class GeneratePlansResponse(BaseModel):
    """
    Response from POST /api/plans/generate
    Returns 0-3 alternative plans for comparison
    """
    snapshot_id: UUID = Field(..., description="Unique identifier for this optimization request")
    plans: List[Plan] = Field(default_factory=list, max_length=3, description="0-3 alternative plans (0 if no feasible plans)")
    warnings: List[str] = Field(default_factory=list, description="System-level warnings")
    metadata: dict = Field(default_factory=dict, description="Additional context")

    # Validation: plans must be sorted by profit_per_day descending
    def __init__(self, **data):
        super().__init__(**data)
        # Verify plans are sorted correctly (only if there are plans)
        if len(self.plans) > 1:
            for i in range(len(self.plans) - 1):
                if self.plans[i].profit_per_day_usd < self.plans[i+1].profit_per_day_usd:
                    raise ValueError("Plans must be sorted by profit_per_day descending")
