"""
Negotiation intelligence — deterministic math only (Phase 3C)

Takes lane percentiles + offered rate → position + suggestions.
No DB access, no side effects.
"""
from typing import Optional, Dict, Any, List


def compute_negotiation(
    offered_rate_usd: float,
    rate_p25: Optional[float],
    rate_p50: Optional[float],
    rate_p75: Optional[float],
    rate_p90: Optional[float],
    time_to_cover_p50_minutes: Optional[float],
    load_count: int,
) -> Dict[str, Any]:
    """
    Compute negotiation position and suggestions from lane percentiles.

    Returns dict with:
        position: "below_median" | "near_median" | "strong"
        suggested_counter: float (p50 or p75)
        suggested_accept: float (p50)
        walk_away: float (p25)
        percentile_position: estimated percentile of offered rate
        explanations: list of plain English strings
    """
    if rate_p50 is None or load_count < 5:
        return {
            "position": None,
            "suggested_counter": None,
            "suggested_accept": None,
            "walk_away": None,
            "percentile_position": None,
            "explanations": [
                "Insufficient lane data for negotiation guidance.",
                f"Only {load_count} samples available (minimum 5 required).",
            ],
        }

    # Estimate percentile position of the offered rate
    percentile_position = _estimate_percentile_position(
        offered_rate_usd, rate_p25, rate_p50, rate_p75, rate_p90
    )

    # Classify position (handle None percentiles gracefully)
    if rate_p75 is not None and offered_rate_usd >= rate_p75:
        position = "strong"
    elif offered_rate_usd >= rate_p50:
        position = "near_median" if rate_p75 is not None else "strong"
    else:
        position = "below_median"

    # Suggestions (use available percentiles, fallback to p50)
    suggested_counter = rate_p75 if rate_p75 is not None else rate_p50
    suggested_accept = rate_p50
    walk_away = rate_p25

    # Explanations
    explanations = _build_explanations(
        offered_rate_usd, position, rate_p25, rate_p50, rate_p75, rate_p90,
        percentile_position, time_to_cover_p50_minutes, load_count,
    )

    return {
        "position": position,
        "suggested_counter": suggested_counter,
        "suggested_accept": suggested_accept,
        "walk_away": walk_away,
        "percentile_position": round(percentile_position, 1),
        "explanations": explanations,
    }


def _estimate_percentile_position(
    rate: float,
    p25: Optional[float],
    p50: Optional[float],
    p75: Optional[float],
    p90: Optional[float],
) -> float:
    """
    Estimate what percentile the offered rate falls at.
    Linear interpolation between known percentile markers.
    """
    markers = []
    if p25 is not None:
        markers.append((25, p25))
    if p50 is not None:
        markers.append((50, p50))
    if p75 is not None:
        markers.append((75, p75))
    if p90 is not None:
        markers.append((90, p90))

    if not markers:
        return 50.0

    # Below lowest marker
    if rate <= markers[0][1]:
        return max(0, markers[0][0] * (rate / markers[0][1]) if markers[0][1] > 0 else 0)

    # Above highest marker
    if rate >= markers[-1][1]:
        return min(100, markers[-1][0] + (100 - markers[-1][0]) * 0.5)

    # Interpolate between markers
    for i in range(len(markers) - 1):
        p_low, v_low = markers[i]
        p_high, v_high = markers[i + 1]
        if v_low <= rate <= v_high:
            if v_high == v_low:
                return (p_low + p_high) / 2.0
            frac = (rate - v_low) / (v_high - v_low)
            return p_low + frac * (p_high - p_low)

    return 50.0


def _build_explanations(
    offered: float,
    position: str,
    p25: Optional[float],
    p50: Optional[float],
    p75: Optional[float],
    p90: Optional[float],
    percentile_pos: float,
    ttc_p50: Optional[float],
    sample_count: int,
) -> List[str]:
    """Build plain English negotiation explanations."""
    lines = []

    lines.append(
        f"Your offered rate of ${offered:,.0f} sits at approximately the "
        f"{percentile_pos:.0f}th percentile of recent lane activity."
    )

    if position == "strong":
        ref = f" (${p75:,.0f})" if p75 is not None else ""
        lines.append(f"This is a strong offer — above the 75th percentile{ref}. Consider accepting.")
    elif position == "near_median":
        counter = f" Counter at ${p75:,.0f} for a stronger position." if p75 is not None else ""
        lines.append(f"This offer is near the median (${p50:,.0f}).{counter}")
    else:
        counter = f" Counter at ${p75:,.0f} (75th pct) or hold" if p75 is not None else " Hold"
        lines.append(f"This is below the median rate of ${p50:,.0f}.{counter} for at least ${p50:,.0f}.")

    if ttc_p50 is not None:
        if ttc_p50 < 60:
            lines.append(
                f"Loads on this lane are covering quickly (~{ttc_p50:.0f} min). "
                f"You have leverage — don't settle below market."
            )
        elif ttc_p50 > 180:
            lines.append(
                f"Loads on this lane sit for a while (~{ttc_p50:.0f} min). "
                f"Broker may have more flexibility to negotiate."
            )

    lines.append(f"Based on {sample_count} loads observed in this window.")

    return lines
