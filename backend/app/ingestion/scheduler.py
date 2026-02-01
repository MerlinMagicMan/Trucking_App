"""
Ingestion scheduler — runs connectors on a cadence, stores snapshots (Phase 3A)

Uses APScheduler BackgroundScheduler so it runs inside the FastAPI process.
"""
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.connection import SessionLocal
from app.connectors.mock_market import MockMarketConnector
from app.ingestion.snapshot_store import upsert_snapshot, expire_stale
from app.models.tenant import Organization
from app.analytics.runner import run_analytics_cycle

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None

# Default ingestion interval in minutes
INGESTION_INTERVAL_MINUTES = 15


def _run_ingestion() -> None:
    """
    Single ingestion cycle:
    1. For each org, run mock_market connector
    2. Upsert snapshots
    3. Expire stale loads
    """
    db = SessionLocal()
    try:
        orgs = db.query(Organization).all()
        if not orgs:
            logger.info("Ingestion: no orgs found, skipping")
            return

        connector = MockMarketConnector()

        for org in orgs:
            org_id = str(org.id)
            try:
                # Fetch loads (use a central location; each org could have a different one)
                # For MVP, use OKC as default search center
                raw_loads, metadata = connector.search_loads(
                    truck_lat=35.4676, truck_lng=-97.5164,
                    radius_miles=5000,  # wide — get everything
                )

                ingested = 0
                for raw_load in raw_loads:
                    canonical = connector.normalize(raw_load)
                    upsert_snapshot(
                        db=db,
                        org_id=org_id,
                        source=connector.name,
                        external_id=raw_load["id"],
                        raw_payload=raw_load,
                        canonical_dict=canonical.model_dump(mode="json"),
                        posted_at=datetime.fromisoformat(raw_load["posted_at"].replace("Z", "+00:00")) if raw_load.get("posted_at") else None,
                    )
                    ingested += 1

                # Expire loads not seen in this cycle
                expired = expire_stale(db, org_id, source=connector.name, older_than_minutes=INGESTION_INTERVAL_MINUTES + 5)

                db.commit()
                logger.info(
                    f"Ingestion [{org.name}]: {ingested} upserted, {expired} expired "
                    f"({metadata.get('total_loads_found', 0)} from connector)"
                )
            except Exception as e:
                db.rollback()
                logger.error(f"Ingestion failed for org {org.name}: {e}")

    except Exception as e:
        logger.error(f"Ingestion cycle failed: {e}")
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the background ingestion scheduler."""
    global _scheduler
    if _scheduler is not None:
        return  # already running

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_ingestion,
        "interval",
        minutes=INGESTION_INTERVAL_MINUTES,
        id="load_ingestion",
        next_run_time=datetime.utcnow(),  # run immediately on start
    )
    _scheduler.add_job(
        run_analytics_cycle,
        "interval",
        minutes=60,
        id="analytics_hourly",
        next_run_time=datetime.utcnow(),  # run immediately on start
    )
    _scheduler.start()
    logger.info(f"Ingestion scheduler started (every {INGESTION_INTERVAL_MINUTES} min, analytics hourly)")


def stop_scheduler() -> None:
    """Stop the background ingestion scheduler."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Ingestion scheduler stopped")


def get_scheduler_status() -> dict:
    """Return current scheduler status for admin endpoint."""
    if _scheduler is None:
        return {"running": False}

    jobs = _scheduler.get_jobs()
    job_info = []
    for job in jobs:
        job_info.append({
            "id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {
        "running": _scheduler.running if _scheduler else False,
        "interval_minutes": INGESTION_INTERVAL_MINUTES,
        "jobs": job_info,
    }
