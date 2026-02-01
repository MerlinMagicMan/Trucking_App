"""
Ingestion admin endpoints (Phase 3A)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.connection import get_db
from app.api.dependencies import get_org_id
from app.models.snapshot import LoadSnapshot
from app.ingestion.scheduler import get_scheduler_status

ingestion_router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@ingestion_router.get("/status")
async def ingestion_status(
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """
    Ingestion pipeline status: scheduler state + snapshot counts.
    """
    scheduler = get_scheduler_status()

    active = db.query(func.count(LoadSnapshot.id)).filter(
        LoadSnapshot.org_id == org_id,
        LoadSnapshot.status == "active",
    ).scalar()

    expired = db.query(func.count(LoadSnapshot.id)).filter(
        LoadSnapshot.org_id == org_id,
        LoadSnapshot.status == "expired",
    ).scalar()

    total = db.query(func.count(LoadSnapshot.id)).filter(
        LoadSnapshot.org_id == org_id,
    ).scalar()

    return {
        "scheduler": scheduler,
        "snapshots": {
            "active": active,
            "expired": expired,
            "total": total,
        },
    }


@ingestion_router.get("/snapshots")
async def list_snapshots(
    status: str = "active",
    limit: int = 50,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """
    List load snapshots for this org.
    """
    q = (
        db.query(LoadSnapshot)
        .filter(LoadSnapshot.org_id == org_id, LoadSnapshot.status == status)
        .order_by(LoadSnapshot.ingested_at.desc())
        .limit(limit)
    )
    rows = q.all()
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "external_id": r.external_id,
            "status": r.status,
            "pickup": f"{r.pickup_city}, {r.pickup_state}",
            "delivery": f"{r.delivery_city}, {r.delivery_state}",
            "rate_total": r.rate_total,
            "miles": r.miles,
            "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
        }
        for r in rows
    ]
