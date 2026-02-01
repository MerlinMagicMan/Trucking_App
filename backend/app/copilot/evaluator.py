"""
Copilot evaluator — pure deterministic plan degradation logic (Phase 4)

No DB access. Takes pre-fetched data as arguments.
"""
from typing import Dict, Any, List, Optional, Tuple


def evaluate_plan(
    plan: Dict[str, Any],
    lane_rate_p50: Optional[float],
    lane_rate_p75: Optional[float],
    lane_time_to_cover: Optional[float],
    lane_load_count: Optional[int],
    market_temperature: Optional[str],
    efficiency_score: Optional[float],
    loads_active: Dict[str, bool],
) -> Tuple[str, List[Dict], List[Dict], List[str]]:
    """
    Evaluate plan degradation.

    Returns: (status, signals, suggestions, explanations)
    """
    signals: List[Dict] = []
    suggestions: List[Dict] = []
    explanations: List[str] = []

    # Extract plan assumed rate from first load
    plan_rate = _extract_plan_rate(plan)
    if plan_rate is None:
        return "unknown", [], [], ["Could not determine plan assumed rate."]

    # ---- Signal: load_unavailable ----
    for load_key, is_active in loads_active.items():
        if not is_active:
            signals.append({
                "kind": "load_unavailable",
                "severity": "high",
                "summary": f"Load {load_key} is no longer active.",
                "details": {"load_id": load_key, "is_active": False},
            })
            explanations.append(f"Load {load_key} has expired or been covered.")

    # ---- Signal: lane_rate_shift ----
    if lane_rate_p50 is not None and plan_rate > 0:
        delta_pct = (lane_rate_p50 - plan_rate) / plan_rate * 100
        abs_delta = abs(delta_pct)

        if abs_delta >= 10:
            severity = "low"
            if abs_delta >= 30:
                severity = "high"
            elif abs_delta >= 20:
                severity = "medium"

            direction = "increased" if delta_pct > 0 else "decreased"
            signals.append({
                "kind": "lane_rate_shift",
                "severity": severity,
                "summary": f"Lane p50 rate has {direction} {abs_delta:.0f}% vs plan.",
                "details": {
                    "plan_rate_usd": round(plan_rate, 2),
                    "lane_p50_usd": round(lane_rate_p50, 2),
                    "delta_pct": round(delta_pct, 1),
                },
            })
            explanations.append(
                f"Lane median rate is ${lane_rate_p50:.0f} vs plan's ${plan_rate:.0f} "
                f"({delta_pct:+.0f}%)."
            )

            # Suggestions for rate shift
            if delta_pct > 0 and lane_time_to_cover is not None and lane_time_to_cover <= 60:
                suggestions.append({
                    "kind": "take_now",
                    "summary": "Market rate is up and loads cover quickly.",
                    "rationale": (
                        f"Lane p50 is ${lane_rate_p50:.0f} (+{delta_pct:.0f}%) and "
                        f"time-to-cover is {lane_time_to_cover:.0f}min. "
                        "Loads may not last."
                    ),
                    "data": {
                        "lane_p50_usd": round(lane_rate_p50, 2),
                        "time_to_cover_minutes": round(lane_time_to_cover, 1),
                    },
                })
                if lane_rate_p75 is not None:
                    suggestions.append({
                        "kind": "counter_offer",
                        "summary": f"Counter at p75 (${lane_rate_p75:.0f}).",
                        "rationale": (
                            f"Market supports higher rates. p75 is ${lane_rate_p75:.0f}."
                        ),
                        "data": {
                            "suggested_rate_usd": round(lane_rate_p75, 2),
                            "lane_p75_usd": round(lane_rate_p75, 2),
                        },
                    })

            elif delta_pct < 0:
                suggestions.append({
                    "kind": "counter_offer",
                    "summary": f"Counter at current p50 (${lane_rate_p50:.0f}).",
                    "rationale": (
                        f"Market rate has dropped. Current median is ${lane_rate_p50:.0f}."
                    ),
                    "data": {
                        "suggested_rate_usd": round(lane_rate_p50, 2),
                    },
                })

    # ---- Signal: destination_score_drop ----
    if efficiency_score is not None and efficiency_score <= 50:
        severity = "high" if efficiency_score <= 25 else "medium"
        signals.append({
            "kind": "destination_score_drop",
            "severity": severity,
            "summary": f"Destination efficiency score is {efficiency_score:.0f}/100.",
            "details": {"efficiency_score": round(efficiency_score, 1)},
        })
        explanations.append(
            f"Delivery destination has low efficiency ({efficiency_score:.0f}/100). "
            "Reload opportunities may be limited."
        )

    # ---- Signal: market_temp_downgrade ----
    if market_temperature == "cold":
        signals.append({
            "kind": "market_temp_downgrade",
            "severity": "medium",
            "summary": "Delivery market is cold.",
            "details": {"market_temperature": "cold"},
        })
        explanations.append(
            "Delivery market is classified as cold. "
            "Expect longer wait times for reload."
        )
        suggestions.append({
            "kind": "add_buffer",
            "summary": "Add 2-hour buffer for reload wait.",
            "rationale": "Cold market may require extra time to find next load.",
            "data": {"buffer_hours": 2, "market_temperature": "cold"},
        })

    # ---- Suggestion: alternate_destination ----
    needs_alternate = (
        (efficiency_score is not None and efficiency_score <= 50)
        or market_temperature == "cold"
        or any(s["kind"] == "lane_rate_shift" and s["details"].get("delta_pct", 0) < -10
               for s in signals)
    )
    if needs_alternate:
        suggestions.append({
            "kind": "alternate_destination",
            "summary": "Consider alternate destinations with better reload markets.",
            "rationale": _alternate_rationale(efficiency_score, market_temperature),
            "data": {
                "efficiency_score": round(efficiency_score, 1) if efficiency_score is not None else None,
                "market_temperature": market_temperature,
            },
        })

    # ---- Determine overall status ----
    if len(signals) == 0:
        status = "ok"
        explanations.append("Plan appears healthy based on current intel.")
    else:
        status = "degraded"

    return status, signals, suggestions, explanations


def _extract_plan_rate(plan: Dict[str, Any]) -> Optional[float]:
    """Extract plan assumed rate from first load."""
    loads = plan.get("loads", [])
    if not loads:
        return None
    first = loads[0]
    load = first.get("load", first)
    rate = load.get("rate_total")
    if rate is not None:
        return float(rate)
    # Fallback: revenue from LoadInPlan
    revenue = first.get("revenue_usd")
    if revenue is not None:
        return float(revenue)
    return None


def _alternate_rationale(
    efficiency_score: Optional[float],
    market_temperature: Optional[str],
) -> str:
    parts = []
    if efficiency_score is not None and efficiency_score <= 50:
        parts.append(f"destination efficiency is low ({efficiency_score:.0f}/100)")
    if market_temperature == "cold":
        parts.append("delivery market is cold")
    if not parts:
        parts.append("lane rate has dropped significantly")
    return "Alternate destinations recommended because " + " and ".join(parts) + "."
