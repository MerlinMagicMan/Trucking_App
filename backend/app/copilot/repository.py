"""
Copilot repository — plan retrieval + load availability checks (Phase 4)
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.events import PlanGenerationEvent
from app.models.snapshot import LoadSnapshot


def find_plan_by_id(
    db: Session,
    org_id: str,
    plan_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Search PlanGenerationEvent full_payload for a plan matching plan_id.
    Returns the plan dict or None.
    """
    events = (
        db.query(PlanGenerationEvent)
        .filter(PlanGenerationEvent.org_id == org_id)
        .order_by(PlanGenerationEvent.timestamp.desc())
        .limit(200)
        .all()
    )

    for event in events:
        payload = event.full_payload
        if not payload or "plans" not in payload:
            continue
        for plan in payload["plans"]:
            if plan.get("plan_id") == plan_id:
                return plan

    return None


def check_load_active(
    db: Session,
    org_id: str,
    source: str,
    external_id: str,
) -> bool:
    """Check if a load snapshot is still active."""
    row = (
        db.query(LoadSnapshot.id)
        .filter(
            LoadSnapshot.org_id == org_id,
            LoadSnapshot.source == source,
            LoadSnapshot.external_id == external_id,
            LoadSnapshot.status == "active",
        )
        .first()
    )
    return row is not None
