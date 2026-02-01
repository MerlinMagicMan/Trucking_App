"""
Analytics runner — orchestrates hourly analytics computation (Phase 3B)

Computes 1h, 6h, and 24h windows ending at the current rounded hour.
Safe to rerun (all jobs use UPSERT).
"""
import logging
from datetime import datetime, timedelta, timezone

from app.db.connection import SessionLocal
from app.models.tenant import Organization
from app.models.snapshot import LoadSnapshot
from app.analytics.jobs import (
    compute_lane_statistics,
    compute_market_statistics,
    compute_destination_scores,
)

logger = logging.getLogger(__name__)

# Windows to compute on each hourly run
WINDOW_HOURS = [1, 6, 24]


def _floor_to_hour(dt: datetime) -> datetime:
    """Round datetime down to the nearest hour."""
    return dt.replace(minute=0, second=0, microsecond=0)


def run_analytics_cycle() -> None:
    """
    Single analytics computation cycle.
    For each org × source × window: compute lane, market, destination stats.
    """
    db = SessionLocal()
    try:
        orgs = db.query(Organization).all()
        if not orgs:
            logger.info("Analytics: no orgs found, skipping")
            return

        now = datetime.now(timezone.utc)
        window_end = _floor_to_hour(now)

        for org in orgs:
            org_id = str(org.id)

            # Discover active sources for this org
            sources = (
                db.query(LoadSnapshot.source)
                .filter(LoadSnapshot.org_id == org_id)
                .distinct()
                .all()
            )
            source_list = [s[0] for s in sources]

            if not source_list:
                continue

            for source in source_list:
                for hours in WINDOW_HOURS:
                    window_start = window_end - timedelta(hours=hours)
                    try:
                        lanes = compute_lane_statistics(db, org_id, source, window_start, window_end)
                        markets = compute_market_statistics(db, org_id, source, window_start, window_end)
                        dests = compute_destination_scores(db, org_id, source, window_start, window_end)
                        db.commit()

                        logger.info(
                            f"Analytics [{org.name}] {source} {hours}h: "
                            f"{lanes} lanes, {markets} markets, {dests} destinations"
                        )
                    except Exception as e:
                        db.rollback()
                        logger.error(
                            f"Analytics failed [{org.name}] {source} {hours}h: {e}"
                        )

    except Exception as e:
        logger.error(f"Analytics cycle failed: {e}")
    finally:
        db.close()
