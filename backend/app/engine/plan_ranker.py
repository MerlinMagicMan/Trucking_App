"""
Plan Ranker — Stratum 6A

Ranks plans with optional confidence weighting.
Part of TruckPLAN (Base tier) — no premium imports here.

Design principles:
- Base tier: rank by profit_per_day only
- Premium tier: rank by confidence-weighted score (via injected callback)
- Deterministic: secondary sort by plan_id for tiebreaker
- Pure function: does not mutate input list
"""
from decimal import Decimal
from typing import Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.plan import Plan

# Type alias for weighting function callback
# Takes (profit_per_day: Decimal, confidence_score: Optional[int]) -> Decimal
WeightingFn = Callable[[Decimal, Optional[int]], Decimal]


def rank_plans(
    plans: "List[Plan]",
    weighting_fn: Optional[WeightingFn] = None
) -> "List[Plan]":
    """
    Rank plans by economic value, optionally weighted by confidence.

    Args:
        plans: List of Plan objects to rank
        weighting_fn: Optional callback for confidence weighting.
                     If None, ranks by profit_per_day only (base tier behavior).
                     If provided, ranks by weighting_fn(profit_per_day, confidence_score).

    Returns:
        New list of plans sorted by ranking criteria (descending).
        Original list is not mutated.

    Ranking criteria:
        - Primary: weighted_score (or profit_per_day if no weighting_fn)
        - Secondary: plan_id (deterministic tiebreaker)

    Design notes:
        - This function has NO imports from premium modules (TruckLEARN)
        - Weighting logic is injected via callback at runtime
        - Base tier passes weighting_fn=None → profit-only ranking
        - Premium tier passes weighting function from trust.weighting
    """
    if not plans:
        return []

    def sort_key(plan: "Plan"):
        """Generate sort key for a plan."""
        profit = Decimal(str(plan.profit_per_day_usd))

        if weighting_fn is not None:
            # Premium tier: use confidence-weighted score
            confidence = getattr(plan, 'confidence_score', None)
            weighted_score = weighting_fn(profit, confidence)
        else:
            # Base tier: use raw profit
            weighted_score = profit

        # Return tuple: negative weighted_score (for descending), then plan_id (tiebreaker)
        return (-weighted_score, str(plan.plan_id))

    # Sort a copy, don't mutate original
    return sorted(plans, key=sort_key)


def rank_plans_profit_only(plans: "List[Plan]") -> "List[Plan]":
    """
    Rank plans by profit_per_day only (no confidence weighting).

    Convenience wrapper for base tier ranking.
    Equivalent to rank_plans(plans, weighting_fn=None).

    Args:
        plans: List of Plan objects to rank

    Returns:
        New list of plans sorted by profit_per_day descending.
    """
    return rank_plans(plans, weighting_fn=None)
