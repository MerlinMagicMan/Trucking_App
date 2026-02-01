"""
Org-scoped API routes: orgs, trucks, routes library, plans history (Phase 2A)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.connection import get_db
from app.api.dependencies import get_org_id
from app.models.tenant import Organization, Truck, Route
from app.models.events import PlanGenerationEvent
from app.models.tenant_schemas import (
    OrgResponse,
    TruckResponse,
    CreateTruckRequest,
    RouteResponse,
    PlanHistoryItem,
    PlanHistoryDetail,
)

org_router = APIRouter()


# ---- Organizations (unscoped) ----

@org_router.get("/orgs", response_model=List[OrgResponse])
def list_orgs(db: Session = Depends(get_db)):
    """List all organizations."""
    return db.query(Organization).order_by(Organization.name).all()


# ---- Trucks (org-scoped) ----

@org_router.get("/trucks", response_model=List[TruckResponse])
def list_trucks(
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """List trucks for the active org."""
    return (
        db.query(Truck)
        .filter(Truck.org_id == org_id)
        .order_by(Truck.name)
        .all()
    )


@org_router.post("/trucks", response_model=TruckResponse, status_code=201)
def create_truck(
    body: CreateTruckRequest,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Create a new truck for the active org."""
    truck = Truck(
        org_id=org_id,
        name=body.name,
        equipment_type=body.equipment_type,
        home_base_city=body.home_base_city,
        home_base_state=body.home_base_state,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)
    return truck


# ---- Routes Library (org-scoped) ----

@org_router.get("/routes", response_model=List[RouteResponse])
def list_routes(
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
    pickup_state: Optional[str] = Query(None),
    delivery_state: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    """List routes for the active org with optional filters."""
    q = db.query(Route).filter(Route.org_id == org_id)
    if pickup_state:
        q = q.filter(Route.pickup_state == pickup_state.upper())
    if delivery_state:
        q = q.filter(Route.delivery_state == delivery_state.upper())
    if source:
        q = q.filter(Route.source == source)
    return q.order_by(Route.created_at.desc()).all()


@org_router.delete("/routes/{route_id}", status_code=204)
def delete_route(
    route_id: str,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Delete a route (must belong to the active org)."""
    route = db.query(Route).filter(Route.id == route_id, Route.org_id == org_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    db.delete(route)
    db.commit()
    return None


# ---- Plans History (org-scoped) ----

@org_router.get("/plans/history", response_model=List[PlanHistoryItem])
def list_plan_history(
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """List plan generation events for the active org (newest first)."""
    return (
        db.query(PlanGenerationEvent)
        .filter(PlanGenerationEvent.org_id == org_id)
        .order_by(PlanGenerationEvent.timestamp.desc())
        .limit(100)
        .all()
    )


@org_router.get("/plans/history/{event_id}", response_model=PlanHistoryDetail)
def get_plan_history_detail(
    event_id: int,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Get full payload for a plan generation event (read-only replay)."""
    event = (
        db.query(PlanGenerationEvent)
        .filter(PlanGenerationEvent.id == event_id, PlanGenerationEvent.org_id == org_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Plan history event not found")
    return event
