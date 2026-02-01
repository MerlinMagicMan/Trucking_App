"""
Snapshot store — persistence layer for load_snapshots (Phase 3A)

Responsibilities:
- Upsert: insert new snapshots, update existing (raw_payload immutable)
- Expire: mark stale loads as expired
- Query: get active loads as CanonicalLoad objects for engine consumption
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from geopy.distance import geodesic

from app.models.snapshot import LoadSnapshot
from app.models.canonical import CanonicalLoad, PickupDeliveryLocation

logger = logging.getLogger(__name__)


def upsert_snapshot(
    db: Session,
    org_id: str,
    source: str,
    external_id: str,
    raw_payload: Dict[str, Any],
    canonical_dict: Dict[str, Any],
    posted_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
) -> None:
    """
    Insert or update a load snapshot.
    - New (source, external_id): insert with raw_payload + canonical
    - Existing: update ingested_at + canonical + denormalized fields (raw_payload immutable)
    """
    now = datetime.utcnow()

    # Extract denormalized fields from canonical
    pickup = canonical_dict.get("pickup", {})
    delivery = canonical_dict.get("delivery", {})

    values = dict(
        org_id=org_id,
        source=source,
        external_id=external_id,
        raw_payload=raw_payload,
        canonical=canonical_dict,
        ingested_at=now,
        status="active",
        posted_at=posted_at,
        expires_at=expires_at,
        equipment=canonical_dict.get("equipment"),
        pickup_city=pickup.get("city"),
        pickup_state=pickup.get("state"),
        delivery_city=delivery.get("city"),
        delivery_state=delivery.get("state"),
        pickup_lat=pickup.get("lat"),
        pickup_lng=pickup.get("lng"),
        delivery_lat=delivery.get("lat"),
        delivery_lng=delivery.get("lng"),
        rate_total=canonical_dict.get("rate_total"),
        miles=canonical_dict.get("miles"),
    )

    stmt = pg_insert(LoadSnapshot).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_source_external_id",
        set_={
            "ingested_at": now,
            "status": "active",
            "canonical": canonical_dict,
            # Denormalized fields update
            "rate_total": values["rate_total"],
            "miles": values["miles"],
            "pickup_city": values["pickup_city"],
            "pickup_state": values["pickup_state"],
            "delivery_city": values["delivery_city"],
            "delivery_state": values["delivery_state"],
            "pickup_lat": values["pickup_lat"],
            "pickup_lng": values["pickup_lng"],
            "delivery_lat": values["delivery_lat"],
            "delivery_lng": values["delivery_lng"],
            "equipment": values["equipment"],
            "expires_at": expires_at,
            # raw_payload NOT updated — immutable
        },
    )
    db.execute(stmt)


def expire_stale(
    db: Session,
    org_id: str,
    source: Optional[str] = None,
    older_than_minutes: int = 60,
) -> int:
    """
    Mark active loads as expired if not refreshed recently.
    Returns count of expired loads.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
    q = (
        db.query(LoadSnapshot)
        .filter(
            LoadSnapshot.org_id == org_id,
            LoadSnapshot.status == "active",
            LoadSnapshot.ingested_at < cutoff,
        )
    )
    if source:
        q = q.filter(LoadSnapshot.source == source)

    count = q.update({"status": "expired"})
    return count


def get_active_loads(
    db: Session,
    org_id: str,
    truck_lat: float,
    truck_lng: float,
    radius_miles: int = 250,
    equipment: str = "reefer",
) -> List[CanonicalLoad]:
    """
    Query active snapshots, filter by radius, return as CanonicalLoad objects.
    """
    snapshots = (
        db.query(LoadSnapshot)
        .filter(
            LoadSnapshot.org_id == org_id,
            LoadSnapshot.status == "active",
        )
        .all()
    )

    loads = []
    truck_pos = (truck_lat, truck_lng)

    for snap in snapshots:
        # Filter by radius using pickup location
        if snap.pickup_lat and snap.pickup_lng:
            pickup_pos = (snap.pickup_lat, snap.pickup_lng)
            try:
                dist = geodesic(truck_pos, pickup_pos).miles
                if dist > radius_miles:
                    continue
            except Exception:
                continue
        else:
            # No coords — skip
            continue

        # Deserialize canonical JSON → CanonicalLoad
        try:
            load = _canonical_from_dict(snap.canonical)
            loads.append(load)
        except Exception as e:
            logger.warning(f"Failed to deserialize snapshot {snap.id}: {e}")

    # Sort by (source, external_id) for determinism
    loads.sort(key=lambda x: (x.source, x.external_id))
    return loads


def _canonical_from_dict(d: Dict[str, Any]) -> CanonicalLoad:
    """Convert canonical JSON dict back to CanonicalLoad Pydantic model."""
    pickup_data = d.get("pickup", {})
    delivery_data = d.get("delivery", {})

    pickup = PickupDeliveryLocation(
        city=pickup_data.get("city", ""),
        state=pickup_data.get("state", ""),
        lat=pickup_data.get("lat", 0.0),
        lng=pickup_data.get("lng", 0.0),
        window_start=pickup_data.get("window_start"),
        window_end=pickup_data.get("window_end"),
    )
    delivery = PickupDeliveryLocation(
        city=delivery_data.get("city", ""),
        state=delivery_data.get("state", ""),
        lat=delivery_data.get("lat", 0.0),
        lng=delivery_data.get("lng", 0.0),
        window_start=delivery_data.get("window_start"),
        window_end=delivery_data.get("window_end"),
    )

    return CanonicalLoad(
        id=d.get("id", ""),
        source=d.get("source", ""),
        external_id=d.get("external_id", ""),
        posted_at=d.get("posted_at", datetime.utcnow().isoformat()),
        equipment=d.get("equipment", "reefer"),
        pickup=pickup,
        delivery=delivery,
        rate_total=d.get("rate_total", 0.0),
        miles=d.get("miles"),
        notes=d.get("notes"),
    )
