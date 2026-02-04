"""
Calibration API — Stratum 5A

GET /api/calibration/report — org-scoped prediction calibration report.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_org_id
from app.db.connection import get_db
from app.outcomes.calibration import compute_calibration_report

logger = logging.getLogger(__name__)

calibration_router = APIRouter(tags=["calibration"])


@calibration_router.get("/calibration/report")
def get_calibration_report(
    window_days: int = Query(30, ge=1, le=365),
    min_sample: int = Query(3, ge=1, le=100),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Return prediction calibration report for the org."""
    try:
        report = compute_calibration_report(
            db, org_id, window_days=window_days, min_sample=min_sample,
        )
    except Exception as e:
        logger.error(f"Calibration computation failed: {e}")
        raise HTTPException(status_code=500, detail="Calibration computation failed")

    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data: fewer than {min_sample} completed outcomes in the last {window_days} days",
        )

    return report
