"""
Shared FastAPI dependencies (Phase 2A)
"""
from fastapi import Header, HTTPException


def get_org_id(x_org_id: str = Header(None)) -> str:
    """Extract org_id from X-Org-Id header. Required for all org-scoped endpoints."""
    if not x_org_id:
        raise HTTPException(
            status_code=400,
            detail="X-Org-Id header is required for this endpoint",
        )
    return x_org_id
