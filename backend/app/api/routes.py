"""
API routes for optimization endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel
from app.models.canonical import TruckSnapshot, OptimizeResponse, CanonicalLoad, PickupDeliveryLocation
from app.api.dependencies import get_org_id
from app.models.tenant import Route
from app.models.plan import GeneratePlansResponse
from app.models.events import RecommendationEvent, PlanGenerationEvent
from app.db.connection import get_db
from app.engine.optimizer import OptimizationEngine
from app.engine.plan_generator import PlanGenerator
from app.engine.economics import EconomicsEngine
from app.connectors.truckstop import TruckstopConnector
from app.connectors.dat import DatConnector
from app.ingestion.snapshot_store import get_active_loads
from app.models.snapshot import LoadSnapshot

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
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """
    Main optimization endpoint
    Returns top 3 HOS-feasible loads with reload scores and explanations

    **This is the core decision-support endpoint.**
    """
    try:
        # Check if snapshots exist for this org; if so, use them
        snapshot_count = db.query(LoadSnapshot).filter(
            LoadSnapshot.org_id == org_id,
            LoadSnapshot.status == "active",
        ).count()

        preloaded = None
        if snapshot_count > 0:
            preloaded = get_active_loads(
                db, org_id,
                truck_lat=snapshot.current_lat,
                truck_lng=snapshot.current_lng,
                radius_miles=radius_miles,
            )

        # Run optimization
        result = optimization_engine.optimize(snapshot, radius_miles=radius_miles, preloaded=preloaded)

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
            warnings=result.warnings,
            org_id=org_id,
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
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
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

        # Check if snapshots exist for this org; if so, use them
        snap_count = db.query(LoadSnapshot).filter(
            LoadSnapshot.org_id == org_id,
            LoadSnapshot.status == "active",
        ).count()

        plan_preloaded = None
        if snap_count > 0:
            plan_preloaded = get_active_loads(
                db, org_id,
                truck_lat=snapshot.current_lat,
                truck_lng=snapshot.current_lng,
                radius_miles=radius_miles,
            )

        # Generate plans
        plans = plan_generator.generate_plans(
            snapshot,
            planning_horizon_days=planning_horizon_days,
            max_plans=max_plans,
            radius_miles=radius_miles,
            preloaded=plan_preloaded,
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
            full_payload=full_payload,
            org_id=org_id,
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


# ---- CSV Route Import (Phase 1.5) ----

class CsvRouteRow(BaseModel):
    pickup_city: str
    pickup_state: str
    delivery_city: str
    delivery_state: str
    miles: str
    rate_total: str
    route_name: Optional[str] = None
    pickup_date: Optional[str] = None
    delivery_date: Optional[str] = None

class CsvImportRequest(BaseModel):
    routes: List[CsvRouteRow]

class CsvImportResponse(BaseModel):
    imported: int
    loads: List[CanonicalLoad]


@router.post("/routes/import", response_model=CsvImportResponse)
async def import_routes(
    request: CsvImportRequest,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """
    Import CSV routes as CanonicalLoad objects and persist to DB.
    Requires X-Org-Id header.
    """
    loads: List[CanonicalLoad] = []

    for row in request.routes:
        try:
            miles_val = float(row.miles) if row.miles else None
            rate_val = float(row.rate_total) if row.rate_total else 0.0
        except ValueError:
            continue  # skip malformed rows

        pickup_time = None
        delivery_time = None
        if row.pickup_date:
            try:
                pickup_time = datetime.fromisoformat(row.pickup_date)
            except ValueError:
                pass
        if row.delivery_date:
            try:
                delivery_time = datetime.fromisoformat(row.delivery_date)
            except ValueError:
                pass

        load_id = str(uuid.uuid4())
        ext_id = f"csv-{uuid.uuid4().hex[:8]}"

        # Persist to routes table
        route_row = Route(
            id=load_id,
            org_id=org_id,
            source="user_uploaded",
            external_id=ext_id,
            pickup_city=row.pickup_city,
            pickup_state=row.pickup_state,
            delivery_city=row.delivery_city,
            delivery_state=row.delivery_state,
            rate_total=rate_val,
            miles=miles_val,
            posted_at=pickup_time or datetime.utcnow(),
        )
        db.add(route_row)

        # Build CanonicalLoad for response
        load = CanonicalLoad(
            id=load_id,
            source="user_uploaded",
            external_id=ext_id,
            posted_at=datetime.utcnow(),
            equipment="reefer",
            pickup=PickupDeliveryLocation(
                city=row.pickup_city,
                state=row.pickup_state,
                lat=0.0,
                lng=0.0,
                window_start=pickup_time,
                window_end=pickup_time,
            ),
            delivery=PickupDeliveryLocation(
                city=row.delivery_city,
                state=row.delivery_state,
                lat=0.0,
                lng=0.0,
                window_start=delivery_time,
                window_end=delivery_time,
            ),
            rate_total=rate_val,
            miles=miles_val,
            notes=row.route_name or f"{row.pickup_city} → {row.delivery_city}",
        )
        loads.append(load)

    db.commit()
    return CsvImportResponse(imported=len(loads), loads=loads)
