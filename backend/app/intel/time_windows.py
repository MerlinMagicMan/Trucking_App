"""
Time window resolution for intelligence queries (Phase 3C)

All analytics rows are stored with exact (window_start, window_end) pairs.
This module resolves a human-friendly window param ("1h", "6h", "24h")
+ optional as_of timestamp into exact window boundaries for DB lookup.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

# Supported window durations
WINDOW_DURATIONS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
}

DEFAULT_WINDOW = "6h"


def floor_to_hour(dt: datetime) -> datetime:
    """Round datetime down to the nearest past hour (UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def resolve_window(
    window: str = DEFAULT_WINDOW,
    as_of: Optional[str] = None,
) -> Tuple[datetime, datetime, str]:
    """
    Resolve window param + as_of into exact (window_start, window_end, window_label).

    Args:
        window: "1h", "6h", or "24h"
        as_of: ISO timestamp string, or None for "now"

    Returns:
        (window_start, window_end, window_label)

    Raises:
        ValueError: if window param is invalid
    """
    if window not in WINDOW_DURATIONS:
        raise ValueError(f"Invalid window: {window}. Must be one of: {list(WINDOW_DURATIONS.keys())}")

    duration = WINDOW_DURATIONS[window]

    if as_of:
        ref = datetime.fromisoformat(as_of)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
    else:
        ref = datetime.now(timezone.utc)

    window_end = floor_to_hour(ref)
    window_start = window_end - duration

    return window_start, window_end, window
