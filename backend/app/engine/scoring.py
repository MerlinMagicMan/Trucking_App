"""
Reload scoring and confidence calculation
Determines reload probability for each load
"""
from typing import Tuple, Literal
from datetime import datetime


# Known reefer hubs (major markets with high reload probability)
REEFER_HUBS = {
    "Dallas": {"state": "TX", "bonus": 8},
    "Fort Worth": {"state": "TX", "bonus": 8},
    "Houston": {"state": "TX", "bonus": 8},
    "Kansas City": {"state": "MO", "bonus": 8},
    "Phoenix": {"state": "AZ", "bonus": 8},
    "Atlanta": {"state": "GA", "bonus": 8},
    # Secondary hubs
    "Memphis": {"state": "TN", "bonus": 5},
    "San Antonio": {"state": "TX", "bonus": 5},
    "Oklahoma City": {"state": "OK", "bonus": 5},
    "Tulsa": {"state": "OK", "bonus": 5},
}


def is_reefer_hub(city: str, state: str) -> Tuple[bool, int]:
    """
    Check if delivery is to a known reefer hub
    Returns (is_hub: bool, bonus_points: int)
    """
    city_normalized = city.strip()
    for hub_city, hub_data in REEFER_HUBS.items():
        if hub_city.lower() in city_normalized.lower():
            if hub_data["state"] == state:
                return True, hub_data["bonus"]
    return False, 0


def is_strong_time_band(arrival_time: datetime) -> Tuple[bool, int]:
    """
    Check if delivery time is in a strong reload time band
    Strong bands: 6am-10am (morning) and 11am-2pm (early afternoon)

    Returns (is_strong: bool, bonus_points: int)
    """
    hour = arrival_time.hour

    # Morning deliveries (6am-10am) - best for reloading
    if 6 <= hour < 10:
        return True, 5

    # Early afternoon (11am-2pm) - good for same-day reload
    if 11 <= hour < 14:
        return True, 5

    # Late morning (10am-11am) - decent
    if 10 <= hour < 11:
        return True, 3

    return False, 0


def calculate_appointment_risk_penalty(
    arrival_time: datetime,
    window_start: datetime,
    window_end: datetime
) -> Tuple[int, str]:
    """
    Calculate penalty for tight or risky appointment windows

    Returns (penalty_points: int, risk_level: str)
    """
    # Calculate window width in hours
    window_width_hours = (window_end - window_start).total_seconds() / 3600

    # Calculate buffer time (arrival to window start)
    buffer_hours = (window_start - arrival_time).total_seconds() / 3600

    penalty = 0
    risk_level = "low"

    # Late arrival (arrive after window start)
    if buffer_hours < 0:
        penalty += 20
        risk_level = "high"
    # Very tight (less than 1 hour buffer)
    elif buffer_hours < 1:
        penalty += 15
        risk_level = "high"
    # Tight (1-2 hour buffer)
    elif buffer_hours < 2:
        penalty += 10
        risk_level = "medium"
    # Comfortable (2-4 hours)
    elif buffer_hours < 4:
        penalty += 5
        risk_level = "low"

    # Narrow window (less than 2 hours)
    if window_width_hours < 2:
        penalty += 5
        if risk_level == "low":
            risk_level = "medium"

    return min(penalty, 20), risk_level  # Cap at 20 points


def calculate_reload_score(
    deadhead_miles: float,
    arrival_at_delivery: datetime,
    delivery_city: str,
    delivery_state: str,
    delivery_window_start: datetime,
    delivery_window_end: datetime,
    has_complete_data: bool
) -> int:
    """
    Calculate reload probability score (0-100)

    Scoring factors:
    - Base: 100 points
    - Deadhead penalty: -1.5 per mile
    - Appointment risk: 0-20 point penalty
    - Reefer hub bonus: +5 to +8 points
    - Time band bonus: +3 to +5 points
    - Data completeness: affects confidence, not score

    NO automatic Oklahoma boost per CTO guidance
    """
    base_score = 100

    # Deadhead penalty (empty miles are expensive)
    deadhead_penalty = deadhead_miles * 1.5

    # Appointment timing risk
    appointment_penalty, _ = calculate_appointment_risk_penalty(
        arrival_at_delivery,
        delivery_window_start,
        delivery_window_end
    )

    # Reefer hub bonus
    is_hub, hub_bonus = is_reefer_hub(delivery_city, delivery_state)

    # Time band bonus
    is_strong_time, time_bonus = is_strong_time_band(arrival_at_delivery)

    # Calculate final score
    score = base_score - deadhead_penalty - appointment_penalty + hub_bonus + time_bonus

    # Clamp to 0-100
    score = max(0, min(100, score))

    return int(score)


def calculate_confidence(
    has_delivery_window: bool,
    has_pickup_window: bool,
    has_miles_data: bool,
    appointment_risk_level: str,
    is_reefer_hub: bool
) -> Literal["low", "medium", "high"]:
    """
    Calculate confidence level based on data completeness and timing

    High confidence:
    - Complete data (windows, miles)
    - Low appointment risk
    - Known reefer hub

    Medium confidence:
    - Some missing data OR medium risk OR secondary market

    Low confidence:
    - Missing critical data OR high risk OR unknown market
    """
    completeness_score = sum([
        has_delivery_window,
        has_pickup_window,
        has_miles_data
    ])

    # High confidence requirements
    if completeness_score == 3 and appointment_risk_level == "low" and is_reefer_hub:
        return "high"

    # Low confidence triggers
    if not has_delivery_window:  # Critical data missing
        return "low"

    if appointment_risk_level == "high":
        return "low"

    if completeness_score == 1:
        return "low"

    # Everything else is medium
    return "medium"
