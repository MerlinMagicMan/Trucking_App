"""
Confidence Weighting — Stratum 6A

Pure functions for confidence-weighted plan ranking.
Part of TruckLEARN (Premium tier).

Design principles:
- Decimal-only: NO FLOAT LITERALS
- Unknown confidence = no weighting influence (multiplier=1.00)
- Multiplier bounded to [0.50, 1.00]
- Deterministic: same inputs → same output
"""
from decimal import Decimal
from typing import Optional

# Constants as Decimal — NO FLOATS
HALF = Decimal("0.5")
HUNDRED = Decimal("100")
MIN_MULTIPLIER = Decimal("0.5")
MAX_MULTIPLIER = Decimal("1.0")

# Confidence thresholds (for reference, not used in weighting calculation)
CONFIDENCE_HIGH_THRESHOLD = 80
CONFIDENCE_MEDIUM_THRESHOLD = 55
CONFIDENCE_UNKNOWN_SAMPLE_THRESHOLD = 10


def compute_confidence_multiplier(confidence_score: Optional[int]) -> Decimal:
    """
    Compute the confidence multiplier for plan ranking.

    Formula: multiplier = 0.5 + 0.5 × (confidence_score / 100)

    Args:
        confidence_score: Trust confidence score (0-100), or None if unknown

    Returns:
        Decimal multiplier in range [0.50, 1.00]
        Returns 1.00 (no influence) if confidence is unknown/missing

    Examples:
        confidence_score=100 → multiplier=1.00
        confidence_score=80  → multiplier=0.90
        confidence_score=55  → multiplier=0.775
        confidence_score=0   → multiplier=0.50
        confidence_score=None → multiplier=1.00 (no influence)
    """
    # Unknown/missing confidence = no weighting influence
    if confidence_score is None:
        return MAX_MULTIPLIER

    # Clamp score to valid range [0, 100]
    clamped_score = max(0, min(100, confidence_score))

    # Calculate multiplier using Decimal arithmetic only
    score_decimal = Decimal(clamped_score)
    ratio = score_decimal / HUNDRED
    multiplier = HALF + (HALF * ratio)

    # Ensure bounded to [0.50, 1.00] (should be guaranteed by formula, but defensive)
    return max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, multiplier))


def compute_weighted_score(
    profit_per_day: Decimal,
    confidence_score: Optional[int]
) -> Decimal:
    """
    Compute confidence-weighted profit score for plan ranking.

    Formula: weighted_score = profit_per_day × multiplier
    Where multiplier = 0.5 + 0.5 × (confidence_score / 100)

    Args:
        profit_per_day: Plan's profit per day in USD (Decimal)
        confidence_score: Trust confidence score (0-100), or None if unknown

    Returns:
        Weighted score as Decimal
        If confidence is unknown/missing, returns profit_per_day unchanged

    Design notes:
        - Trust influences ranking, NOT eligibility
        - Unknown confidence = no ranking influence (preserves user trust)
        - Higher confidence = score closer to full profit_per_day
        - Lower confidence = reduced weighted score
        - Multiplier bounded to [0.50, 1.00] — confidence never makes plan look better than it is
    """
    multiplier = compute_confidence_multiplier(confidence_score)
    return profit_per_day * multiplier


def get_confidence_label(confidence_score: Optional[int]) -> str:
    """
    Get human-readable confidence label from numeric score.

    Args:
        confidence_score: Trust confidence score (0-100), or None

    Returns:
        "high" (≥80), "medium" (55-79), "low" (<55), or "unknown" (None)
    """
    if confidence_score is None:
        return "unknown"
    if confidence_score >= CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    if confidence_score >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "medium"
    return "low"
