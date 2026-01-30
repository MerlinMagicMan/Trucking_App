"""
Tests for Economics Engine
Verifies cost calculations and financial integrity
"""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.engine.economics import EconomicsEngine
from app.models.plan import Plan, LoadInPlan, TimeBlock, FinancialEvent
from app.models.canonical import CanonicalLoad, PickupDeliveryLocation, TruckSnapshot, HOSSnapshot


@pytest.fixture
def economics_engine():
    """Create an Economics Engine instance"""
    return EconomicsEngine()


@pytest.fixture
def sample_load():
    """Create a sample CanonicalLoad"""
    return CanonicalLoad(
        id="test_load_001",
        source="truckstop",
        external_id="TS001",
        posted_at=datetime.now(timezone.utc),
        equipment="reefer",
        pickup=PickupDeliveryLocation(
            city="Oklahoma City",
            state="OK",
            lat=35.4676,
            lng=-97.5164,
            window_start=datetime.now(timezone.utc) + timedelta(hours=2),
            window_end=datetime.now(timezone.utc) + timedelta(hours=6)
        ),
        delivery=PickupDeliveryLocation(
            city="Dallas",
            state="TX",
            lat=32.7767,
            lng=-96.7970,
            window_start=datetime.now(timezone.utc) + timedelta(hours=8),
            window_end=datetime.now(timezone.utc) + timedelta(hours=12)
        ),
        rate_total=1200.00,
        miles=205.0
    )


@pytest.fixture
def sample_plan(sample_load):
    """Create a sample Plan with one load"""
    now = datetime.now(timezone.utc)

    truck_snapshot = TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=660,
            on_duty_remaining_min=840,
            cycle_remaining_min=4200
        )
    )

    # Create time blocks for the load
    time_blocks = [
        TimeBlock(
            start_time=now,
            end_time=now + timedelta(hours=4),
            duration_min=240,
            block_type="drive_loaded",
            location_lat=35.4676,
            location_lng=-97.5164,
            location_name="Oklahoma City, OK → Dallas, TX",
            related_load_id=sample_load.id
        ),
        TimeBlock(
            start_time=now + timedelta(hours=4),
            end_time=now + timedelta(hours=5.5),
            duration_min=90,
            block_type="unloading",
            location_lat=32.7767,
            location_lng=-96.7970,
            location_name="Dallas, TX",
            related_load_id=sample_load.id
        )
    ]

    load_in_plan = LoadInPlan(
        load=sample_load,
        sequence_number=1,
        deadhead_miles=0.0,  # Already at pickup
        revenue_usd=sample_load.rate_total,
        estimated_fuel_cost_usd=0.0,  # Will be calculated
        estimated_toll_cost_usd=0.0,  # Will be calculated
        net_revenue_usd=0.0,  # Will be calculated
        time_blocks=time_blocks
    )

    plan = Plan(
        truck_snapshot=truck_snapshot,
        planning_horizon_days=7,
        loads=[load_in_plan],
        time_blocks=time_blocks,
        end_location_lat=32.7767,
        end_location_lng=-96.7970,
        end_location_name="Dallas, TX",
        total_revenue_usd=0.0,  # Will be calculated
        total_costs_usd=0.0,  # Will be calculated
        net_profit_usd=0.0,  # Will be calculated
        profit_per_day_usd=0.0,  # Will be calculated
        financial_events=[],  # Will be populated
        plan_score=85.0,
        confidence="high",
        explanations=[
            "Short deadhead to pickup",
            "Delivers into Dallas reefer hub",
            "Comfortable pickup window"
        ],
        loads_analyzed=25,
        plans_generated=3
    )

    return plan


def test_fuel_cost_calculation(economics_engine, sample_plan):
    """Test fuel cost calculation"""
    plan = economics_engine.calculate_full_economics(sample_plan)

    # Find fuel cost event
    fuel_events = [e for e in plan.financial_events if e.event_type == "fuel_cost"]
    assert len(fuel_events) == 1

    fuel_event = fuel_events[0]
    expected_cost = 205.0 * 0.85  # miles × cost_per_mile
    assert fuel_event.amount_usd == pytest.approx(-expected_cost, rel=0.01)
    assert "calculation_details" in fuel_event.model_dump()


def test_toll_cost_for_toll_states(economics_engine, sample_plan):
    """Test toll cost when crossing toll states"""
    plan = economics_engine.calculate_full_economics(sample_plan)

    # TX is a toll state
    toll_events = [e for e in plan.financial_events if e.event_type == "toll_cost"]
    assert len(toll_events) == 1

    toll_event = toll_events[0]
    expected_cost = 205.0 * 0.12  # miles × toll_cost_per_mile
    assert toll_event.amount_usd == pytest.approx(-expected_cost, rel=0.01)


def test_no_toll_cost_for_non_toll_states(economics_engine, sample_load):
    """Test no toll cost when not crossing toll states"""
    # Change both pickup and delivery to non-toll states
    sample_load.pickup.state = "ND"  # North Dakota has no tolls
    sample_load.delivery.state = "MT"  # Montana has no tolls

    # Create simple plan with this load
    now = datetime.now(timezone.utc)
    truck_snapshot = TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(drive_remaining_min=660, on_duty_remaining_min=840, cycle_remaining_min=4200)
    )

    time_blocks = [TimeBlock(
        start_time=now,
        end_time=now + timedelta(hours=4),
        duration_min=240,
        block_type="drive_loaded",
        location_lat=35.4676,
        location_lng=-97.5164
    )]

    load_in_plan = LoadInPlan(
        load=sample_load,
        sequence_number=1,
        deadhead_miles=0.0,
        revenue_usd=sample_load.rate_total,
        estimated_fuel_cost_usd=0.0,
        estimated_toll_cost_usd=0.0,
        net_revenue_usd=0.0,
        time_blocks=time_blocks
    )

    plan = Plan(
        truck_snapshot=truck_snapshot,
        planning_horizon_days=7,
        loads=[load_in_plan],
        time_blocks=time_blocks,
        end_location_lat=32.7767,
        end_location_lng=-96.7970,
        end_location_name="Fargo, ND",
        total_revenue_usd=0.0,
        total_costs_usd=0.0,
        net_profit_usd=0.0,
        profit_per_day_usd=0.0,
        financial_events=[],
        plan_score=75.0,
        confidence="medium",
        explanations=["Test", "Plan", "Explanations"],
        loads_analyzed=10,
        plans_generated=2
    )

    plan = economics_engine.calculate_full_economics(plan)

    # Should have no toll events
    toll_events = [e for e in plan.financial_events if e.event_type == "toll_cost"]
    assert len(toll_events) == 0


def test_financial_events_sum_to_net_profit(economics_engine, sample_plan):
    """Test that all financial events sum correctly to net profit"""
    plan = economics_engine.calculate_full_economics(sample_plan)

    # Sum all financial events
    total_from_events = sum(event.amount_usd for event in plan.financial_events)

    # Should equal net profit
    assert total_from_events == pytest.approx(plan.net_profit_usd, rel=0.01)


def test_profit_per_day_calculation(economics_engine, sample_plan):
    """Test profit_per_day = net_profit / planning_horizon_days"""
    plan = economics_engine.calculate_full_economics(sample_plan)

    expected_profit_per_day = plan.net_profit_usd / plan.planning_horizon_days
    assert plan.profit_per_day_usd == pytest.approx(expected_profit_per_day, rel=0.01)


def test_opportunity_cost_for_idle_days(economics_engine, sample_plan):
    """Test opportunity cost when plan duration < horizon"""
    # Plan completes in ~5.5 hours but horizon is 7 days
    # Should have opportunity cost for ~6.8 idle days

    plan = economics_engine.calculate_full_economics(sample_plan)

    opp_events = [e for e in plan.financial_events if e.event_type == "opportunity_cost"]
    assert len(opp_events) == 1

    opp_event = opp_events[0]
    # Duration is < 1 day, so idle_days ≈ 6 days
    # Opportunity cost ≈ 6 × $500 = $3000
    assert opp_event.amount_usd < 0  # Cost is negative
    assert abs(opp_event.amount_usd) >= 2500  # At least 5 days × $500


def test_all_financial_events_have_calculation_details(economics_engine, sample_plan):
    """Test that all financial events include calculation_details for audit"""
    plan = economics_engine.calculate_full_economics(sample_plan)

    for event in plan.financial_events:
        assert event.calculation_details is not None
        assert isinstance(event.calculation_details, dict)
        assert len(event.calculation_details) > 0


def test_deterministic_economics(economics_engine, sample_plan):
    """Test that same plan produces same economic calculation"""
    plan1 = economics_engine.calculate_full_economics(sample_plan)
    plan2 = economics_engine.calculate_full_economics(sample_plan)

    assert plan1.net_profit_usd == plan2.net_profit_usd
    assert plan1.profit_per_day_usd == plan2.profit_per_day_usd
    assert plan1.total_revenue_usd == plan2.total_revenue_usd
    assert plan1.total_costs_usd == plan2.total_costs_usd


def test_revenue_is_positive(economics_engine, sample_plan):
    """Test that total revenue is always positive"""
    plan = economics_engine.calculate_full_economics(sample_plan)

    assert plan.total_revenue_usd > 0
    revenue_events = [e for e in plan.financial_events if e.event_type == "revenue"]
    for event in revenue_events:
        assert event.amount_usd > 0  # Revenue is positive


def test_costs_are_negative(economics_engine, sample_plan):
    """Test that all cost events are negative"""
    plan = economics_engine.calculate_full_economics(sample_plan)

    cost_types = ["fuel_cost", "toll_cost", "waiting_cost", "maintenance_reserve", "opportunity_cost"]
    for event in plan.financial_events:
        if event.event_type in cost_types:
            assert event.amount_usd < 0  # Costs are negative
