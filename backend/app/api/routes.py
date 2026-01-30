"""
API routes for optimization endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from app.models.canonical import TruckSnapshot, OptimizeResponse
from app.models.plan import GeneratePlansResponse
from app.models.events import RecommendationEvent, PlanGenerationEvent
from app.db.connection import get_db
from app.engine.optimizer import OptimizationEngine
from app.engine.plan_generator import PlanGenerator
from app.engine.economics import EconomicsEngine
from app.connectors.truckstop import TruckstopConnector
from app.connectors.dat import DatConnector

router = APIRouter()

# Initialize connectors
truckstop_connector = TruckstopConnector()
dat_connector = DatConnector()

# Initialize optimization engine
optimization_engine = OptimizationEngine(
    connectors=[truckstop_connector, dat_connector]
)

# Initialize economics engine and plan generator (Phase 0)
economics_engine = EconomicsEngine()
plan_generator = PlanGenerator(optimization_engine, economics_engine)


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_route(
    snapshot: TruckSnapshot,
    radius_miles: int = 250,
    db: Session = Depends(get_db)
):
    """
    Main optimization endpoint
    Returns top 3 HOS-feasible loads with reload scores and explanations

    **This is the core decision-support endpoint.**
    """
    try:
        # Run optimization
        result = optimization_engine.optimize(snapshot, radius_miles=radius_miles)

        # Create audit log event
        input_load_ids = []
        output_top3 = []

        for rec in result.recommendations:
            output_top3.append({
                "loadId": rec.load_id,
                "score": rec.reload_score,
                "confidence": rec.confidence,
                "rank": rec.rank
            })

        # Full payload for replay/debug
        full_payload = {
            "request": {
                "snapshot_id": str(snapshot.snapshot_id),
                "timestamp": snapshot.timestamp.isoformat(),
                "current_lat": snapshot.current_lat,
                "current_lng": snapshot.current_lng,
                "hos": {
                    "drive_remaining_min": snapshot.hos.drive_remaining_min,
                    "on_duty_remaining_min": snapshot.hos.on_duty_remaining_min,
                    "cycle_remaining_min": snapshot.hos.cycle_remaining_min
                },
                "radius_miles": radius_miles
            },
            "response": {
                "snapshot_id": str(result.snapshot_id),
                "recommendations_count": len(result.recommendations),
                "recommendations": [
                    {
                        "load_id": rec.load_id,
                        "rank": rec.rank,
                        "reload_score": rec.reload_score,
                        "confidence": rec.confidence,
                        "deadhead_miles": rec.deadhead_miles,
                        "explanations": rec.explanations
                    }
                    for rec in result.recommendations
                ],
                "loads_analyzed": result.loads_analyzed,
                "loads_feasible": result.loads_feasible,
                "warnings": result.warnings
            }
        }

        # Write audit log
        event = RecommendationEvent(
            timestamp=datetime.utcnow(),
            snapshot_id=snapshot.snapshot_id,
            connector="truckstop",  # Primary connector for MVP
            query_params={"radius_miles": radius_miles},
            input_load_ids=input_load_ids,
            output_top3=output_top3,
            full_payload=full_payload,
            loads_analyzed=result.loads_analyzed,
            loads_feasible=result.loads_feasible,
            warnings=result.warnings
        )

        db.add(event)
        db.commit()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/plans/generate", response_model=GeneratePlansResponse)
async def generate_plans(
    snapshot: TruckSnapshot,
    planning_horizon_days: int = 7,
    max_plans: int = 3,
    radius_miles: int = 250,
    db: Session = Depends(get_db)
):
    """
    **Phase 0: Plan Generation Endpoint**

    Generates 2-3 strategically different multi-load plans (7-14 day horizons)

    Plans are the primary decision unit - complete multi-day strategies with:
    - 2-3 chained loads
    - Full timeline (TimeBlocks)
    - Complete financial model (revenue, costs, profit_per_day)
    - Risk assessment (RiskSignals)
    - Plain-English explanations

    **Key metric**: profit_per_day_usd (not just reload_score)

    Args:
        snapshot: Current truck state (location, HOS)
        planning_horizon_days: Planning horizon (7-14 days, default 7)
        max_plans: Maximum plans to return (default 3)
        radius_miles: Search radius for loads (default 250)

    Returns:
        GeneratePlansResponse with 2-3 alternative plans sorted by profit_per_day
    """
    try:
        # Validate inputs
        if planning_horizon_days < 7 or planning_horizon_days > 14:
            raise HTTPException(
                status_code=400,
                detail="planning_horizon_days must be between 7 and 14"
            )

        if max_plans < 1 or max_plans > 3:
            raise HTTPException(
                status_code=400,
                detail="max_plans must be between 1 and 3"
            )

        # Generate plans
        plans = plan_generator.generate_plans(
            snapshot,
            planning_horizon_days=planning_horizon_days,
            max_plans=max_plans,
            radius_miles=radius_miles
        )

        # Build warnings
        warnings = []
        if len(plans) == 0:
            warnings.append("No feasible multi-load plans found. Try increasing radius or checking HOS limits.")

        # Build response
        response = GeneratePlansResponse(
            snapshot_id=snapshot.snapshot_id,
            plans=plans,
            warnings=warnings,
            metadata={
                "planning_horizon_days": planning_horizon_days,
                "radius_miles": radius_miles,
                "plans_requested": max_plans,
                "plans_generated": len(plans)
            }
        )

        # Build full payload for audit log
        full_payload = {
            "request": {
                "snapshot_id": str(snapshot.snapshot_id),
                "timestamp": snapshot.timestamp.isoformat(),
                "current_lat": snapshot.current_lat,
                "current_lng": snapshot.current_lng,
                "hos": {
                    "drive_remaining_min": snapshot.hos.drive_remaining_min,
                    "on_duty_remaining_min": snapshot.hos.on_duty_remaining_min,
                    "cycle_remaining_min": snapshot.hos.cycle_remaining_min
                },
                "planning_horizon_days": planning_horizon_days,
                "max_plans": max_plans,
                "radius_miles": radius_miles
            },
            "response": {
                "snapshot_id": str(response.snapshot_id),
                "plans_generated": len(plans),
                "plans": [
                    {
                        "plan_id": str(plan.plan_id),
                        "num_loads": len(plan.loads),
                        "profit_per_day_usd": plan.profit_per_day_usd,
                        "net_profit_usd": plan.net_profit_usd,
                        "total_revenue_usd": plan.total_revenue_usd,
                        "total_costs_usd": plan.total_costs_usd,
                        "end_location": plan.end_location_name,
                        "confidence": plan.confidence,
                        "plan_score": plan.plan_score,
                        "load_ids": [load.load.id for load in plan.loads]
                    }
                    for plan in plans
                ],
                "warnings": response.warnings
            }
        }

        # Write audit log
        event = PlanGenerationEvent(
            timestamp=datetime.utcnow(),
            snapshot_id=snapshot.snapshot_id,
            planning_horizon_days=planning_horizon_days,
            plans_generated=len(plans),
            full_payload=full_payload
        )

        db.add(event)
        db.commit()

        return response

    except HTTPException:
        raise  # Re-raise validation errors
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {str(e)}")


@router.get("/health")
async def health_check():
    """
    API health check
    Returns service status
    """
    return {
        "status": "ok",
        "service": "Single-Truck Optimization API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/connectors/health")
async def connectors_health():
    """
    Check health of all load board connectors
    Returns status for each connector
    """
    connectors = [
        truckstop_connector,
        dat_connector
    ]

    health_results = []
    overall_status = "ok"

    for connector in connectors:
        try:
            health = connector.health_check()
            health_results.append(health)

            if health.get("status") != "ok" and health.get("status") != "stub":
                overall_status = "degraded"
        except Exception as e:
            health_results.append({
                "connector": connector.name,
                "status": "error",
                "message": str(e)
            })
            overall_status = "degraded"

    return {
        "overall_status": overall_status,
        "connectors": health_results,
        "timestamp": datetime.utcnow().isoformat()
    }
